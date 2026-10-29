import os
import subprocess
import time
import psycopg
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation
from .auth import hash_password, check_password, token_for, current_user

DB = os.getenv("DATABASE_URL", "postgresql://demo:demo@localhost:5432/ledger")
app = FastAPI(title="Authenticated Transactional Ledger")
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (id BIGSERIAL PRIMARY KEY, owner TEXT NOT NULL, balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0), opening_balance BIGINT NOT NULL DEFAULT 0 CHECK (opening_balance >= 0), user_id BIGINT REFERENCES users(id));
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS opening_balance BIGINT;
CREATE TABLE IF NOT EXISTS transfers (id BIGSERIAL PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, from_id BIGINT NOT NULL REFERENCES accounts(id), to_id BIGINT NOT NULL REFERENCES accounts(id), amount BIGINT NOT NULL CHECK (amount > 0), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS journal (id BIGSERIAL PRIMARY KEY, transfer_id BIGINT NOT NULL REFERENCES transfers(id), account_id BIGINT NOT NULL REFERENCES accounts(id), amount BIGINT NOT NULL CHECK (amount <> 0));
"""
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=256)
class AccountIn(BaseModel):
    owner: str = Field(min_length=1, max_length=120)
    opening_balance: int = Field(default=0, ge=0, le=10**12)
class TransferIn(BaseModel):
    from_id: int = Field(gt=0)
    to_id: int = Field(gt=0)
    amount: int = Field(gt=0, le=10**12)
    idempotency_key: str = Field(min_length=8, max_length=120)

def validate_legs(legs: list[int], executable="/usr/local/bin/journal") -> bool:
    payload = str(len(legs)) + "\n" + "\n".join(map(str, legs)) + "\n"
    try:
        result = subprocess.run([executable], input=payload, text=True, capture_output=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503, "journal validator unavailable") from exc
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
    try:
        with psycopg.connect(DB) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as exc:
        raise HTTPException(503, "database unavailable") from exc
    return {"ok": True}

@app.post("/auth/register", status_code=201)
def register(body: RegisterIn):
    try:
        with psycopg.connect(DB) as conn:
            row = conn.execute("INSERT INTO users(username,password_hash) VALUES (%s,%s) RETURNING id", (body.username, hash_password(body.password))).fetchone()
        return {"id": row[0], "username": body.username}
    except UniqueViolation as exc:
        raise HTTPException(409, "username already exists") from exc
    except psycopg.Error as exc:
        raise HTTPException(503, "database unavailable") from exc

@app.post("/auth/login")
def login(body: RegisterIn):
    try:
        with psycopg.connect(DB) as conn:
            row = conn.execute("SELECT id,password_hash FROM users WHERE username=%s", (body.username,)).fetchone()
    except psycopg.Error as exc:
        raise HTTPException(503, "database unavailable") from exc
    if not row or not check_password(row[1], body.password):
        raise HTTPException(401, "invalid credentials")
    return {"access_token": token_for(row[0]), "token_type": "bearer"}

@app.post("/accounts", status_code=201)
def create_account(body: AccountIn, user_id: int = Depends(current_user)):
    try:
        with psycopg.connect(DB) as conn:
            row = conn.execute("INSERT INTO accounts(owner,balance,opening_balance,user_id) VALUES (%s,%s,%s,%s) RETURNING id,balance", (body.owner, body.opening_balance, body.opening_balance, user_id)).fetchone()
        return {"id": row[0], "balance": row[1]}
    except psycopg.Error as exc:
        raise HTTPException(503, "database unavailable") from exc

@app.get("/accounts/{account_id}")
def get_account(account_id: int, user_id: int = Depends(current_user)):
    with psycopg.connect(DB) as conn:
        row = conn.execute("SELECT id,owner,balance FROM accounts WHERE id=%s AND user_id=%s", (account_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "account not found")
    return {"id": row[0], "owner": row[1], "balance": row[2]}

@app.post("/transfers", status_code=201)
def transfer(body: TransferIn, user_id: int = Depends(current_user)):
    if body.from_id == body.to_id:
        raise HTTPException(422, "distinct accounts required")
    if not validate_legs([-body.amount, body.amount]):
        raise HTTPException(500, "journal validation failed")
    try:
        with psycopg.connect(DB) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (body.idempotency_key,))
                existing = conn.execute("SELECT id,from_id,to_id,amount FROM transfers WHERE idempotency_key=%s", (body.idempotency_key,)).fetchone()
                if existing:
                    owned = conn.execute("SELECT 1 FROM accounts WHERE id=%s AND user_id=%s", (body.from_id, user_id)).fetchone()
                    if not owned:
                        raise HTTPException(404, "source account not found")
                    if existing[1:] != (body.from_id, body.to_id, body.amount):
                        raise HTTPException(409, "idempotency key reused with different payload")
                    return {"id": existing[0], "replayed": True}
                ids = sorted((body.from_id, body.to_id))
                rows = conn.execute("SELECT id,balance,user_id FROM accounts WHERE id=ANY(%s) ORDER BY id FOR UPDATE", (ids,)).fetchall()
                if len(rows) != 2:
                    raise HTTPException(404, "account not found")
                accounts = {r[0]: r for r in rows}
                if accounts[body.from_id][2] != user_id:
                    raise HTTPException(404, "source account not found")
                if accounts[body.from_id][1] < body.amount:
                    raise HTTPException(409, "insufficient funds")
                if accounts[body.to_id][1] + body.amount > 9223372036854775807:
                    raise HTTPException(422, "balance overflow")
                conn.execute("UPDATE accounts SET balance=balance-%s WHERE id=%s", (body.amount, body.from_id))
                conn.execute("UPDATE accounts SET balance=balance+%s WHERE id=%s", (body.amount, body.to_id))
                transfer_id = conn.execute("INSERT INTO transfers(idempotency_key,from_id,to_id,amount) VALUES (%s,%s,%s,%s) RETURNING id", (body.idempotency_key, body.from_id, body.to_id, body.amount)).fetchone()[0]
                conn.execute("INSERT INTO journal(transfer_id,account_id,amount) VALUES (%s,%s,%s),(%s,%s,%s)", (transfer_id, body.from_id, -body.amount, transfer_id, body.to_id, body.amount))
                return {"id": transfer_id, "replayed": False}
    except psycopg.Error as exc:
        raise HTTPException(503, "database transaction failed") from exc

@app.get("/reconcile")
def reconcile(user_id: int = Depends(current_user)):
    with psycopg.connect(DB) as conn:
        rows = conn.execute("""SELECT t.id FROM transfers t JOIN accounts a ON a.id=t.from_id
            LEFT JOIN journal j ON j.transfer_id=t.id WHERE a.user_id=%s
            GROUP BY t.id HAVING COUNT(j.id)<>2 OR COALESCE(SUM(j.amount),0)<>0""", (user_id,)).fetchall()
        mismatches = conn.execute("""SELECT a.id FROM accounts a LEFT JOIN journal j ON j.account_id=a.id
            WHERE a.user_id=%s GROUP BY a.id,a.balance,a.opening_balance
            HAVING a.opening_balance IS NULL OR a.balance <> a.opening_balance+COALESCE(SUM(j.amount),0)""", (user_id,)).fetchall()
    return {"balanced": not rows and not mismatches, "unbalanced_transfer_ids": [r[0] for r in rows], "balance_mismatch_account_ids": [r[0] for r in mismatches]}
