from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_support_history_requires_authentication():
    assert client.get("/api/v1/support/requests").status_code == 401


def test_support_submission_requires_authentication():
    response = client.post(
        "/api/v1/support/requests",
        json={"category": "song", "subject": "Song failed", "message": "The song stopped during processing."},
    )
    assert response.status_code == 401

