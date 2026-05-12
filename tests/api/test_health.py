"""Tests for application health endpoints."""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok_status_and_database_name(client: TestClient):
    """Test the health endpoint returns the expected status and database name."""
    response = client.get("/health")

    assert response.status_code == 200

    health_data = response.json()
    assert health_data["status"] == "ok"
    assert health_data["database"] == "mongodb"
