import os
import uuid
import pytest
import psycopg
from fastapi.testclient import TestClient
from app.main import app, SCHEMA
from app import main as service

@pytest.fixture
def client(monkeypatch):
    db=os.getenv("TEST_DATABASE_URL")
    if not db: pytest.skip("TEST_DATABASE_URL not configured")
    monkeypatch.setattr(service,"DB",db)
    with psycopg.connect(db) as conn:
        conn.execute(SCHEMA,prepare=False)
    with TestClient(app) as c:
        yield c

def auth(client):
    username="user_"+uuid.uuid4().hex
    password="a-long-test-password-123"
    assert client.post("/auth/register",json={"username":username,"password":password}).status_code==201
    token=client.post("/auth/login",json={"username":username,"password":password}).json()["access_token"]
    return {"Authorization":"Bearer "+token}

def test_requires_auth(client):
    assert client.post("/accounts",json={"owner":"A"}).status_code in (401,403)
    assert client.get("/reconcile").status_code in (401,403)

def test_account_ownership(client):
    first=auth(client)
    second=auth(client)
    response=client.post("/accounts",json={"owner":"A","opening_balance":100},headers=first)
    assert response.status_code==201
    account_id=response.json()["id"]
    assert client.get(f"/accounts/{account_id}",headers=first).status_code==200
    assert client.get(f"/accounts/{account_id}",headers=second).status_code==404

def test_transfer_atomicity_and_replay(client,monkeypatch):
    monkeypatch.setattr(service,"validate_legs",lambda legs: sum(legs)==0)
    headers=auth(client)
    a=client.post("/accounts",json={"owner":"A","opening_balance":100},headers=headers).json()["id"]
    b=client.post("/accounts",json={"owner":"B","opening_balance":0},headers=headers).json()["id"]
    body={"from_id":a,"to_id":b,"amount":40,"idempotency_key":uuid.uuid4().hex}
    assert client.post("/transfers",json=body,headers=headers).status_code==201
    replay=client.post("/transfers",json=body,headers=headers)
    assert replay.status_code==201 and replay.json()["replayed"]
    assert client.get(f"/accounts/{a}",headers=headers).json()["balance"]==60
    assert client.get(f"/accounts/{b}",headers=headers).json()["balance"]==40
    assert client.get("/reconcile",headers=headers).json()["balanced"]
    body["idempotency_key"]=uuid.uuid4().hex
    body["amount"]=1000
    assert client.post("/transfers",json=body,headers=headers).status_code==409
    assert client.get(f"/accounts/{a}",headers=headers).json()["balance"]==60
