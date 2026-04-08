"""Document service - Business logic"""

import os
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Document
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.repositories import DocumentRepository


class DocumentService:
    """Service for document business logic"""

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
        # Validate that file exists
        if not os.path.exists(document_data.file_path):
            raise ValueError(f"File not found: {document_data.file_path}")

        document = Document(
            name=document_data.name,
            file_path=document_data.file_path,
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
            # Placeholder for PDF extraction logic
            # In a real application, integrate with PyPDF2 or similar
            extracted_text = f"Extracted text from {document.name}"

            update_data = {"extracted_text": extracted_text, "is_processed": True}
            updated_doc = self.repository.update(document_id, update_data)
            return DocumentResponse.model_validate(updated_doc)

        except Exception as e:
            raise ValueError(f"Error extracting text: {str(e)}")
