"""Tests for document delete endpoints."""

from fastapi.testclient import TestClient

from tests.support.api_documents import create_document_body


def test_delete_document_removes_document_from_subsequent_reads(client: TestClient):
    """Test deleting a document removes it from subsequent reads."""
    created_document = create_document_body(client)
    document_id = created_document["id"]

    response = client.delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 204

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404
