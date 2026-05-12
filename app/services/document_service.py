"""Document service - Business logic."""

from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional

from app.config import settings
from app.core import validators as v
from app.models import Document
from app.repositories import DocumentRepository
from app.schemas import DocumentResponse, DocumentUpdate


class DocumentService:
    """Service for document business logic."""

    def __init__(self, db: Any):
        """Initialize service with database session."""
        self.repository = DocumentRepository(db)
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_document(
        self, name: str, original_filename: str | None, file_content: bytes
    ) -> DocumentResponse:
        """Create a new document from uploaded PDF bytes."""
        normalized_name = v.validate_document_name(name)
        normalized_filename = v.validate_original_filename(original_filename)

        self._validate_pdf_content(normalized_filename, file_content)

        checksum = v.calculate_checksum(file_content)
        existing = self.repository.get_by_checksum(checksum)
        v.validate_unique_checksum(checksum, existing_document=existing)

        extracted_text = self._extract_pdf_text_from_bytes(file_content)
        document = Document(
            name=normalized_name,
            original_filename=normalized_filename,
            file_path=self._build_memory_reference(checksum),
            checksum=checksum,
            file_size=len(file_content),
            extracted_text=extracted_text,
            is_processed=True,
        )

        created_document = self.repository.create(document)
        return DocumentResponse.model_validate(created_document)

    def get_document(self, document_id: int) -> Optional[DocumentResponse]:
        """Get document by ID."""
        document = self.repository.get_by_id(document_id)
        if not document:
            return None
        return DocumentResponse.model_validate(document)

    def get_all_documents(
        self, skip: int = 0, limit: int = 10
    ) -> List[DocumentResponse]:
        """Get all documents with validated pagination."""
        validated_skip, validated_limit = v.validate_pagination(skip, limit)
        documents = self.repository.get_all(validated_skip, validated_limit)
        return [DocumentResponse.model_validate(doc) for doc in documents]

    def update_document(
        self, document_id: int, document_data: DocumentUpdate
    ) -> Optional[DocumentResponse]:
        """Update document name."""
        update_data = document_data.model_dump(exclude_unset=True)
        if "name" in update_data:
            update_data["name"] = v.validate_document_name(update_data["name"])

        document = self.repository.update(document_id, update_data)
        if not document:
            return None

        return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: int) -> bool:
        """Delete document."""
        document = self.repository.get_by_id(document_id)
        if not document:
            return False

        deleted = self.repository.delete(document_id)
        if deleted and document.file_path:
            legacy_path = Path(document.file_path)
            if legacy_path.is_file():
                legacy_path.unlink(missing_ok=True)
        return deleted

    def extract_text(self, document_id: int) -> Optional[DocumentResponse]:
        """Extract text from PDF document."""
        document = self.repository.get_by_id(document_id)
        if not document:
            return None

        if document.is_processed and document.extracted_text is not None:
            return DocumentResponse.model_validate(document)

        file_path = Path(document.file_path)
        v.validate_pdf_file_on_disk(
            file_path, document.file_size, settings.max_pdf_size_bytes
        )

        current_checksum = self._calculate_file_checksum(file_path)
        if current_checksum != document.checksum:
            raise ValueError("Document file no longer matches the stored checksum")

        extracted_text = self._extract_pdf_text_from_file(file_path)

        update_data = {
            "extracted_text": extracted_text,
            "is_processed": True,
        }
        updated_doc = self.repository.update(document_id, update_data)
        return DocumentResponse.model_validate(updated_doc)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_pdf_content(self, original_filename: str, file_content: bytes) -> None:
        """Validate extension, size and magic signature of uploaded PDF bytes."""
        v.validate_pdf_extension(original_filename)
        v.validate_pdf_size(file_content, settings.max_pdf_size_bytes)
        v.validate_pdf_signature(file_content)

    # ------------------------------------------------------------------
    # Checksum helpers
    # ------------------------------------------------------------------
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file on disk."""
        digest = __import__("hashlib").sha256()
        with file_path.open("rb") as pdf_file:
            for chunk in iter(lambda: pdf_file.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------
    def _extract_pdf_text_from_bytes(self, file_content: bytes) -> str:
        """Extract text from uploaded PDF bytes."""
        return self._extract_pdf_text(BytesIO(file_content))

    def _extract_pdf_text_from_file(self, file_path: Path) -> str:
        """Extract text from a stored PDF file."""
        return self._extract_pdf_text(str(file_path))

    @staticmethod
    def _extract_pdf_text(pdf_source: BytesIO | str) -> str:
        """Extract text from a PDF source using pypdf."""
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF extraction dependency is not installed") from exc

        try:
            reader = PdfReader(pdf_source)
            page_texts = []
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(text)
            return "\n\n".join(page_texts)
        except Exception as exc:
            raise ValueError(f"Error extracting text: {exc}") from exc

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _build_memory_reference(checksum: str) -> str:
        """Build a logical reference for an in-memory processed document."""
        return f"memory://documents/{checksum}.pdf"
