"""Document service - Business logic."""

from io import BytesIO
import hashlib
from pathlib import Path
from typing import Any, List, Optional

from app.config import settings
from app.models import Document
from app.repositories import DocumentRepository
from app.schemas import DocumentResponse, DocumentUpdate


class DocumentService:
    """Service for document business logic."""

    PDF_SIGNATURE = b"%PDF-"

    def __init__(self, db: Any):
        """
        Initialize service with database session.

        Args:
            db: Database handle
        """
        self.repository = DocumentRepository(db)
        self.db = db

    def create_document(
        self, name: str, original_filename: str | None, file_content: bytes
    ) -> DocumentResponse:
        """
        Create a new document from uploaded PDF bytes.

        Args:
            name: Human-readable document name
            original_filename: Original uploaded filename
            file_content: Uploaded PDF bytes

        Returns:
            Created document response
        """
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Document name is required")

        normalized_filename = self._normalize_original_filename(original_filename)
        self._validate_uploaded_pdf(normalized_filename, file_content)
        checksum = self._calculate_checksum(file_content)

        if self.repository.get_by_checksum(checksum):
            raise ValueError("Document with the same checksum already exists")

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
        """
        Get document by ID.

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
        """
        Get all documents.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of document responses
        """
        documents = self.repository.get_all(skip, limit)
        return [DocumentResponse.model_validate(doc) for doc in documents]

    def update_document(
        self, document_id: int, document_data: DocumentUpdate
    ) -> Optional[DocumentResponse]:
        """
        Update document.

        Args:
            document_id: Document ID
            document_data: Update schema

        Returns:
            Updated document response if found
        """
        update_data = document_data.model_dump(exclude_unset=True)
        if "name" in update_data:
            normalized_name = update_data["name"].strip()
            if not normalized_name:
                raise ValueError("Document name is required")
            update_data["name"] = normalized_name

        document = self.repository.update(document_id, update_data)

        if not document:
            return None

        return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: int) -> bool:
        """
        Delete document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
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
        """
        Extract text from PDF document.

        Args:
            document_id: Document ID

        Returns:
            Updated document response
        """
        document = self.repository.get_by_id(document_id)
        if not document:
            return None

        try:
            if document.is_processed and document.extracted_text is not None:
                return DocumentResponse.model_validate(document)

            file_path = Path(document.file_path)
            self._validate_pdf_file(file_path, document.file_size)

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

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Error extracting text: {str(exc)}")

    def _normalize_original_filename(self, original_filename: str | None) -> str:
        """
        Normalize the uploaded filename for safe persistence.

        Args:
            original_filename: Original uploaded filename

        Returns:
            Sanitized filename
        """
        if not original_filename:
            raise ValueError("A PDF file is required")

        normalized_filename = Path(original_filename).name.strip()
        if not normalized_filename:
            raise ValueError("A PDF file is required")

        return normalized_filename

    def _validate_uploaded_pdf(
        self, original_filename: str | None, file_content: bytes
    ) -> None:
        """
        Validate uploaded PDF bytes before persistence.

        Args:
            original_filename: Original uploaded filename
            file_content: Uploaded PDF bytes
        """
        if Path(original_filename).suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are allowed")

        file_size = len(file_content)
        if file_size == 0:
            raise ValueError("Invalid PDF file")

        if file_size > settings.max_pdf_size_bytes:
            raise ValueError(
                f"PDF exceeds maximum allowed size of {settings.max_pdf_size_bytes} bytes"
            )

        if file_content[: len(self.PDF_SIGNATURE)] != self.PDF_SIGNATURE:
            raise ValueError("Invalid PDF file")

    def _validate_pdf_file(self, file_path: Path, expected_size: int) -> None:
        """
        Validate that the given path points to a stored PDF file with a valid size.

        Args:
            file_path: Path to the file on disk
            expected_size: Expected size in bytes
        """
        if not file_path.is_file():
            raise ValueError(f"File not found: {file_path}")

        if file_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are allowed")

        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            raise ValueError(
                f"File size mismatch: expected {expected_size} bytes, found {actual_size}"
            )

        if actual_size > settings.max_pdf_size_bytes:
            raise ValueError(
                f"PDF exceeds maximum allowed size of {settings.max_pdf_size_bytes} bytes"
            )

        with file_path.open("rb") as pdf_file:
            if pdf_file.read(len(self.PDF_SIGNATURE)) != self.PDF_SIGNATURE:
                raise ValueError("Invalid PDF file")

    def _calculate_checksum(self, file_content: bytes) -> str:
        """
        Calculate the SHA-256 checksum of uploaded bytes.

        Args:
            file_content: Uploaded PDF bytes

        Returns:
            SHA-256 checksum as a hex string
        """
        digest = hashlib.sha256()
        digest.update(file_content)
        return digest.hexdigest()

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """
        Calculate the SHA-256 checksum of a stored file.

        Args:
            file_path: Path to the stored file on disk

        Returns:
            SHA-256 checksum as a hex string
        """
        digest = hashlib.sha256()
        with file_path.open("rb") as pdf_file:
            for chunk in iter(lambda: pdf_file.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _build_memory_reference(self, checksum: str) -> str:
        """
        Build a logical reference for a document processed fully in memory.

        Args:
            checksum: SHA-256 checksum of the file

        Returns:
            Stable reference string stored for backward compatibility
        """
        return f"memory://documents/{checksum}.pdf"

    def _extract_pdf_text_from_bytes(self, file_content: bytes) -> str:
        """
        Extract text from uploaded PDF bytes using pypdf.

        Args:
            file_content: Uploaded PDF bytes

        Returns:
            Extracted text with normalized page separation
        """
        return self._extract_pdf_text(BytesIO(file_content))

    def _extract_pdf_text_from_file(self, file_path: Path) -> str:
        """
        Extract text from a legacy stored PDF file using pypdf.

        Args:
            file_path: Path to the PDF file on disk

        Returns:
            Extracted text with normalized page separation
        """
        return self._extract_pdf_text(str(file_path))

    def _extract_pdf_text(self, pdf_source: BytesIO | str) -> str:
        """
        Extract text from a PDF source using pypdf.

        Args:
            pdf_source: File-like object in memory or a file path

        Returns:
            Extracted text with normalized page separation
        """
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
            raise ValueError(f"Error extracting text: {str(exc)}") from exc
