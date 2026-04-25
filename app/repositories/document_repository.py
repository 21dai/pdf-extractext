"""Document repository for database operations"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Document


class DocumentRepository:
    """Repository for Document database operations"""

    def __init__(self, session: Session):
        """
        Initialize repository with database session

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def create(self, document: Document) -> Document:
        """
        Create a new document

        Args:
            document: Document object to create

        Returns:
            Created document
        """
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get_by_id(self, document_id: int) -> Optional[Document]:
        """
        Get document by ID

        Args:
            document_id: Document ID

        Returns:
            Document if found, None otherwise
        """
        return self.session.query(Document).filter(Document.id == document_id).first()

    def get_all(self, skip: int = 0, limit: int = 10) -> List[Document]:
        """
        Get all documents with pagination

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of documents
        """
        return self.session.query(Document).offset(skip).limit(limit).all()

    def get_by_name(self, name: str) -> Optional[Document]:
        """
        Get document by name

        Args:
            name: Document name

        Returns:
            Document if found, None otherwise
        """
        return self.session.query(Document).filter(Document.name == name).first()

    def get_by_file_path(self, file_path: str) -> Optional[Document]:
        """
        Get document by file path.

        Args:
            file_path: Document file path

        Returns:
            Document if found, None otherwise
        """
        return self.session.query(Document).filter(Document.file_path == file_path).first()

    def get_by_checksum(self, checksum: str) -> Optional[Document]:
        """
        Get document by checksum.

        Args:
            checksum: SHA-256 checksum of the file

        Returns:
            Document if found, None otherwise
        """
        return self.session.query(Document).filter(Document.checksum == checksum).first()

    def update(self, document_id: int, data: dict) -> Optional[Document]:
        """
        Update document

        Args:
            document_id: Document ID
            data: Dictionary with fields to update

        Returns:
            Updated document if found, None otherwise
        """
        document = self.get_by_id(document_id)
        if not document:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(document, key, value)

        self.session.commit()
        self.session.refresh(document)
        return document

    def delete(self, document_id: int) -> bool:
        """
        Delete document

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        document = self.get_by_id(document_id)
        if not document:
            return False

        self.session.delete(document)
        self.session.commit()
        return True
