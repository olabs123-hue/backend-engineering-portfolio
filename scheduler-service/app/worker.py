"""At-least-once worker with renewable leases and token-fenced state transitions."""
import subprocess
import time
import uuid
import threading
import psycopg
from .main import DB,SCHEMA
LEASE_SECONDS=30
def run_task(kind,payload):
    if kind=="sum":
        nums=payload.get("numbers")
        if not isinstance(nums,list) or len(nums)>10000 or not all(type(x) in (int,float) for x in nums): raise ValueError("invalid numbers")
        return sum(nums)
    if kind=="uppercase":
        value=payload.get("text")
        if not isinstance(value,str) or len(value)>10000: raise ValueError("invalid text")
        return value.upper()
    raise ValueError("unsupported task")
def backoff(attempts,executable="/usr/local/bin/backoff"):
    output=subprocess.run([executable,str(attempts)],capture_output=True,text=True,timeout=2,check=True)
    return int(output.stdout.strip())
def reap_exhausted(conn):
    with conn.transaction():
        result=conn.execute("""UPDATE jobs SET status='dead',lease_until=NULL,claim_token=NULL,
            last_error=COALESCE(last_error,'worker lease expired after final attempt')
            WHERE status='running' AND lease_until<now() AND attempts>=max_attempts""")
        return result.rowcount
def claim(conn):
    token=str(uuid.uuid4())
    with conn.transaction():
        row=conn.execute("""SELECT id,kind,payload,attempts,max_attempts FROM jobs
          WHERE ((status='pending' AND run_at<=now()) OR (status='running' AND lease_until<now()))
          AND attempts<max_attempts ORDER BY run_at,id FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not row: return None
        conn.execute("""UPDATE jobs SET status='running',attempts=attempts+1,
          lease_until=now()+(%s*interval '1 second'),claim_token=%s WHERE id=%s""",(LEASE_SECONDS,token,row[0]))
    return (*row,token)
def renew_lease(job_id,token):
    with psycopg.connect(DB) as conn:
        result=conn.execute("""UPDATE jobs SET lease_until=now()+(%s*interval '1 second')
          WHERE id=%s AND claim_token=%s AND status='running' AND lease_until>now()""",(LEASE_SECONDS,job_id,token))
        return result.rowcount==1
def complete(conn,job_id,token):
    with conn.transaction():
        result=conn.execute("""UPDATE jobs SET status='done',lease_until=NULL,claim_token=NULL
          WHERE id=%s AND claim_token=%s AND status='running' AND lease_until>now()""",(job_id,token))
        return result.rowcount==1
def fail(conn,job_id,token,attempts,max_attempts,error):
    dead=attempts>=max_attempts
    delay=0 if dead else backoff(attempts)
    with conn.transaction():
        result=conn.execute("""UPDATE jobs SET status=%s,lease_until=NULL,claim_token=NULL,
          run_at=now()+(%s*interval '1 second'),last_error=%s
          WHERE id=%s AND claim_token=%s AND status='running' AND lease_until>now()""",("dead" if dead else "pending",delay,str(error)[:500],job_id,token))
        return result.rowcount==1
def _heartbeat(job_id,token,stop):
    while not stop.wait(LEASE_SECONDS/3):
        try:
            if not renew_lease(job_id,token): return
        except psycopg.Error: return
def main():
    while True:
        try:
            with psycopg.connect(DB) as conn:
                conn.execute(SCHEMA,prepare=False)
                reap_exhausted(conn)
                row=claim(conn)
                if not row:
                    time.sleep(.5)
                    continue
                job_id,kind,payload,previous_attempts,max_attempts,token=row
                stop=threading.Event()
                thread=threading.Thread(target=_heartbeat,args=(job_id,token,stop),daemon=True)
                thread.start()
                try:
                    run_task(kind,payload)
                    complete(conn,job_id,token)
                except Exception as exc:
                    fail(conn,job_id,token,previous_attempts+1,max_attempts,exc)
                finally:
                    stop.set()
                    thread.join(timeout=1)
        except (psycopg.Error,OSError,subprocess.SubprocessError) as exc:
            print(f"worker retry: {exc}",flush=True)
            time.sleep(2)
if __name__=="__main__": main()
