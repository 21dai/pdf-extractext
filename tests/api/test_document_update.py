"""Tests for document update endpoints."""

from fastapi.testclient import TestClient

from tests.support.pdf import create_upload_payload


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
