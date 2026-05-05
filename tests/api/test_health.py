"""Tests for application health endpoints."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Test application health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "mongodb"
