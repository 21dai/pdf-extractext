"""Document API endpoints"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.services import DocumentService
from app.utils.database import get_db

router = APIRouter(prefix="/documents", tags=["documentos"])


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    """Dependencia para obtener el servicio de documentos."""
    return DocumentService(db)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo documento",
)
async def create_document(
    document_data: DocumentCreate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Crear un nuevo documento.

    Args:
        document_data: Datos del documento a crear
        service: Servicio de documentos

    Returns:
        Documento creado
    """
    try:
        return service.create_document(document_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "", response_model=List[DocumentResponse], summary="Listar todos los documentos"
)
async def list_documents(
    skip: int = 0,
    limit: int = 10,
    service: DocumentService = Depends(get_document_service),
) -> List[DocumentResponse]:
    """
    Listar todos los documentos con paginacion.

    Args:
        skip: Cantidad de registros a omitir
        limit: Cantidad maxima de registros
        service: Servicio de documentos

    Returns:
        Lista de documentos
    """
    return service.get_all_documents(skip, limit)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Obtener un documento por ID",
)
async def get_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Obtener un documento por su ID.

    Args:
        document_id: ID del documento
        service: Servicio de documentos

    Returns:
        Detalle del documento

    Raises:
        HTTPException: Si el documento no existe
    """
    document = service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
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
    """
    Actualizar un documento.

    Args:
        document_id: ID del documento
        document_data: Datos del documento a actualizar
        service: Servicio de documentos

    Returns:
        Documento actualizado

    Raises:
        HTTPException: Si el documento no existe
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
    summary="Eliminar un documento",
)
async def delete_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
):
    """
    Eliminar un documento.

    Args:
        document_id: ID del documento
        service: Servicio de documentos

    Raises:
        HTTPException: Si el documento no existe
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
    summary="Extraer texto de un documento",
)
async def extract_text(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Extraer texto real de un documento PDF.

    Args:
        document_id: ID del documento
        service: Servicio de documentos

    Returns:
        Documento con el texto extraido

    Raises:
        HTTPException: Si el documento no existe o falla la extraccion
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
