"""Document service - Business logic."""

from io import BytesIO
from typing import List, Optional

from app.config import settings
from app.core import validators as v
from app.models import Document
from app.repositories import DocumentRepository
from app.schemas import DocumentResponse, DocumentUpdate


class DocumentService:
    """Service for document business logic."""

    EXTRACT_ONLY_ON_UPLOAD_MESSAGE = (
        "La API procesa el PDF solo en el upload y no lo guarda en disco, "
        "por lo que no puede reprocesar."
    )

    def __init__(self, repository: DocumentRepository):
        """Initialize service with the document repository.

        Args:
            repository: Persistence adapter for documents
        """
        self.repository = repository

    def create_document(
        self, name: str, original_filename: str | None, file_content: bytes
    ) -> DocumentResponse:
        """Create a new document from uploaded PDF bytes.

        Args:
            name: Human-readable document name
            original_filename: Original uploaded filename
            file_content: Uploaded PDF bytes

        Returns:
            Created document response
        """
        normalized_name = v.validate_document_name(name)
        normalized_filename = self._normalize_original_filename(original_filename)
        self._validate_uploaded_pdf(normalized_filename, file_content)
        checksum = v.calculate_checksum(file_content)

        if self.repository.get_by_checksum(checksum):
            raise ValueError("Ya existe un documento con el mismo checksum")

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
        """Get document by ID.

        Args:
            document_id: Document ID

        Returns:
            Document response if found
        """
        document = self.repository.get_by_id(document_id)
        if not document:
            return None
        return DocumentResponse.model_validate(document)

    def get_all_documents(
        self, skip: int = 0, limit: int = 10
    ) -> List[DocumentResponse]:
        """Get all documents.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of document responses
        """
        validated_skip, validated_limit = v.validate_pagination(skip, limit)
        documents = self.repository.get_all(validated_skip, validated_limit)
        return [DocumentResponse.model_validate(doc) for doc in documents]

    def update_document(
        self, document_id: int, document_data: DocumentUpdate
    ) -> Optional[DocumentResponse]:
        """Update document.

        Args:
            document_id: Document ID
            document_data: Update schema

        Returns:
            Updated document response if found
        """
        update_data = document_data.model_dump(exclude_unset=True)
        if "name" in update_data:
            update_data["name"] = v.validate_document_name(update_data["name"])

        document = self.repository.update(document_id, update_data)

        if not document:
            return None

        return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: int) -> bool:
        """Delete document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        document = self.repository.get_by_id(document_id)
        if not document:
            return False

        return self.repository.delete(document_id)

    def extract_text(self, document_id: int) -> Optional[DocumentResponse]:
        document = self.repository.get_by_id(document_id)
        if not document:
            return None

        if document.is_processed and document.extracted_text is not None:
            return DocumentResponse.model_validate(document)

        raise ValueError(self.EXTRACT_ONLY_ON_UPLOAD_MESSAGE)

    def _normalize_original_filename(self, original_filename: str | None) -> str:
        """Normalize the uploaded filename for safe persistence.

        Args:
            original_filename: Original uploaded filename

        Returns:
            Sanitized filename
        """
        return v.validate_original_filename(original_filename)

    def _validate_uploaded_pdf(
        self, original_filename: str, file_content: bytes
    ) -> None:
        """Validate uploaded PDF bytes before persistence.

        Args:
            original_filename: Original uploaded filename
            file_content: Uploaded PDF bytes
        """
        # Delegate to pure validators in app.core.validators
        v.validate_pdf_extension(original_filename)
        v.validate_pdf_size(file_content, settings.max_pdf_size_bytes)
        v.validate_pdf_signature(file_content)

    def _build_memory_reference(self, checksum: str) -> str:
        """Build a logical reference for a document processed fully in memory.

        Args:
            checksum: SHA-256 checksum of the file

        Returns:
            Stable reference string stored for backward compatibility
        """
        return f"memory://documents/{checksum}.pdf"

    def _extract_pdf_text_from_bytes(self, file_content: bytes) -> str:
        """Extract text from uploaded PDF bytes using pypdf.

        Args:
            file_content: Uploaded PDF bytes

        Returns:
            Extracted text with normalized page separation
        """
        return self._extract_pdf_text(BytesIO(file_content))

    def _extract_pdf_text(self, pdf_source: BytesIO | str) -> str:
        """Extract text from a PDF source using pypdf.

        Args:
            pdf_source: File-like object in memory or a file path

        Returns:
            Extracted text with normalized page separation
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "La dependencia de extraccion de PDF no esta instalada"
            ) from exc

        try:
            reader = PdfReader(pdf_source)
            page_texts = []
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(text)
            return "\n\n".join(page_texts)
        except Exception as exc:
            raise ValueError(f"Error al extraer el texto: {str(exc)}") from exc
