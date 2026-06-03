"""Tests for document summary endpoint."""

from fastapi.testclient import TestClient

from app.api.routers.document import get_summary_service
from app.config import settings
from tests.support.api_documents import DOCUMENTS_PATH, create_document_body
from tests.support.pdf import build_pdf_bytes


class FakeSummaryService:
    """Test double that avoids calling a real Ollama server."""

    model = "fake-ollama-model"

    def __init__(self, summary: str = "Resumen generado para pruebas"):
        self.summary = summary
        self.received_text = ""

    def summarize(self, text: str) -> str:
        self.received_text = text
        return self.summary


def test_summary_requires_api_key(client: TestClient, monkeypatch):
    """Test rejecting summary requests without the X-API-Key header."""
    monkeypatch.setattr(settings, "app_api_key", "test-secret")
    document = create_document_body(client)

    response = client.post(f"{DOCUMENTS_PATH}/{document['id']}/summary")

    assert response.status_code == 401
    assert response.json()["detail"] == "Se requiere X-API-Key"


def test_summary_rejects_invalid_api_key(client: TestClient, monkeypatch):
    """Test rejecting summary requests with an invalid API key."""
    monkeypatch.setattr(settings, "app_api_key", "test-secret")
    document = create_document_body(client)

    response = client.post(
        f"{DOCUMENTS_PATH}/{document['id']}/summary",
        headers={"X-API-Key": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "X-API-Key invalida"


def test_summary_returns_generated_summary(client: TestClient, monkeypatch):
    """Test generating a summary from the stored extracted text."""
    monkeypatch.setattr(settings, "app_api_key", "test-secret")
    fake_summary_service = FakeSummaryService("Resumen breve del documento")
    client.app.dependency_overrides[get_summary_service] = (
        lambda: fake_summary_service
    )

    try:
        document_text = "Texto principal del PDF"
        document = create_document_body(
            client,
            content=build_pdf_bytes(document_text),
        )

        response = client.post(
            f"{DOCUMENTS_PATH}/{document['id']}/summary",
            headers={"X-API-Key": "test-secret"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200

    response_body = response.json()
    assert response_body["document_id"] == document["id"]
    assert response_body["model"] == "fake-ollama-model"
    assert response_body["summary"] == "Resumen breve del documento"
    assert response_body["source_text_length"] == len(document_text)
    assert fake_summary_service.received_text == document_text


def test_summary_returns_not_found_for_missing_document(
    client: TestClient, monkeypatch
):
    """Test summary endpoint returns 404 when the document does not exist."""
    monkeypatch.setattr(settings, "app_api_key", "test-secret")

    response = client.post(
        f"{DOCUMENTS_PATH}/999/summary",
        headers={"X-API-Key": "test-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Documento 999 no encontrado"


def test_summary_rejects_document_without_extracted_text(
    client: TestClient, monkeypatch
):
    """Test summary endpoint rejects documents without extracted text."""
    monkeypatch.setattr(settings, "app_api_key", "test-secret")
    document = create_document_body(
        client,
        name="Blank PDF",
        content=build_pdf_bytes("   "),
    )

    response = client.post(
        f"{DOCUMENTS_PATH}/{document['id']}/summary",
        headers={"X-API-Key": "test-secret"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El documento no tiene texto extraido para resumir"
