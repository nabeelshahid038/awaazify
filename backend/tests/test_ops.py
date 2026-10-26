from fastapi.testclient import TestClient

from app.main import app


def test_operations_dashboard_requires_authentication():
    assert TestClient(app).get("/api/v1/admin/ops").status_code == 401


def test_production_diagnostics_requires_authentication():
    assert TestClient(app).get("/api/v1/admin/diagnostics").status_code == 401
