"""Shared API helpers for document-related tests."""

from collections.abc import Mapping
from typing import Any

from fastapi.testclient import TestClient

from tests.support.pdf import (
    DEFAULT_PDF_TEXT,
    MINIMAL_PDF_BYTES,
    SHA256_MINIMAL_PDF,
    create_upload_payload,
)

DOCUMENTS_PATH = "/api/v1/documents"


def create_document_response(client: TestClient, **upload_kwargs: Any):
    """Create a document through the API and return the raw response."""
    data, files = create_upload_payload(**upload_kwargs)
    return client.post(DOCUMENTS_PATH, data=data, files=files)


def create_document_body(client: TestClient, **upload_kwargs: Any) -> Mapping[str, Any]:
    """Create a document through the API and return the parsed response body."""
    response = create_document_response(client, **upload_kwargs)
    return response.json()


def assert_created_document(
    document: Mapping[str, Any],
    *,
    expected_name: str = "Test Document",
    expected_filename: str = "test.pdf",
    expected_content: bytes = MINIMAL_PDF_BYTES,
    expected_checksum: str = SHA256_MINIMAL_PDF,
    expected_text: str = DEFAULT_PDF_TEXT,
) -> None:
    """Assert the standard response fields for a successfully created document.

    El checksum esperado es un literal conocido, no se recalcula sobre el
    contenido. Por eso, si se pasa un `expected_content` distinto al PDF
    minimo, hay que pasar tambien su `expected_checksum`.
    """
    assert document["name"] == expected_name
    assert document["original_filename"] == expected_filename
    assert document["checksum"] == expected_checksum
    assert document["file_size"] == len(expected_content)
    assert document["is_processed"] is True
    assert document["extracted_text"] == expected_text
    assert "file_path" not in document
    assert "id" in document
