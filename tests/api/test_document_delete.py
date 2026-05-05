"""Tests for document delete endpoints."""

from fastapi.testclient import TestClient

from tests.support.pdf import create_upload_payload


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
