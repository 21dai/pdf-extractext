"""Tests for document endpoints"""

import hashlib
from pathlib import Path

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


def create_pdf_file(tmp_path, name: str = "test.pdf", content: bytes = MINIMAL_PDF_BYTES):
    """Create a minimal PDF-like test file and return its path."""
    test_file = tmp_path / name
    test_file.write_bytes(content)
    return test_file


def pdf_checksum(content: bytes = MINIMAL_PDF_BYTES) -> str:
    """Return the expected SHA-256 checksum for the given PDF bytes."""
    return hashlib.sha256(content).hexdigest()


def test_list_documents_empty(client: TestClient):
    """Test listing documents when empty"""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_create_document(client: TestClient, tmp_path):
    """Test creating a document"""
    test_file = create_pdf_file(tmp_path)

    payload = {
        "name": "Test Document",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test Document"
    assert data["checksum"] == pdf_checksum()
    assert data["is_processed"] is False
    assert "id" in data


def test_get_document(client: TestClient, tmp_path):
    """Test getting a document by ID"""
    test_file = create_pdf_file(tmp_path)

    payload = {
        "name": "Test Document",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    # Get the document
    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == document_id
    assert data["name"] == "Test Document"
    assert data["checksum"] == pdf_checksum()


def test_get_nonexistent_document(client: TestClient):
    """Test getting a non-existent document"""
    response = client.get("/api/v1/documents/999")
    assert response.status_code == 404


def test_update_document(client: TestClient, tmp_path):
    """Test updating a document"""
    test_file = create_pdf_file(tmp_path)

    payload = {
        "name": "Test Document",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    # Update the document
    update_payload = {"name": "Updated Document"}
    response = client.put(f"/api/v1/documents/{document_id}", json=update_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Updated Document"


def test_delete_document(client: TestClient, tmp_path):
    """Test deleting a document"""
    test_file = create_pdf_file(tmp_path)

    payload = {
        "name": "Test Document",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    # Delete the document
    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404


def test_create_document_rejects_non_pdf_extension(client: TestClient, tmp_path):
    """Test rejecting files that do not have a .pdf extension."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a pdf")

    payload = {
        "name": "Invalid Document",
        "file_path": str(test_file),
        "file_size": test_file.stat().st_size,
    }

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


def test_create_document_rejects_invalid_pdf_content(client: TestClient, tmp_path):
    """Test rejecting files that end in .pdf but do not have a PDF signature."""
    test_file = tmp_path / "fake.pdf"
    test_file.write_text("this is not a pdf")

    payload = {
        "name": "Invalid PDF",
        "file_path": str(test_file),
        "file_size": test_file.stat().st_size,
    }

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid PDF file"


def test_create_document_rejects_file_size_mismatch(client: TestClient, tmp_path):
    """Test rejecting payloads whose file_size does not match the file on disk."""
    test_file = create_pdf_file(tmp_path)

    payload = {
        "name": "Wrong Size",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES) + 1,
    }

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 400
    assert "File size mismatch" in response.json()["detail"]


def test_create_document_rejects_oversized_pdf(client: TestClient, tmp_path, monkeypatch):
    """Test rejecting PDFs that exceed the configured size limit."""
    test_file = create_pdf_file(tmp_path)
    monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)

    payload = {
        "name": "Too Large",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 400
    assert "PDF exceeds maximum allowed size" in response.json()["detail"]


def test_create_document_rejects_duplicate_checksum(client: TestClient, tmp_path):
    """Test rejecting PDFs with the same content but a different file path."""
    original_file = create_pdf_file(tmp_path, name="original.pdf")
    duplicate_file = create_pdf_file(tmp_path, name="duplicate.pdf")

    first_payload = {
        "name": "Original",
        "file_path": str(original_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }
    second_payload = {
        "name": "Duplicate",
        "file_path": str(duplicate_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }

    first_response = client.post("/api/v1/documents", json=first_payload)
    assert first_response.status_code == 201

    second_response = client.post("/api/v1/documents", json=second_payload)
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Document with the same checksum already exists"


def test_create_document_rejects_duplicate_file_path(client: TestClient, tmp_path):
    """Test rejecting reuse of the same file path when content changes."""
    test_file = create_pdf_file(tmp_path)
    first_payload = {
        "name": "Original",
        "file_path": str(test_file),
        "file_size": len(MINIMAL_PDF_BYTES),
    }

    first_response = client.post("/api/v1/documents", json=first_payload)
    assert first_response.status_code == 201

    updated_content = MINIMAL_PDF_BYTES + b"\n%changed"
    test_file.write_bytes(updated_content)

    second_payload = {
        "name": "Changed Path Reuse",
        "file_path": str(test_file),
        "file_size": len(updated_content),
    }

    second_response = client.post("/api/v1/documents", json=second_payload)
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Document with this file path already exists"


def test_extract_document_text(client: TestClient, tmp_path):
    """Test extracting real text from a stored PDF."""
    extracted_text = "Hello PDF extraction"
    pdf_bytes = build_pdf_bytes(extracted_text)
    test_file = create_pdf_file(tmp_path, content=pdf_bytes)

    payload = {
        "name": "Extractable Document",
        "file_path": str(test_file),
        "file_size": len(pdf_bytes),
    }
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == document_id
    assert data["is_processed"] is True
    assert data["extracted_text"] == extracted_text


def test_extract_document_rejects_changed_file_content(client: TestClient, tmp_path):
    """Test rejecting extraction if the file content changes after registration."""
    original_bytes = build_pdf_bytes("Original content")
    test_file = create_pdf_file(tmp_path, content=original_bytes)

    payload = {
        "name": "Mutable Document",
        "file_path": str(test_file),
        "file_size": len(original_bytes),
    }
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    changed_bytes = build_pdf_bytes("Changed content!")
    assert len(changed_bytes) == len(original_bytes)
    Path(test_file).write_bytes(changed_bytes)

    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 400
    assert response.json()["detail"] == "Document file no longer matches the stored checksum"
