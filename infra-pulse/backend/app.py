"""InfraPulse monitoring API. Development MVP, not a production observability platform."""
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.getenv("INFRAPULSE_DB", str(Path(__file__).resolve().parent / "infrapulse.sqlite3"))
INGEST_TOKEN = os.getenv("INFRAPULSE_INGEST_TOKEN", "")
app = FastAPI(title="InfraPulse API", version="0.1.0", description="Local infrastructure monitoring MVP")
origins = os.getenv("INFRAPULSE_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Ingest-Token"])

@contextmanager
def connection():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '', latency_threshold_ms INTEGER NOT NULL DEFAULT 500);
        CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL REFERENCES services(id), ok INTEGER NOT NULL, latency_ms REAL NOT NULL, collected_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_samples_service_time ON samples(service_id, id DESC);
        CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL REFERENCES services(id), level TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT);
        """)

@app.on_event("startup")
def startup():
    init_db()

class ServiceIn(BaseModel):
    name: str = Field(min_length=2, max_length=70, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]*$")
    description: str = Field(default="", max_length=240)
    latency_threshold_ms: int = Field(default=500, ge=1, le=60000)

class SampleIn(BaseModel):
    ok: bool
    latency_ms: float = Field(ge=0, le=120000)


def authorize_ingest(x_ingest_token: str | None = Header(default=None)):
    if not INGEST_TOKEN or not x_ingest_token or not secrets.compare_digest(x_ingest_token, INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="Ingestion token required")


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@app.get("/health")
def health():
    return {"status": "ok", "app": "InfraPulse"}

@app.get("/api/services")
def services():
    with connection() as db:
        rows = db.execute("SELECT * FROM services ORDER BY id").fetchall()
        data = []
        for row in rows:
            last = db.execute("SELECT ok,latency_ms,collected_at FROM samples WHERE service_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
            count = db.execute("SELECT COUNT(*) AS n FROM alerts WHERE service_id=? AND resolved_at IS NULL", (row["id"],)).fetchone()["n"]
            data.append({**dict(row), "latest": dict(last) if last else None, "open_alerts": count})
        return data

@app.post("/api/services", status_code=201, dependencies=[Depends(authorize_ingest)])
def create_service(item: ServiceIn):
    with connection() as db:
        try:
            cur = db.execute("INSERT INTO services (name,description,latency_threshold_ms) VALUES (?,?,?)", (item.name, item.description, item.latency_threshold_ms))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Service already exists")
        return {"id":cur.lastrowid, **item.model_dump()}

@app.post("/api/services/{service_id}/samples", status_code=201, dependencies=[Depends(authorize_ingest)])
def record_sample(service_id: int, sample: SampleIn):
    with connection() as db:
        service = db.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        now = iso_now()
        db.execute("INSERT INTO samples(service_id,ok,latency_ms,collected_at) VALUES (?,?,?,?)", (service_id, int(sample.ok), sample.latency_ms, now))
        problem = None if sample.ok and sample.latency_ms <= service["latency_threshold_ms"] else ("Service unavailable" if not sample.ok else "Latency threshold exceeded")
        existing = db.execute("SELECT id FROM alerts WHERE service_id=? AND resolved_at IS NULL", (service_id,)).fetchone()
        if problem and existing is None:
            db.execute("INSERT INTO alerts(service_id,level,message,created_at) VALUES (?,?,?,?)", (service_id, "critical" if not sample.ok else "warning", problem, now))
        elif not problem and existing:
            db.execute("UPDATE alerts SET resolved_at=? WHERE service_id=? AND resolved_at IS NULL", (now, service_id))
        return {"service_id": service_id, "ok":sample.ok, "latency_ms":sample.latency_ms, "alert":problem, "collected_at":now}

@app.get("/api/services/{service_id}/samples")
def service_samples(service_id: int, limit: int = 30):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be 1..200")
    with connection() as db:
        if not db.execute("SELECT id FROM services WHERE id=?", (service_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Service not found")
        return [dict(r) for r in db.execute("SELECT id, ok, latency_ms, collected_at FROM samples WHERE service_id=? ORDER BY id DESC LIMIT ?",(service_id,limit)).fetchall()][::-1]

@app.get("/api/alerts")
def alerts(state: Literal["open", "all"]="open"):
    with connection() as db:
        where = "WHERE a.resolved_at IS NULL" if state=="open" else ""
        return [dict(r) for r in db.execute(f"SELECT a.*, s.name AS service_name FROM alerts a JOIN services s ON a.service_id=s.id {where} ORDER BY a.id DESC LIMIT 100").fetchall()]

@app.get("/api/summary")
def summary():
    with connection() as db:
        total = db.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        open_alerts = db.execute("SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL").fetchone()[0]
        samples = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        healthy = db.execute("""SELECT COUNT(*) FROM services s WHERE
          (SELECT ok FROM samples WHERE service_id=s.id ORDER BY id DESC LIMIT 1)=1
          AND (SELECT latency_ms FROM samples WHERE service_id=s.id ORDER BY id DESC LIMIT 1)<=s.latency_threshold_ms""").fetchone()[0]
        return {"services":total,"healthy":healthy,"open_alerts":open_alerts,"samples":samples}
