#!/usr/bin/env python3
"""Isolated PostgreSQL-backed benchmark; run only against disposable test databases."""
import argparse, concurrent.futures, json, os, statistics, time, uuid
import httpx
import psycopg

def check(ok, message):
    if not ok: raise AssertionError(message)

def ledger(base, db, count, workers):
    run = uuid.uuid4().hex[:12]
    with httpx.Client(base_url=base, timeout=30) as c:
        r=c.post("/auth/register",json={"username":"bench_"+run,"password":"benchmark-only-password-123"})
        r.raise_for_status()
        r=c.post("/auth/login",json={"username":"bench_"+run,"password":"benchmark-only-password-123"})
        r.raise_for_status()
        headers={"Authorization":"Bearer "+r.json()["access_token"]}
        ids=[]
        for owner,balance in (("source",count+100),("sink",0)):
            r=c.post("/accounts",headers=headers,json={"owner":owner,"opening_balance":balance})
            r.raise_for_status(); ids.append(r.json()["id"])
    def send(i, key=None):
        t=time.perf_counter()
        with httpx.Client(base_url=base,timeout=30) as c:
            r=c.post("/transfers",headers=headers,json={"from_id":ids[0],"to_id":ids[1],"amount":1,"idempotency_key":key or f"{run}-transfer-{i:08d}"})
        return (r.status_code,r.json(),time.perf_counter()-t)
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(send,range(count)))
    elapsed=time.perf_counter()-start
    successes=sum(code==201 and not body.get("replayed",True) for code,body,_ in results)
    check(successes==count,f"ledger success count {successes}/{count}; errors: {[r[:2] for r in results if r[0]!=201][:3]}")
    # Concurrent requests sharing the same idempotency key must insert exactly one transfer.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        dup=list(pool.map(lambda i:send(i,f"{run}-duplicate-key"),range(workers)))
    check(all(code==201 for code,_,_ in dup),"duplicate requests returned errors")
    check(sum(not body.get("replayed",True) for _,body,_ in dup)==1,"duplicate requests created more than one transfer")
    with psycopg.connect(db) as conn:
        a,b=conn.execute("SELECT id,balance,opening_balance FROM accounts WHERE id=ANY(%s) ORDER BY id",(ids,)).fetchall()
        transfers=conn.execute("SELECT count(*) FROM transfers WHERE from_id=%s AND to_id=%s",(ids[0],ids[1])).fetchone()[0]
        bad=conn.execute("""SELECT t.id FROM transfers t LEFT JOIN journal j ON j.transfer_id=t.id
            WHERE t.from_id=%s AND t.to_id=%s GROUP BY t.id HAVING count(j.id)<>2 OR sum(j.amount)<>0""",tuple(ids)).fetchall()
    check(a[1]+b[1]==a[2]+b[2],"total balance changed")
    check(a[1]==a[2]-count-1 and b[1]==count+1,"account balances incorrect")
    check(transfers==count+1 and not bad,"transfer count or journal invariant failed")
    return {"attempted_transfers":count,"successful_transfers":successes,"concurrent_clients":workers,
            "elapsed_seconds":round(elapsed,3),"transfers_per_second":round(successes/elapsed,2),
            "duplicate_requests":workers,"unique_duplicate_key_commits":1,
            "journal_mismatches":len(bad),"balance_conserved":True,
            "p50_ms":round(statistics.median(x[2] for x in results)*1000,2)}

def scheduler(db, count, workers):
    import sys
    sys.path.insert(0,os.path.abspath("scheduler-service"))
    from app.worker import claim,complete
    from psycopg.types.json import Jsonb
    with psycopg.connect(db) as conn:
        conn.execute("TRUNCATE jobs RESTART IDENTITY")
        with conn.cursor() as cur:
            for i in range(count):
                cur.execute("INSERT INTO jobs(kind,payload) VALUES ('sum',%s)",(Jsonb({"numbers":[i,1]}),))
    def work(_):
        n=0
        with psycopg.connect(db) as conn:
            while True:
                item=claim(conn)
                if item is None: break
                check(complete(conn,item[0],item[-1]),"valid claim could not complete")
                n+=1
        return n
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        completed=sum(pool.map(work,range(workers)))
    elapsed=time.perf_counter()-start
    with psycopg.connect(db) as conn:
        done,attempts=conn.execute("SELECT count(*),coalesce(sum(attempts),0) FROM jobs WHERE status='done'").fetchone()
        check(done==count and completed==count and attempts==count,"missing or duplicate claims")
        # Failure simulation: expire a claimed lease and reclaim it; old token must be fenced.
        conn.execute("INSERT INTO jobs(kind,payload) VALUES ('sum',%s)",(Jsonb({"numbers":[1]}),))
        first=claim(conn);check(first is not None,"failed to claim recovery job")
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s",(first[0],))
        second=claim(conn)
        check(second is not None and second[0]==first[0] and second[-1]!=first[-1],"lease recovery failed")
        check(not complete(conn,first[0],first[-1]),"stale worker could complete job")
        check(complete(conn,second[0],second[-1]),"new owner could not complete recovered job")
        recovery=conn.execute("SELECT status,attempts FROM jobs WHERE id=%s",(first[0],)).fetchone()
        check(recovery==("done",2),"recovery status or attempt count wrong")
    return {"jobs_enqueued":count,"jobs_completed":done,"concurrent_workers":workers,
            "elapsed_seconds":round(elapsed,3),"jobs_per_second":round(count/elapsed,2),
            "duplicate_claims":attempts-done,"expired_lease_reclaimed":True,
            "stale_claim_rejected":True,"recovered_job_attempts":2,
            "failure_mode":"simulated lease expiry; not an OS-level worker kill"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger-url",default="http://127.0.0.1:8001")
    p.add_argument("--ledger-db",required=True)
    p.add_argument("--scheduler-db",required=True)
    p.add_argument("--transfers",type=int,default=100)
    p.add_argument("--clients",type=int,default=10)
    p.add_argument("--jobs",type=int,default=100)
    p.add_argument("--workers",type=int,default=10)
    p.add_argument("--output",default="benchmark-results.json")
    args=p.parse_args()
    check(min(args.transfers,args.clients,args.jobs,args.workers)>0,"positive workloads required")
    report={"scope":"disposable PostgreSQL 16; synthetic workload; no production claims",
            "ledger":ledger(args.ledger_url,args.ledger_db,args.transfers,args.clients),
            "scheduler":scheduler(args.scheduler_db,args.jobs,args.workers)}
    with open(args.output,"w") as f: json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))

if __name__=="__main__": main()
