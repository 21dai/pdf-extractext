"""Tests for the liveness (/health) and readiness (/ready) endpoints.

/health only says the process answers: Docker uses it, and a MongoDB outage
must not mark the replicas as unhealthy, because POST /extract does not need
the database. /ready also checks the dependencies of the full service.
"""

import pytest
from fastapi.testclient import TestClient

from app.utils.database import get_db


class BrokenDatabase:
    """Database whose ping always fails, like MongoDB being down."""

    def command(self, name: str):
        raise ConnectionError("MongoDB no responde")


@pytest.fixture
def client_with_database_down(client: TestClient):
    """Client whose requests see MongoDB as unreachable."""
    client.app.dependency_overrides[get_db] = lambda: BrokenDatabase()
    yield client
    client.app.dependency_overrides.clear()


def test_health_reports_the_process_is_alive(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_depend_on_the_database(client_with_database_down):
    assert client_with_database_down.get("/health").status_code == 200


def test_ready_reports_the_database(client: TestClient):
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "mongodb"


def test_ready_fails_when_the_database_is_down(client_with_database_down):
    response = client_with_database_down.get("/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
