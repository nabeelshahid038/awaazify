from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_voices_require_bearer_token():
    response = client.get("/api/v1/voices")
    assert response.status_code == 401


def test_song_library_requires_bearer_token():
    response = client.get("/api/v1/library/songs")
    assert response.status_code == 401
