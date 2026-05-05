"""Tests for document read endpoints."""

from fastapi.testclient import TestClient

from tests.support.pdf import create_upload_payload, pdf_checksum


def test_list_documents_empty(client: TestClient):
    """Test listing documents when empty."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


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
