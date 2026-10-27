import subprocess
import time
import psycopg
from .main import DB, SCHEMA


def run_task(kind: str, payload: dict):
    if kind == "sum":
        numbers = payload.get("numbers")
        if not isinstance(numbers, list) or len(numbers) > 10000 or not all(type(x) in (int, float) for x in numbers):
            raise ValueError("numbers must be a numeric list of <=10000 entries")
        return sum(numbers)
    if kind == "uppercase":
        value = payload.get("text")
        if not isinstance(value, str) or len(value) > 10000:
            raise ValueError("text must be a string of <=10000 characters")
        return value.upper()
    raise ValueError("unsupported task kind")


def backoff(attempts: int, executable="/usr/local/bin/backoff") -> int:
    output = subprocess.run([executable, str(attempts)], capture_output=True, text=True, timeout=2, check=True)
    return int(output.stdout.strip())


def claim(conn):
    # Reclaim expired leases. Work is at-least-once, never exactly-once.
    with conn.transaction():
        row = conn.execute("""SELECT id,kind,payload,attempts,max_attempts FROM jobs
            WHERE (status='pending' AND run_at <= now())
               OR (status='running' AND lease_until < now())
            ORDER BY run_at,id FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not row:
            return None
        conn.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease_until=now()+interval '30 seconds' WHERE id=%s", (row[0],))
        return row


def main():
    while True:
        try:
            with psycopg.connect(DB) as conn:
                conn.execute(SCHEMA, prepare=False)
                row = claim(conn)
                if not row:
                    time.sleep(0.5)
                    continue
                job_id, kind, payload, previous_attempts, max_attempts = row
                attempts = previous_attempts + 1
                try:
                    run_task(kind, payload)
                    with conn.transaction():
                        conn.execute("UPDATE jobs SET status='done',lease_until=NULL WHERE id=%s AND status='running' AND attempts=%s", (job_id, attempts))
                except Exception as exc:
                    dead = attempts >= max_attempts
                    delay = 0 if dead else backoff(attempts)
                    with conn.transaction():
                        conn.execute("""UPDATE jobs SET status=%s,lease_until=NULL,
                            run_at=now() + %s * interval '1 second',last_error=%s
                            WHERE id=%s AND status='running' AND attempts=%s""",
                            ('dead' if dead else 'pending', delay, str(exc)[:500], job_id, attempts))
        except (psycopg.Error, OSError, subprocess.SubprocessError) as exc:
            print(f"worker retry: {exc}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
