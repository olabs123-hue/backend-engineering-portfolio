import os
import pytest
from fastapi.testclient import TestClient
from app.main import app,require_api_key
def test_auth_required():
    client=TestClient(app)
    assert client.get("/jobs/1").status_code in (401,503)
def test_auth_valid(monkeypatch):
    monkeypatch.setenv("SCHEDULER_API_KEY","a"*40)
    assert TestClient(app).get("/jobs/1").status_code==401
    assert TestClient(app).post("/jobs",json={"kind":"sum","payload":{"numbers":[1,2]} }).status_code==401
