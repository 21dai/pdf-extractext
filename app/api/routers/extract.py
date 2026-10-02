"""Stateless extraction endpoint required by the TP: POST /extract."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.config import settings
from app.core.validators import validate_pdf_size_limit
from app.schemas import ExtractResponse
from app.services import ExtractionService

router = APIRouter(tags=["extraccion"])

# Margen para lo que agrega multipart alrededor del PDF (boundaries y headers
# de cada parte): el limite se aplica al archivo, no al body completo.
MULTIPART_OVERHEAD_BYTES = 64 * 1024

# El endpoint es async para leer el body sin ocupar un hilo, y la extraccion
# (que bloquea) va al threadpool para no frenar el event loop.

_PROBLEM = {"description": "Problem details (RFC 9457)"}


def get_extraction_service() -> ExtractionService:
    """Dependency to obtain the extraction service."""
    return ExtractionService(max_pdf_size_bytes=settings.max_pdf_size_bytes)


async def _read_raw_body(request: Request, max_size_bytes: int) -> bytes:
    """Read the raw body in memory, cutting it off as soon as it exceeds the limit."""
    _reject_declared_size(request, max_size_bytes)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        validate_pdf_size_limit(len(body), max_size_bytes)
    return bytes(body)


async def _read_multipart_file(request: Request, max_size_bytes: int) -> bytes:
    """Read the `file` field of a multipart form."""
    _reject_declared_size(request, max_size_bytes + MULTIPART_OVERHEAD_BYTES)
    async with request.form(max_files=1) as form:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise RequestValidationError(
                [
                    {
                        "type": "missing",
                        "loc": ("body", "file"),
                        "msg": "Field required",
                        "input": None,
                    }
                ]
            )
        return await upload.read()


def _reject_declared_size(request: Request, max_size_bytes: int) -> None:
    """Reject by Content-Length before reading anything, when the client sends it."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit():
        validate_pdf_size_limit(int(declared), max_size_bytes)


@router.post(
    "/extract",
    response_model=ExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extraer el texto de un PDF sin guardarlo",
    responses={400: _PROBLEM, 413: _PROBLEM, 422: _PROBLEM},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Archivo PDF",
                            }
                        },
                    }
                },
            },
        }
    },
)
async def extract(
    request: Request,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractResponse:
    """Extract the content and page count of a PDF.

    Acepta el PDF como body crudo (`application/pdf`, como los scripts de
    carga del TP) o como campo `file` de un multipart. No persiste nada: el
    mismo PDF se puede enviar las veces que haga falta.
    """
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        content = await _read_multipart_file(request, service.max_pdf_size_bytes)
    else:
        content = await _read_raw_body(request, service.max_pdf_size_bytes)

    result = await run_in_threadpool(service.extract, content)
    return ExtractResponse(content=result.text, page_count=result.page_count)
