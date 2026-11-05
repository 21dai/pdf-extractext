"""The service is a pure extractor: POST /extract and nothing that stores.

Since 2.0.0 (ADR-0008) there is no CRUD and no MongoDB: documents are stored by
document-store, through the orchestrator. The infrastructure stack may still
pass the old database variables, so the service must start and extract with
them present and pointing to nothing.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.support.pdf import MINIMAL_PDF_BYTES

# Un puerto donde no hay nada escuchando: si la app intentara usar una base,
# fallaria al arrancar o en el primer request.
UNREACHABLE_DATABASE_URL = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200"

# Las que todavia le pasa el compose de infrastructure (issue #31).
LEFTOVER_DATABASE_ENV = {
    "DATABASE_URL": UNREACHABLE_DATABASE_URL,
    "DATABASE_NAME": "pdf_extract",
    "DATABASE_TIMEOUT_MS": "3000",
    "DOCUMENTS_API_ENABLED": "true",
}


def extract(client: TestClient):
    return client.post(
        "/extract",
        content=MINIMAL_PDF_BYTES,
        headers={"Content-Type": "application/pdf"},
    )


@pytest.fixture
def client_with_leftover_database_env(monkeypatch: pytest.MonkeyPatch):
    """App started with the old database variables, pointing to nothing."""
    for name, value in LEFTOVER_DATABASE_ENV.items():
        monkeypatch.setenv(name, value)

    with TestClient(create_app()) as client:
        yield client


def test_starts_and_extracts_without_database_variables(client: TestClient):
    response = extract(client)

    assert response.status_code == 200
    assert response.json()["page_count"] == 1


def test_starts_and_extracts_with_an_unreachable_database_url(
    client_with_leftover_database_env: TestClient,
):
    response = extract(client_with_leftover_database_env)

    assert response.status_code == 200
    assert response.json()["page_count"] == 1
    assert client_with_leftover_database_env.get("/ready").status_code == 200


def test_leftover_database_variables_are_ignored(monkeypatch: pytest.MonkeyPatch):
    for name, value in LEFTOVER_DATABASE_ENV.items():
        monkeypatch.setenv(name, value)

    settings = Settings(_env_file=None)

    assert not hasattr(settings, "database_url")
    assert not hasattr(settings, "documents_api_enabled")


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "path", ["/api/v1/documents", "/api/v1/documents/1", "/documents"]
)
def test_the_documents_crud_does_not_exist(client: TestClient, method: str, path: str):
    response = getattr(client, method)(path)

    assert response.status_code == 404


def test_openapi_only_documents_extraction(client: TestClient):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/extract" in paths
    assert not [path for path in paths if "documents" in path]
