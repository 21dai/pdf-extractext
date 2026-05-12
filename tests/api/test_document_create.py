"""Tests for document creation endpoints."""

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


def test_create_document_rejects_pdf_larger_than_configured_limit(
    client: TestClient, monkeypatch
):
    """Test creating a document rejects PDFs above the configured size limit."""
    monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)
    response = create_document_response(client, name="Too Large")

    assert response.status_code == 400

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
