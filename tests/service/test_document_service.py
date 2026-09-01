"""Tests for the document service business layer.

These tests exercise DocumentService through its own interface, without going
through HTTP. State is prepared using the repository's public API, never by
writing raw documents into the database.
"""

import pytest

from app.config import settings
from app.models import Document
from app.repositories import DocumentRepository
from app.schemas import DocumentUpdate
from app.services import DocumentService
from tests.support.pdf import (
    DEFAULT_PDF_TEXT,
    MINIMAL_PDF_BYTES,
    build_pdf_bytes,
    pdf_checksum,
)


@pytest.fixture
def repository(db) -> DocumentRepository:
    """Provide a repository backed by the isolated test database."""
    return DocumentRepository(db)


@pytest.fixture
def service(repository: DocumentRepository) -> DocumentService:
    """Provide a document service wired to the test repository."""
    return DocumentService(repository)


def store_unprocessed_document(repository: DocumentRepository) -> Document:
    """Persist a document that has no extracted text, via the repository API."""
    return repository.create(
        Document(
            name="Memory Only Document",
            original_filename="memory-only.pdf",
            file_path="memory://documents/memory-only.pdf",
            checksum="0" * 64,
            file_size=len(MINIMAL_PDF_BYTES),
            extracted_text=None,
            is_processed=False,
        )
    )


# create_document


def test_create_document_persists_extracted_text_and_checksum(
    service: DocumentService,
):
    """Test creating a document extracts its text and stores its checksum."""
    document = service.create_document("Contrato", "contrato.pdf", MINIMAL_PDF_BYTES)

    assert document.id is not None
    assert document.name == "Contrato"
    assert document.original_filename == "contrato.pdf"
    assert document.checksum == pdf_checksum(MINIMAL_PDF_BYTES)
    assert document.file_size == len(MINIMAL_PDF_BYTES)
    assert document.extracted_text == DEFAULT_PDF_TEXT
    assert document.is_processed is True


def test_create_document_extracts_the_text_embedded_in_the_pdf(
    service: DocumentService,
):
    """Test the extracted text comes from the uploaded PDF content."""
    original_text = "Clausula primera del contrato"

    document = service.create_document(
        "Contrato", "contrato.pdf", build_pdf_bytes(original_text)
    )

    assert document.extracted_text == original_text


def test_create_document_assigns_sequential_ids(service: DocumentService):
    """Test each created document receives the next sequential ID."""
    first = service.create_document("Primero", "a.pdf", build_pdf_bytes("Uno"))
    second = service.create_document("Segundo", "b.pdf", build_pdf_bytes("Dos"))

    assert second.id == first.id + 1


def test_create_document_rejects_duplicate_checksum(service: DocumentService):
    """Test creating a document rejects content already stored."""
    service.create_document("Original", "original.pdf", MINIMAL_PDF_BYTES)

    with pytest.raises(ValueError) as error:
        service.create_document("Duplicado", "duplicado.pdf", MINIMAL_PDF_BYTES)

    assert str(error.value) == "Ya existe un documento con el mismo checksum"


def test_create_document_rejects_blank_document_name(service: DocumentService):
    """Test creating a document rejects blank document names."""
    with pytest.raises(ValueError) as error:
        service.create_document("   ", "contrato.pdf", MINIMAL_PDF_BYTES)

    assert str(error.value) == "El nombre del documento es obligatorio"


def test_create_document_rejects_file_without_pdf_extension(service: DocumentService):
    """Test creating a document rejects filenames that are not PDFs."""
    with pytest.raises(ValueError) as error:
        service.create_document("Invalido", "notas.txt", MINIMAL_PDF_BYTES)

    assert str(error.value) == "Solo se permiten archivos PDF"


def test_create_document_rejects_content_without_pdf_signature(
    service: DocumentService,
):
    """Test creating a document rejects content that is not a real PDF."""
    with pytest.raises(ValueError) as error:
        service.create_document("Falso", "falso.pdf", b"esto no es un pdf")

    assert str(error.value) == "Archivo PDF invalido"


def test_create_document_rejects_pdf_larger_than_configured_limit(
    service: DocumentService, monkeypatch
):
    """Test creating a document rejects PDFs above the configured size limit."""
    monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)

    with pytest.raises(ValueError) as error:
        service.create_document("Muy grande", "grande.pdf", MINIMAL_PDF_BYTES)

    assert "El PDF supera el tamano maximo permitido" in str(error.value)


