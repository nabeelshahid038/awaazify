from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_wallet_requires_authentication():
    assert client.get("/api/v1/wallet").status_code == 401


def test_payment_submission_requires_authentication():
    response = client.post("/api/v1/wallet/payment-requests", json={})
    assert response.status_code == 401


def test_admin_queue_requires_authentication():
    assert client.get("/api/v1/admin/payment-requests").status_code == 401
