"""Tests for document creation endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.support.api_documents import (
    assert_created_document,
    create_document_response,
)
from tests.support.pdf import MINIMAL_PDF_BYTES, build_pdf_bytes


def test_create_document_returns_processed_document(client: TestClient):
    """Test creating a document returns a processed document body."""
    response = create_document_response(client)

    assert response.status_code == 201

    created_document = response.json()
    assert_created_document(created_document)


def test_create_document_rejects_files_without_pdf_extension(client: TestClient):
    """Test creating a document rejects files without a .pdf extension."""
    response = create_document_response(
        client,
        name="Invalid Document",
        filename="test.txt",
        content=b"not a pdf",
        content_type="text/plain",
    )

    assert response.status_code == 400

    error_body = response.json()
    assert error_body["detail"] == "Solo se permiten archivos PDF"


def test_create_document_rejects_pdf_file_with_invalid_signature(client: TestClient):
    """Test creating a document rejects PDF filenames with invalid content."""
    response = create_document_response(
        client,
        name="Invalid PDF",
        filename="fake.pdf",
        content=b"this is not a pdf",
    )

    assert response.status_code == 400

    error_body = response.json()
    assert error_body["detail"] == "Archivo PDF invalido"


def test_create_document_rejects_blank_document_name(client: TestClient):
    """Test creating a document rejects blank document names."""
    response = create_document_response(client, name="   ")

    assert response.status_code == 400

    error_body = response.json()
    assert error_body["detail"] == "El nombre del documento es obligatorio"


def test_create_document_rejects_pdf_larger_than_configured_limit(db):
    """Test creating a document rejects PDFs above the configured size limit."""
    from app.api.routers.document import get_document_service
    from app.main import create_app
    from app.repositories import DocumentRepository
    from app.services import DocumentService

    # Set a custom limit that is smaller than the MINIMAL_PDF_BYTES
    custom_limit = len(MINIMAL_PDF_BYTES) - 1
    repository = DocumentRepository(db)
    app = create_app()

    def _override_service():
        return DocumentService(repository, max_pdf_size_bytes=custom_limit)

    app.dependency_overrides[get_document_service] = _override_service
    with TestClient(app) as client:
        response = create_document_response(client, name="Too Large")

        assert response.status_code == 413

        error_body = response.json()
        assert "El PDF supera el tamano maximo permitido" in error_body["detail"]


def test_create_document_rejects_duplicate_document_checksum(client: TestClient):
    """Test creating a document rejects a duplicate document checksum."""
    first_response = create_document_response(
        client,
        name="Original",
        filename="original.pdf",
    )
    second_response = create_document_response(
        client,
        name="Duplicate",
        filename="duplicate.pdf",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400

    error_body = second_response.json()
    assert error_body["detail"] == "Ya existe un documento con el mismo checksum"


def test_create_document_allows_same_filename_when_content_differs(
    client: TestClient,
):
    """Test creating documents allows the same filename when content differs."""
    first_response = create_document_response(
        client,
        name="Version One",
        filename="same.pdf",
        content=build_pdf_bytes("Version one"),
    )
    second_response = create_document_response(
        client,
        name="Version Two",
        filename="same.pdf",
        content=build_pdf_bytes("Version two"),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_document = first_response.json()
    second_document = second_response.json()
    assert second_document["checksum"] != first_document["checksum"]


STRESS_PDFS = Path(__file__).resolve().parents[1] / "stress" / "pdfs"


@pytest.mark.usefixtures("disk_forbidden")
def test_create_document_keeps_uploads_bigger_than_one_megabyte_in_memory(
    client: TestClient,
):
    """Requisito 8: el PDF no se escribe a disco mientras se procesa.

    Starlette pasa a un archivo temporal las partes de mas de 1 MB.
    """
    source = STRESS_PDFS / "scrum_manager_historias_usuario.pdf"  # 3,8 MB

    response = create_document_response(
        client, name="Grande", filename="grande.pdf", content=source.read_bytes()
    )

    assert response.status_code == 201


def test_create_document_rejects_declared_size_over_limit_before_reading(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """With Content-Length over the limit the upload is rejected with 413."""
    monkeypatch.setattr(settings, "max_pdf_size_bytes", 1024)
    big_pdf = build_pdf_bytes("x" * 10) + b"%" * 200_000

    response = create_document_response(client, name="Enorme", content=big_pdf)

    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"


def test_create_document_without_file_returns_422(client: TestClient):
    response = client.post("/api/v1/documents", data={"name": "Sin archivo"})

    assert response.status_code == 422


def test_create_document_without_name_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("a.pdf", MINIMAL_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 422
