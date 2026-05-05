"""Tests for document extraction endpoints."""

from fastapi.testclient import TestClient

from tests.support.api_documents import create_document_body
from tests.support.pdf import build_pdf_bytes


def test_extract_document_returns_processed_text_for_created_pdf(client: TestClient):
    """Test extracting a document returns processed text for a created PDF."""
    extracted_text = "Hello PDF extraction"
    created_document = create_document_body(
        client,
        name="Extractable Document",
        filename="extractable.pdf",
        content=build_pdf_bytes(extracted_text),
    )
    document_id = created_document["id"]

    assert created_document["is_processed"] is True
    assert created_document["extracted_text"] == extracted_text

    response = client.post(f"/api/v1/documents/{document_id}/extract")

    assert response.status_code == 200

    extracted_document = response.json()
    assert extracted_document["id"] == document_id
    assert extracted_document["is_processed"] is True
    assert extracted_document["extracted_text"] == extracted_text


def test_extract_document_returns_stored_text_without_reprocessing(client: TestClient):
    """Test that extraction returns the stored in-memory result."""
    original_text = "Original content"
    created_document = create_document_body(
        client,
        name="Processed In Memory",
        filename="processed.pdf",
        content=build_pdf_bytes(original_text),
    )
    document_id = created_document["id"]

    response = client.post(f"/api/v1/documents/{document_id}/extract")

    assert response.status_code == 200

    extracted_document = response.json()
    assert extracted_document["extracted_text"] == original_text
