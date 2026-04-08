"""Tests for document endpoints"""

import pytest
from fastapi.testclient import TestClient


def test_list_documents_empty(client: TestClient):
    """Test listing documents when empty"""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_create_document(client: TestClient, tmp_path):
    """Test creating a document"""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    payload = {"name": "Test Document", "file_path": str(test_file), "file_size": 12}

    response = client.post("/api/v1/documents", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test Document"
    assert data["is_processed"] is False
    assert "id" in data


def test_get_document(client: TestClient, tmp_path):
    """Test getting a document by ID"""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Create a document
    payload = {"name": "Test Document", "file_path": str(test_file), "file_size": 12}
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    # Get the document
    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == document_id
    assert data["name"] == "Test Document"


def test_get_nonexistent_document(client: TestClient):
    """Test getting a non-existent document"""
    response = client.get("/api/v1/documents/999")
    assert response.status_code == 404


def test_update_document(client: TestClient, tmp_path):
    """Test updating a document"""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Create a document
    payload = {"name": "Test Document", "file_path": str(test_file), "file_size": 12}
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
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Create a document
    payload = {"name": "Test Document", "file_path": str(test_file), "file_size": 12}
    create_response = client.post("/api/v1/documents", json=payload)
    document_id = create_response.json()["id"]

    # Delete the document
    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404
