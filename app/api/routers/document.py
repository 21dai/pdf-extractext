"""Document API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo.database import Database
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_admission_gate
from app.api.uploads import (
    form_file,
    form_text,
    is_multipart,
    missing_field,
    multipart_form,
)
from app.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    InvalidPdfError,
    PdfTooLargeError,
    PdfUnreadableError,
)
from app.core.validators import MAX_PAGINATION_LIMIT
from app.repositories import DocumentRepository
from app.schemas import DocumentResponse, DocumentUpdate
from app.services import DocumentService
from app.services.admission import AdmissionGate
from app.utils.database import get_db

router = APIRouter(prefix="/documents", tags=["documentos"])

# El service usa PyMongo y PDFium, que bloquean: los endpoints son `def` y
# FastAPI los corre en un pool de hilos. El alta es la excepcion: es async para
# leer el upload en memoria (ver app/api/uploads.py) y despues pasa el trabajo
# bloqueante al pool.

_PROBLEM = {"description": "Problem details (RFC 9457)"}


def get_document_service(db: Database = Depends(get_db)) -> DocumentService:
    """Dependency to obtain the document service."""
    repository = DocumentRepository(db)
    return DocumentService(repository, max_pdf_size_bytes=settings.max_pdf_size_bytes)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear y procesar un nuevo documento",
    responses={400: _PROBLEM, 409: _PROBLEM, 413: _PROBLEM, 422: _PROBLEM},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["name", "file"],
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Nombre del documento",
                            },
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Archivo PDF a registrar",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def create_document(
    request: Request,
    service: DocumentService = Depends(get_document_service),
    gate: AdmissionGate = Depends(get_admission_gate),
) -> DocumentResponse:
    """Create a new document from an uploaded PDF.

    El PDF se lee en memoria y con limite de tamano. Comparte la compuerta de
    admision con /extract: si la cola esta llena responde 503 con
    Retry-After antes de leer el PDF. Los errores del PDF (400, 413, 422) los
    traducen los handlers RFC 9457; el resto de las validaciones del service
    responde 400.
    """
    if not is_multipart(request):
        raise missing_field("file")  # sin multipart no puede venir el archivo
    with gate.admit() as ticket:
        async with multipart_form(request, service.max_pdf_size_bytes) as form:
            name = form_text(form, "name")
            content, filename = await form_file(form, "file")
        ticket.body_received()

        async def work() -> DocumentResponse:
            return await run_in_threadpool(
                service.create_document, name, filename, content
            )

        try:
            return await ticket.run(work, request.is_disconnected, cost=len(content))
        except InvalidPdfError, PdfTooLargeError, PdfUnreadableError:
            raise
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )


@router.get(
    "", response_model=List[DocumentResponse], summary="Listar todos los documentos"
)
def list_documents(
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
def get_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Get a document by ID."""
    document = service.get_document(document_id)
    if not document:
        raise DocumentNotFoundError(document_id)
    return document


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Actualizar un documento",
)
def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Update a document."""
    try:
        document = service.update_document(document_id, document_data)
        if not document:
            raise DocumentNotFoundError(document_id)
        return document
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un documento",
)
def delete_document(
    document_id: int, service: DocumentService = Depends(get_document_service)
):
    """Delete a document."""
    success = service.delete_document(document_id)
    if not success:
        raise DocumentNotFoundError(document_id)


@router.post(
    "/{document_id}/extract",
    response_model=DocumentResponse,
    summary="Obtener o completar el texto extraido de un documento",
)
def extract_text(
    document_id: int, service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Get or complete the extracted text of a document.

    CannotReprocessError is translated to HTTP 409 by the registered
    problem details handler.
    """
    document = service.extract_text(document_id)
    if not document:
        raise DocumentNotFoundError(document_id)
    return document
