import os
import subprocess
import time

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB = os.getenv("DATABASE_URL", "postgresql://demo:demo@localhost:5432/ledger")
app = FastAPI(title="Transactional Ledger Demo")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id BIGSERIAL PRIMARY KEY, owner TEXT NOT NULL,
  balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0)
);
CREATE TABLE IF NOT EXISTS transfers (
  id BIGSERIAL PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
  from_id BIGINT NOT NULL REFERENCES accounts(id),
  to_id BIGINT NOT NULL REFERENCES accounts(id),
  amount BIGINT NOT NULL CHECK (amount > 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS journal (
  id BIGSERIAL PRIMARY KEY, transfer_id BIGINT NOT NULL REFERENCES transfers(id),
  account_id BIGINT NOT NULL REFERENCES accounts(id), amount BIGINT NOT NULL CHECK (amount <> 0)
);
"""

class AccountIn(BaseModel):
    owner: str = Field(min_length=1, max_length=120)
    opening_balance: int = Field(default=0, ge=0, le=10**12)

class TransferIn(BaseModel):
    from_id: int = Field(gt=0)
    to_id: int = Field(gt=0)
    amount: int = Field(gt=0, le=10**12)
    idempotency_key: str = Field(min_length=8, max_length=120)


def validate_legs(legs: list[int], executable: str = "/usr/local/bin/journal") -> bool:
    payload = str(len(legs)) + "\n" + "\n".join(map(str, legs)) + "\n"
    try:
        result = subprocess.run([executable], input=payload, text=True,
                                capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("C++ journal validator unavailable") from exc
    return result.returncode == 0

@app.on_event("startup")
def setup():
    for _ in range(30):
        try:
            with psycopg.connect(DB) as conn:
                conn.execute(SCHEMA, prepare=False)
            return
        except psycopg.OperationalError:
            time.sleep(1)
    raise RuntimeError("database unavailable")

@app.get("/health")
def health():
    with psycopg.connect(DB) as conn:
        conn.execute("SELECT 1")
    return {"ok": True}

@app.post("/accounts", status_code=201)
def create_account(body: AccountIn):
    with psycopg.connect(DB) as conn:
        row = conn.execute("INSERT INTO accounts(owner,balance) VALUES (%s,%s) RETURNING id,balance",
                           (body.owner, body.opening_balance)).fetchone()
        return {"id": row[0], "balance": row[1]}

@app.get("/accounts/{account_id}")
def get_account(account_id: int):
    with psycopg.connect(DB) as conn:
        row = conn.execute("SELECT id,owner,balance FROM accounts WHERE id=%s", (account_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "account not found")
        return {"id": row[0], "owner": row[1], "balance": row[2]}

@app.post("/transfers", status_code=201)
def transfer(body: TransferIn):
    if body.from_id == body.to_id:
        raise HTTPException(422, "distinct accounts required")
    if not validate_legs([-body.amount, body.amount]):
        raise HTTPException(500, "journal validation failed")
    # SERIALIZABLE is not needed for the locked two-account invariant;
    # idempotency is serialized by a unique key in transfers.
    try:
        with psycopg.connect(DB) as conn:
            with conn.transaction():
                # Advisory transaction lock serializes concurrent requests for the same key.
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (body.idempotency_key,))
                existing = conn.execute("SELECT id,from_id,to_id,amount FROM transfers WHERE idempotency_key=%s",
                                        (body.idempotency_key,)).fetchone()
                if existing:
                    if existing[1:] != (body.from_id, body.to_id, body.amount):
                        raise HTTPException(409, "idempotency key reused with different payload")
                    return {"id": existing[0], "replayed": True}
                # Lock in ascending ID order to avoid deadlock on opposite-direction transfers.
                ids = sorted([body.from_id, body.to_id])
                rows = conn.execute("SELECT id,balance FROM accounts WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (ids,)).fetchall()
                if len(rows) != 2:
                    raise HTTPException(404, "account not found")
                balances = dict(rows)
                if balances[body.from_id] < body.amount:
                    raise HTTPException(409, "insufficient funds")
                new_source = balances[body.from_id] - body.amount
                new_target = balances[body.to_id] + body.amount
                if new_target > 9223372036854775807:
                    raise HTTPException(422, "balance overflow")
                conn.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_source, body.from_id))
                conn.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_target, body.to_id))
                transfer_id = conn.execute("INSERT INTO transfers(idempotency_key,from_id,to_id,amount) VALUES (%s,%s,%s,%s) RETURNING id",
                                           (body.idempotency_key, body.from_id, body.to_id, body.amount)).fetchone()[0]
                conn.execute("INSERT INTO journal(transfer_id,account_id,amount) VALUES (%s,%s,%s),(%s,%s,%s)",
                             (transfer_id, body.from_id, -body.amount, transfer_id, body.to_id, body.amount))
                return {"id": transfer_id, "replayed": False}
    except psycopg.Error as exc:
        raise HTTPException(503, "database transaction failed") from exc

@app.get("/reconcile")
def reconcile():
    # Demo-only: opening balances are not journaled, so report transfer net only.
    with psycopg.connect(DB) as conn:
        unbalanced = conn.execute("SELECT transfer_id FROM journal GROUP BY transfer_id HAVING SUM(amount) <> 0").fetchall()
    return {"balanced": len(unbalanced) == 0, "unbalanced_transfer_ids": [r[0] for r in unbalanced]}
