from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_training_requests_require_authentication():
    assert client.get("/api/v1/voice-training").status_code == 401


def test_training_submission_requires_authentication():
    assert client.post("/api/v1/voice-training", json={}).status_code == 401


def test_admin_training_queue_requires_authentication():
    assert client.get("/api/v1/admin/voice-training").status_code == 401
