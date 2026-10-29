import os
import time
import hmac
import psycopg
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
DB=os.getenv("DATABASE_URL","postgresql://demo:demo@localhost:5432/jobs")
app=FastAPI(title="Durable Job Scheduler")
SCHEMA="""
CREATE TABLE IF NOT EXISTS jobs (
 id BIGSERIAL PRIMARY KEY, kind TEXT NOT NULL, payload JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','done','dead')),
 attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
 run_at TIMESTAMPTZ NOT NULL DEFAULT now(), lease_until TIMESTAMPTZ,
 last_error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), claim_token TEXT
);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS claim_token TEXT;
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status,run_at);
"""
def require_api_key(authorization: str | None = Header(default=None)):
    expected=os.getenv("SCHEDULER_API_KEY","")
    if len(expected)<32:
        raise HTTPException(503,"scheduler API key not configured")
    if not authorization or not authorization.startswith("Bearer ") or not hmac.compare_digest(authorization[7:],expected):
        raise HTTPException(401,"invalid API credential",headers={"WWW-Authenticate":"Bearer"})
class JobIn(BaseModel):
    kind: str=Field(pattern="^(sum|uppercase)$")
    payload: dict
    max_attempts: int=Field(default=3,ge=1,le=10)
    delay_seconds: int=Field(default=0,ge=0,le=86400)
@app.on_event("startup")
def setup():
    for _ in range(30):
        try:
            with psycopg.connect(DB) as conn: conn.execute(SCHEMA,prepare=False)
            return
        except psycopg.OperationalError: time.sleep(1)
    raise RuntimeError("database unavailable")
@app.get("/health")
def health():
    with psycopg.connect(DB) as conn: conn.execute("SELECT 1")
    return {"ok":True}
@app.post("/jobs",status_code=201)
def create_job(job:JobIn, _=Depends(require_api_key)):
    from psycopg.types.json import Jsonb
    with psycopg.connect(DB) as conn:
        row=conn.execute("INSERT INTO jobs(kind,payload,max_attempts,run_at) VALUES (%s,%s,%s,now()+%s*interval '1 second') RETURNING id",(job.kind,Jsonb(job.payload),job.max_attempts,job.delay_seconds)).fetchone()
    return {"id":row[0],"status":"pending"}
@app.get("/jobs/{job_id}")
def get_job(job_id:int, _=Depends(require_api_key)):
    with psycopg.connect(DB) as conn:
        row=conn.execute("SELECT id,kind,status,attempts,max_attempts,last_error FROM jobs WHERE id=%s",(job_id,)).fetchone()
    if row is None: raise HTTPException(404,"job not found")
    return dict(zip(("id","kind","status","attempts","max_attempts","last_error"),row))
