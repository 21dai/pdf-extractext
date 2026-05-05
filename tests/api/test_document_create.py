"""Tests for document creation endpoints."""

from fastapi.testclient import TestClient

from app.config import settings
from tests.support.pdf import (
    DEFAULT_PDF_TEXT,
    MINIMAL_PDF_BYTES,
    build_pdf_bytes,
    create_upload_payload,
    pdf_checksum,
)


def test_create_document(client: TestClient):
    """Test creating a document from an uploaded PDF."""
    data, files = create_upload_payload()
    response = client.post("/api/v1/documents", data=data, files=files)
    assert response.status_code == 201

    document = response.json()
    assert document["name"] == "Test Document"
    assert document["original_filename"] == "test.pdf"
    assert document["checksum"] == pdf_checksum()
    assert document["file_size"] == len(MINIMAL_PDF_BYTES)
    assert document["is_processed"] is True
    assert document["extracted_text"] == DEFAULT_PDF_TEXT
    assert "file_path" not in document
    assert "id" in document


def test_create_document_rejects_non_pdf_extension(client: TestClient):
    """Test rejecting files that do not have a .pdf extension."""
    data, files = create_upload_payload(
        name="Invalid Document",
        filename="test.txt",
        content=b"not a pdf",
        content_type="text/plain",
    )

    response = client.post("/api/v1/documents", data=data, files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "Solo se permiten archivos PDF"


def test_create_document_rejects_invalid_pdf_content(client: TestClient):
    """Test rejecting files that end in .pdf but do not have a PDF signature."""
    data, files = create_upload_payload(
        name="Invalid PDF",
        filename="fake.pdf",
        content=b"this is not a pdf",
    )

    response = client.post("/api/v1/documents", data=data, files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "Archivo PDF invalido"


def test_create_document_rejects_blank_name(client: TestClient):
    """Test rejecting uploads without a valid document name."""
    data, files = create_upload_payload(name="   ")
    response = client.post("/api/v1/documents", data=data, files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "El nombre del documento es obligatorio"


def test_create_document_rejects_oversized_pdf(client: TestClient, monkeypatch):
    """Test rejecting PDFs that exceed the configured size limit."""
    monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)
    data, files = create_upload_payload(name="Too Large")

    response = client.post("/api/v1/documents", data=data, files=files)
    assert response.status_code == 400
    assert "El PDF supera el tamano maximo permitido" in response.json()["detail"]


def test_create_document_rejects_duplicate_checksum(client: TestClient):
    """Test rejecting PDFs with the same content but a different filename."""
    first_data, first_files = create_upload_payload(
        name="Original",
        filename="original.pdf",
    )
    second_data, second_files = create_upload_payload(
        name="Duplicate",
        filename="duplicate.pdf",
    )

    first_response = client.post("/api/v1/documents", data=first_data, files=first_files)
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/documents", data=second_data, files=second_files
    )
    assert second_response.status_code == 400
    assert (
        second_response.json()["detail"]
        == "Ya existe un documento con el mismo checksum"
    )


def test_create_document_allows_same_filename_with_different_content(client: TestClient):
    """Test allowing repeated original filenames when content changes."""
    first_data, first_files = create_upload_payload(
        name="Version One",
        filename="same.pdf",
        content=build_pdf_bytes("Version one"),
    )
    second_data, second_files = create_upload_payload(
        name="Version Two",
        filename="same.pdf",
        content=build_pdf_bytes("Version two"),
    )

    first_response = client.post("/api/v1/documents", data=first_data, files=first_files)
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/documents", data=second_data, files=second_files
    )
    assert second_response.status_code == 201
    assert second_response.json()["checksum"] != first_response.json()["checksum"]
