import os
import uuid
import pytest
import psycopg
from fastapi.testclient import TestClient
from app import main as service
from app import worker

@pytest.fixture
def db(monkeypatch):
    url=os.getenv("TEST_DATABASE_URL")
    if not url: pytest.skip("TEST_DATABASE_URL not configured")
    monkeypatch.setattr(service,"DB",url)
    monkeypatch.setattr(worker,"DB",url)
    with psycopg.connect(url) as conn:
        conn.execute(service.SCHEMA,prepare=False)
    return url

def test_api_key(db,monkeypatch):
    monkeypatch.setenv("SCHEDULER_API_KEY","z"*40)
    with TestClient(service.app) as client:
        assert client.post("/jobs",json={"kind":"sum","payload":{"numbers":[1]}}).status_code==401
        response=client.post("/jobs",json={"kind":"sum","payload":{"numbers":[1]}},headers={"Authorization":"Bearer "+"z"*40})
        assert response.status_code==201

def test_claim_and_fencing(db):
    with psycopg.connect(db) as conn:
        job_id=conn.execute("INSERT INTO jobs(kind,payload,max_attempts) VALUES ('sum','{}',2) RETURNING id").fetchone()[0]
        first=worker.claim(conn)
        assert first[0]==job_id
        assert worker.claim(conn) is None
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s",(job_id,))
        second=worker.claim(conn)
        assert second[0]==job_id
        assert first[-1]!=second[-1]
        assert not worker.complete(conn,job_id,first[-1])
        assert worker.complete(conn,job_id,second[-1])

def test_reap_final_attempt(db):
    with psycopg.connect(db) as conn:
        job_id=conn.execute("""INSERT INTO jobs(kind,payload,status,attempts,max_attempts,lease_until,claim_token)
            VALUES ('sum','{}','running',1,1,now()-interval '1 second',%s) RETURNING id""",(uuid.uuid4().hex,)).fetchone()[0]
        assert worker.reap_exhausted(conn)>=1
        assert conn.execute("SELECT status FROM jobs WHERE id=%s",(job_id,)).fetchone()[0]=="dead"
