"""Tests for document extraction endpoints."""

from datetime import UTC, datetime
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


def test_extract_document_without_cached_text_returns_problem_details(
    client: TestClient, db
):
    """Test that a memory-only document without cached text cannot be reprocessed."""
    document_id = 901
    db["documents"].insert_one(
        {
            "id": document_id,
            "name": "Memory Only Document",
            "original_filename": "memory-only.pdf",
            "file_path": "memory://documents/memory-only.pdf",
            "checksum": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "file_size": len(build_pdf_bytes("Placeholder text")),
            "extracted_text": None,
            "is_processed": False,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    response = client.post(f"/api/v1/documents/{document_id}/extract")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")

    problem_details = response.json()
    assert problem_details["type"] == "about:blank"
    assert problem_details["title"] == "Conflict"
    assert problem_details["status"] == 409
    assert (
        problem_details["detail"]
        == "La API procesa el PDF solo en el upload y no lo guarda en disco, por lo que no puede reprocesar."
    )
    assert problem_details["instance"].endswith(
        f"/api/v1/documents/{document_id}/extract"
    )
