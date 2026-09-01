"""Shared domain-model fixtures for document tests."""

from app.models import Document

UNPROCESSED_CHECKSUM = "0" * 64


def build_unprocessed_document(document_id: int | None = None) -> Document:
    """Build a document stored without extracted text.

    This state cannot be produced through the public API, because uploads are
    always processed in memory. Tests that need it persist this model through
    the repository, so they never depend on the stored document's shape.
    """
    return Document(
        id=document_id,
        name="Memory Only Document",
        original_filename="memory-only.pdf",
        file_path="memory://documents/memory-only.pdf",
        checksum=UNPROCESSED_CHECKSUM,
        file_size=1024,
        extracted_text=None,
        is_processed=False,
    )
