"""Tests for document extraction endpoints."""

from fastapi.testclient import TestClient

from tests.support.pdf import build_pdf_bytes, create_upload_payload


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