def test_create_document_does_not_persist_rejected_documents(
    service: DocumentService,
):
    """Test a rejected upload leaves no document stored."""
    with pytest.raises(ValueError):
        service.create_document("Falso", "falso.pdf", b"esto no es un pdf")

    assert service.get_all_documents() == []


# get_document / get_all_documents


def test_get_document_returns_the_stored_document(service: DocumentService):
    """Test reading a document by ID returns the stored document."""
    created = service.create_document("Contrato", "contrato.pdf", MINIMAL_PDF_BYTES)

    found = service.get_document(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.name == "Contrato"


def test_get_document_returns_none_for_unknown_id(service: DocumentService):
    """Test reading an unknown document returns nothing."""
    assert service.get_document(999) is None


def test_get_all_documents_returns_documents_in_creation_order(
    service: DocumentService,
):
    """Test listing documents returns them ordered by ID."""
    service.create_document("Primero", "a.pdf", build_pdf_bytes("Uno"))
    service.create_document("Segundo", "b.pdf", build_pdf_bytes("Dos"))

    documents = service.get_all_documents()

    assert [document.name for document in documents] == ["Primero", "Segundo"]


def test_get_all_documents_applies_pagination(service: DocumentService):
    """Test listing documents honours skip and limit."""
    service.create_document("Primero", "a.pdf", build_pdf_bytes("Uno"))
    service.create_document("Segundo", "b.pdf", build_pdf_bytes("Dos"))

    documents = service.get_all_documents(skip=1, limit=1)

    assert [document.name for document in documents] == ["Segundo"]


# extract_text


def test_extract_text_returns_stored_text_for_processed_document(
    service: DocumentService,
):
    """Test extracting text returns the text captured during upload."""
    created = service.create_document("Contrato", "contrato.pdf", MINIMAL_PDF_BYTES)

    extracted = service.extract_text(created.id)

    assert extracted is not None
    assert extracted.extracted_text == DEFAULT_PDF_TEXT


def test_extract_text_rejects_document_without_cached_text(
    service: DocumentService, repository: DocumentRepository
):
    """Test a document stored without extracted text cannot be reprocessed."""
    stored = store_unprocessed_document(repository)

    with pytest.raises(ValueError) as error:
        service.extract_text(stored.id)

    assert str(error.value) == DocumentService.EXTRACT_ONLY_ON_UPLOAD_MESSAGE


def test_extract_text_returns_none_for_unknown_id(service: DocumentService):
    """Test extracting text from an unknown document returns nothing."""
    assert service.extract_text(999) is None


# update_document


def test_update_document_changes_the_document_name(service: DocumentService):
    """Test updating a document changes its name."""
    created = service.create_document("Nombre viejo", "contrato.pdf", MINIMAL_PDF_BYTES)

    updated = service.update_document(created.id, DocumentUpdate(name="Nombre nuevo"))

    assert updated is not None
    assert updated.name == "Nombre nuevo"
    assert service.get_document(created.id).name == "Nombre nuevo"


def test_update_document_rejects_blank_document_name(service: DocumentService):
    """Test updating a document rejects blank names."""
    created = service.create_document("Contrato", "contrato.pdf", MINIMAL_PDF_BYTES)

    with pytest.raises(ValueError) as error:
        service.update_document(created.id, DocumentUpdate(name="   "))

    assert str(error.value) == "El nombre del documento es obligatorio"


def test_update_document_returns_none_for_unknown_id(service: DocumentService):
    """Test updating an unknown document returns nothing."""
    assert service.update_document(999, DocumentUpdate(name="Otro")) is None


# delete_document


def test_delete_document_removes_it_from_subsequent_reads(service: DocumentService):
    """Test deleting a document removes it from later reads."""
    created = service.create_document("Contrato", "contrato.pdf", MINIMAL_PDF_BYTES)

    assert service.delete_document(created.id) is True
    assert service.get_document(created.id) is None


def test_delete_document_returns_false_for_unknown_id(service: DocumentService):
    """Test deleting an unknown document reports that nothing was deleted."""
    assert service.delete_document(999) is False
