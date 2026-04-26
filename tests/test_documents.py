"""Tests for document endpoints."""

import hashlib

from fastapi.testclient import TestClient

from app.config import settings


DEFAULT_PDF_TEXT = "Test Document Content"


def build_pdf_bytes(text: str = DEFAULT_PDF_TEXT) -> bytes:
    """Build a minimal valid single-page PDF containing the given text."""
    escaped_text = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    stream = f"BT\n/F1 18 Tf\n50 100 Td\n({escaped_text}) Tj\nET\n"
    stream_bytes = stream.encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("utf-8")
            + stream_bytes
            + b"endstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(f"{index} 0 obj\n".encode("utf-8"))
        pdf_bytes.extend(obj)
        pdf_bytes.extend(b"\nendobj\n")

    startxref = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    pdf_bytes.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    pdf_bytes.extend(
        (
            f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
            f"startxref\n{startxref}\n%%EOF\n"
        ).encode("utf-8")
    )

    return bytes(pdf_bytes)


MINIMAL_PDF_BYTES = build_pdf_bytes()


def pdf_checksum(content: bytes = MINIMAL_PDF_BYTES) -> str:
    """Return the expected SHA-256 checksum for the given PDF bytes."""
    return hashlib.sha256(content).hexdigest()


def create_upload_payload(
    name: str = "Test Document",
    filename: str = "test.pdf",
    content: bytes = MINIMAL_PDF_BYTES,
    content_type: str = "application/pdf",
):
    """Build multipart request data for document uploads."""
    return (
        {"name": name},
        {"file": (filename, content, content_type)},
    )


def test_list_documents_empty(client: TestClient):
    """Test listing documents when empty."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_health_endpoint(client: TestClient):
    """Test application health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "mongodb"


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


def test_get_document(client: TestClient):
    """Test getting a document by ID."""
    data, files = create_upload_payload()
    create_response = client.post("/api/v1/documents", data=data, files=files)
    document_id = create_response.json()["id"]

    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200

    document = response.json()
    assert document["id"] == document_id
    assert document["name"] == "Test Document"
    assert document["original_filename"] == "test.pdf"
    assert document["checksum"] == pdf_checksum()


def test_get_nonexistent_document(client: TestClient):
    """Test getting a non-existent document."""
    response = client.get("/api/v1/documents/999")
    assert response.status_code == 404


def test_update_document(client: TestClient):
    """Test updating a document."""
    data, files = create_upload_payload()
    create_response = client.post("/api/v1/documents", data=data, files=files)
    document_id = create_response.json()["id"]

    update_payload = {"name": "Updated Document"}
    response = client.put(f"/api/v1/documents/{document_id}", json=update_payload)
    assert response.status_code == 200

    document = response.json()
    assert document["name"] == "Updated Document"


def test_update_document_rejects_blank_name(client: TestClient):
    """Test rejecting blank names during update."""
    data, files = create_upload_payload()
    create_response = client.post("/api/v1/documents", data=data, files=files)
    document_id = create_response.json()["id"]

    response = client.put(f"/api/v1/documents/{document_id}", json={"name": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "El nombre del documento es obligatorio"


def test_delete_document(client: TestClient):
    """Test deleting a document."""
    data, files = create_upload_payload()
    create_response = client.post("/api/v1/documents", data=data, files=files)
    document = create_response.json()
    document_id = document["id"]

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 204

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404


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


def test_extract_document_text(client: TestClient):
    """Test returning extracted text for an in-memory processed PDF."""
    extracted_text = "Hello PDF extraction"
    pdf_bytes = build_pdf_bytes(extracted_text)
    data, files = create_upload_payload(
        name="Extractable Document",
        filename="extractable.pdf",
        content=pdf_bytes,
    )
    create_response = client.post("/api/v1/documents", data=data, files=files)
    created_document = create_response.json()
    document_id = create_response.json()["id"]
    assert created_document["is_processed"] is True
    assert created_document["extracted_text"] == extracted_text

    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 200

    document = response.json()
    assert document["id"] == document_id
    assert document["is_processed"] is True
    assert document["extracted_text"] == extracted_text


def test_extract_document_returns_stored_text_without_reprocessing(client: TestClient):
    """Test that extraction returns the stored in-memory result."""
    original_text = "Original content"
    original_bytes = build_pdf_bytes(original_text)
    data, files = create_upload_payload(
        name="Processed In Memory",
        filename="processed.pdf",
        content=original_bytes,
    )
    create_response = client.post("/api/v1/documents", data=data, files=files)
    document_id = create_response.json()["id"]

    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 200
    assert response.json()["extracted_text"] == original_text
