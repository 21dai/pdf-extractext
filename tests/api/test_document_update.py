"""Tests for document update endpoints."""

from fastapi.testclient import TestClient

from tests.support.api_documents import create_document_body


def test_update_document_returns_document_with_updated_name(client: TestClient):
    """Test updating a document returns the document with the updated name."""
    created_document = create_document_body(client)
    document_id = created_document["id"]

    update_payload = {"name": "Updated Document"}
    response = client.put(f"/api/v1/documents/{document_id}", json=update_payload)

    assert response.status_code == 200

    updated_document = response.json()
    assert updated_document["name"] == "Updated Document"


def test_update_document_rejects_blank_name(client: TestClient):
    """Test rejecting blank names during update."""
    created_document = create_document_body(client)
    document_id = created_document["id"]

    response = client.put(f"/api/v1/documents/{document_id}", json={"name": "   "})

    assert response.status_code == 400

    error_body = response.json()
    assert error_body["detail"] == "El nombre del documento es obligatorio"
