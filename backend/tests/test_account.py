from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_delete_song_requires_authentication():
    response = client.delete("/api/v1/library/songs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401

