from fastapi.testclient import TestClient
from app.main import app

def test_health():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "awaazify-api", "version": "0.11.0"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]


def test_readiness_fails_closed_without_production_configuration():
    response = TestClient(app).get("/api/v1/health/ready")
    assert response.status_code == 503
