"""Tests for document read endpoints."""

from fastapi.testclient import TestClient

from tests.support.api_documents import create_document_body


def test_list_documents_returns_empty_list_when_database_has_no_documents(
    client: TestClient,
):
    """Test listing documents returns an empty list when no documents exist."""
    response = client.get("/api/v1/documents")

    assert response.status_code == 200

    response_body = response.json()
    assert response_body == []


def test_get_document_returns_previously_created_document(client: TestClient):
    """Test getting a document returns a previously created document."""
    created_document = create_document_body(client)
    document_id = created_document["id"]

    response = client.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200

    document = response.json()
    assert document["id"] == document_id
    assert document["name"] == created_document["name"]
    assert document["original_filename"] == created_document["original_filename"]
    assert document["checksum"] == created_document["checksum"]


def test_get_document_returns_not_found_for_unknown_id(client: TestClient):
    """Test getting a document returns not found for an unknown ID."""
    response = client.get("/api/v1/documents/999")

    assert response.status_code == 404
