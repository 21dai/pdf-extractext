"""Document API endpoints."""

from typing import List
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.schemas import DocumentResponse, DocumentUpdate
from app.services import DocumentService
from app.utils.database import get_db

router = APIRouter(prefix="/documents", tags=["documentos"])


def get_document_service(db: Any = Depends(get_db)) -> DocumentService:
    """Dependencia para obtener el servicio de documentos."""
    return DocumentService(db)


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
    """
    Crear un nuevo documento a partir de un archivo PDF subido.
    El PDF se valida y se procesa completamente en memoria.

    Args:
        name: Nombre del documento
        file: Archivo PDF subido por el cliente
        service: Servicio de documentos

    Returns:
        Documento creado
    """
    try:
        file_content = await file.read()
        return service.create_document(name, file.filename, file_content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await file.close()


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
    """
    Obtener el texto real de un documento PDF.
    Si el documento ya fue procesado en memoria, devuelve el resultado almacenado.

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
                detail=f"Documento {document_id} no encontrado",
            )
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
