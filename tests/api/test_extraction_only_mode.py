"""Tests for running the service as a pure extractor, without MongoDB.

With DOCUMENTS_API_ENABLED=false the service only exposes POST /extract: it
starts without a database, so the TP replicas share no state and do not go
down when MongoDB does.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.utils.database import reset_client
from tests.support.pdf import MINIMAL_PDF_BYTES

# Un puerto donde no hay nada escuchando: si la app intentara usar MongoDB,
# fallaria al arrancar o en el primer request.
UNREACHABLE_DATABASE_URL = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200"


@pytest.fixture
def extraction_only_client(monkeypatch: pytest.MonkeyPatch):
    """Client for an app configured as extractor only, with no database reachable."""
    monkeypatch.setattr(settings, "documents_api_enabled", False)
    monkeypatch.setattr(settings, "database_url", UNREACHABLE_DATABASE_URL)
    reset_client()

    with TestClient(create_app()) as client:
        yield client

    reset_client()


def test_starts_and_extracts_without_a_database(extraction_only_client: TestClient):
    response = extraction_only_client.post(
        "/extract",
        content=MINIMAL_PDF_BYTES,
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 200
    assert response.json()["page_count"] == 1


def test_health_does_not_depend_on_the_database(extraction_only_client: TestClient):
    response = extraction_only_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documents_api_is_not_exposed(extraction_only_client: TestClient):
    assert extraction_only_client.get("/api/v1/documents").status_code == 404


def test_documents_api_is_enabled_by_default():
    assert settings.documents_api_enabled is True
