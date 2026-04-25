"""Document service - Business logic"""

import hashlib
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.repositories import DocumentRepository
from app.schemas import DocumentCreate, DocumentResponse, DocumentUpdate


class DocumentService:
    """Service for document business logic"""

    PDF_SIGNATURE = b"%PDF-"

    def __init__(self, db: Session):
        """
        Initialize service with database session

        Args:
            db: SQLAlchemy database session
        """
        self.repository = DocumentRepository(db)
        self.db = db

    def create_document(self, document_data: DocumentCreate) -> DocumentResponse:
        """
        Create a new document

        Args:
            document_data: Document creation schema

        Returns:
            Created document response
        """
        file_path = Path(document_data.file_path)
        self._validate_pdf_file(file_path, document_data.file_size)
        checksum = self._calculate_checksum(file_path)

        if self.repository.get_by_checksum(checksum):
            raise ValueError("Document with the same checksum already exists")

        if self.repository.get_by_file_path(str(file_path)):
            raise ValueError("Document with this file path already exists")

        document = Document(
            name=document_data.name,
            file_path=str(file_path),
            checksum=checksum,
            file_size=document_data.file_size,
            is_processed=False,
        )

        created_document = self.repository.create(document)
        return DocumentResponse.model_validate(created_document)

    def get_document(self, document_id: int) -> Optional[DocumentResponse]:
        """
        Get document by ID

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
        Get all documents

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
        Update document

        Args:
            document_id: Document ID
            document_data: Update schema

        Returns:
            Updated document response if found
        """
        update_data = document_data.model_dump(exclude_unset=True)
        document = self.repository.update(document_id, update_data)

        if not document:
            return None

        return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: int) -> bool:
        """
        Delete document

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        return self.repository.delete(document_id)

    def extract_text(self, document_id: int) -> Optional[DocumentResponse]:
        """
        Extract text from PDF document

        Args:
            document_id: Document ID

        Returns:
            Updated document response
        """
        document = self.repository.get_by_id(document_id)
        if not document:
            return None

        try:
            file_path = Path(document.file_path)
            self._validate_pdf_file(file_path, document.file_size)

            current_checksum = self._calculate_checksum(file_path)
            if current_checksum != document.checksum:
                raise ValueError("Document file no longer matches the stored checksum")

            extracted_text = self._extract_pdf_text(file_path)

            update_data = {"extracted_text": extracted_text, "is_processed": True}
            updated_doc = self.repository.update(document_id, update_data)
            return DocumentResponse.model_validate(updated_doc)

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Error extracting text: {str(e)}")

    def _validate_pdf_file(self, file_path: Path, expected_size: int) -> None:
        """
        Validate that the given path points to a PDF file with a valid size.

        Args:
            file_path: Path to the file on disk
            expected_size: Size received from the API payload
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

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate the SHA-256 checksum of a file.

        Args:
            file_path: Path to the file on disk

        Returns:
            SHA-256 checksum as a hex string
        """
        digest = hashlib.sha256()
        with file_path.open("rb") as pdf_file:
            for chunk in iter(lambda: pdf_file.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _extract_pdf_text(self, file_path: Path) -> str:
        """
        Extract text from a PDF using pypdf.

        Args:
            file_path: Path to the PDF file on disk

        Returns:
            Extracted text with normalized page separation
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF extraction dependency is not installed") from exc

        try:
            reader = PdfReader(str(file_path))
            page_texts = []
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(text)
            return "\n\n".join(page_texts)
        except Exception as exc:
            raise ValueError(f"Error extracting text: {str(exc)}") from exc
