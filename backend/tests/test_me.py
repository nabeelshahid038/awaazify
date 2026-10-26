from fastapi.testclient import TestClient
from app.main import app

def test_me_requires_bearer_token():
    r = TestClient(app).get("/api/v1/me")
    assert r.status_code == 401
