"""Document API endpoints."""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pymongo.database import Database

from app.core.validators import (
    MAX_PAGINATION_LIMIT,
    validate_document_id,
    validate_document_name,
    validate_original_filename,
    validate_pagination,
)
from app.repositories import DocumentRepository
from app.schemas import DocumentResponse, DocumentUpdate
from app.services import DocumentService
from app.utils.database import get_db

router = APIRouter(prefix="/documents", tags=["documentos"])


def get_document_service(db: Database = Depends(get_db)) -> DocumentService:
    """Dependency to obtain the document service."""
    return DocumentService(DocumentRepository(db))


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear y procesar un nuevo documento",
)
async def create_document(
    name: str = Form(..., description="Nombre del documento"),
    file: UploadFile = File(..., description="Archivo PDF a registrar"),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Create a new document from an uploaded PDF.

    Validates the document name and the uploaded file on the router layer,
    then delegates business logic to the service.
    """
    # Layer 1: Router-level validation (fail fast)
    try:
        validated_name = validate_document_name(name)
        if file.filename:
            validate_original_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        file_content = await file.read()
        return service.create_document(validated_name, file.filename, file_content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await file.close()


@router.get(
    "", response_model=List[DocumentResponse], summary="Listar todos los documentos"
)
async def list_documents(
    skip: int = Query(0, ge=0, description="Cantidad de registros a omitir"),
    limit: int = Query(
        10, ge=1, le=MAX_PAGINATION_LIMIT, description="Cantidad maxima de registros"
    ),
    service: DocumentService = Depends(get_document_service),
) -> List[DocumentResponse]:
    """List all documents with validated pagination."""
    return service.get_all_documents(skip, limit)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Obtener un documento por ID",
)
async def get_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Get a document by ID."""
    document = service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} no encontrado",
        )
    return document


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Actualizar un documento",
)
async def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Update a document."""
    try:
        document = service.update_document(document_id, document_data)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento {document_id} no encontrado",
            )
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un documento",
)
async def delete_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
):
    """Delete a document."""
    success = service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento {document_id} no encontrado",
        )


@router.post(
    "/{document_id}/extract",
    response_model=DocumentResponse,
    summary="Obtener o completar el texto extraido de un documento",
)
async def extract_text(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Get or complete the extracted text of a document."""
    try:
        document = service.extract_text(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento {document_id} no encontrado",
            )
        return document
    except ValueError as exc:
        error_message = str(exc)
        status_code = (
            status.HTTP_409_CONFLICT
            if error_message
            == service.EXTRACT_ONLY_ON_UPLOAD_MESSAGE
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=error_message)
