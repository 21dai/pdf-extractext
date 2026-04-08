"""Document API endpoints"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.services import DocumentService
from app.utils.database import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    """Dependency to get document service"""
    return DocumentService(db)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document",
)
async def create_document(
    document_data: DocumentCreate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Create a new document

    Args:
        document_data: Document creation data
        service: Document service

    Returns:
        Created document
    """
    try:
        return service.create_document(document_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[DocumentResponse], summary="List all documents")
async def list_documents(
    skip: int = 0,
    limit: int = 10,
    service: DocumentService = Depends(get_document_service),
) -> List[DocumentResponse]:
    """
    List all documents with pagination

    Args:
        skip: Number of records to skip
        limit: Maximum number of records
        service: Document service

    Returns:
        List of documents
    """
    return service.get_all_documents(skip, limit)


@router.get(
    "/{document_id}", response_model=DocumentResponse, summary="Get a document by ID"
)
async def get_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Get a document by ID

    Args:
        document_id: Document ID
        service: Document service

    Returns:
        Document details

    Raises:
        HTTPException: If document not found
    """
    document = service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return document


@router.put(
    "/{document_id}", response_model=DocumentResponse, summary="Update a document"
)
async def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Update a document

    Args:
        document_id: Document ID
        document_data: Document update data
        service: Document service

    Returns:
        Updated document

    Raises:
        HTTPException: If document not found
    """
    document = service.update_document(document_id, document_data)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
):
    """
    Delete a document

    Args:
        document_id: Document ID
        service: Document service

    Raises:
        HTTPException: If document not found
    """
    success = service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )


@router.post(
    "/{document_id}/extract",
    response_model=DocumentResponse,
    summary="Extract text from document",
)
async def extract_text(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Extract text from a PDF document

    Args:
        document_id: Document ID
        service: Document service

    Returns:
        Document with extracted text

    Raises:
        HTTPException: If document not found or extraction fails
    """
    try:
        document = service.extract_text(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )
        return document
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
