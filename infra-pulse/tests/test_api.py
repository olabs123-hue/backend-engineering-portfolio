import importlib
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INFRAPULSE_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("INFRAPULSE_INGEST_TOKEN", "test-token")
    import backend.app as module
    module = importlib.reload(module)
    with TestClient(module.app) as c:
        yield c

H={"X-Ingest-Token":"test-token"}

def test_auth_and_validation(client):
    assert client.post('/api/services',json={"name":"API"}).status_code==401
    assert client.post('/api/services',json={"name":"x"},headers=H).status_code==422
    assert client.get('/health').json()['status']=='ok'

def test_alert_lifecycle(client):
    res=client.post('/api/services',json={"name":"Payments", "latency_threshold_ms":100},headers=H)
    assert res.status_code==201
    sid=res.json()['id']
    assert client.post('/api/services',json={"name":"Payments"},headers=H).status_code==409
    r=client.post(f'/api/services/{sid}/samples',headers=H,json={"ok":False,"latency_ms":25})
    assert r.status_code==201
    assert len(client.get('/api/alerts').json())==1
    client.post(f'/api/services/{sid}/samples',headers=H,json={"ok":False,"latency_ms":20})
    assert len(client.get('/api/alerts').json())==1  # deduplicated active alert
    client.post(f'/api/services/{sid}/samples',headers=H,json={"ok":True,"latency_ms":200})
    assert len(client.get('/api/alerts').json())==1
    client.post(f'/api/services/{sid}/samples',headers=H,json={"ok":True,"latency_ms":50})
    assert client.get('/api/alerts').json()==[]
    assert client.get('/api/summary').json()=={"services":1,"healthy":1,"open_alerts":0,"samples":4}
    assert len(client.get(f'/api/services/{sid}/samples').json())==4
    assert len(client.get('/api/alerts?state=all').json())==1

def test_missing_and_bad_samples(client):
    assert client.post('/api/services/55/samples',headers=H,json={"ok":True,"latency_ms":2}).status_code==404
    assert client.post('/api/services/55/samples',headers=H,json={"ok":True,"latency_ms":-2}).status_code==422
    assert client.get('/api/services/55/samples').status_code==404
    assert client.get('/api/services').json()==[]
