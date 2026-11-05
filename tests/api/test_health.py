"""Tests for the liveness (/health) and readiness (/ready) endpoints.

The service has no external dependencies (no database, no other services):
both only say the process answers. Docker uses /health for the healthcheck.
"""

from fastapi.testclient import TestClient


def test_health_reports_the_process_is_alive(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_the_service_can_take_requests(client: TestClient):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_does_not_report_a_database(client: TestClient):
    body = client.get("/").json()

    assert body["version"]
    assert "database" not in body
    assert "database_name" not in body
