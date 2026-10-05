"""Stateless extraction endpoint required by the TP: POST /extract."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from python_multipart.exceptions import FormParserError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.config import settings
from app.core.exceptions import InvalidPdfError
from app.core.pdf_extraction import PdfExtraction
from app.core.validators import validate_pdf_size_limit
from app.schemas import ExtractResponse
from app.services import ExtractionService
from app.services.admission import AdmissionGate

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


def get_admission_gate(request: Request) -> AdmissionGate:
    """Dependency to obtain the admission gate of this process."""
    return request.app.state.admission_gate


async def _read_raw_body(request: Request, max_size_bytes: int) -> bytes:
    """Read the raw body in memory, cutting it off as soon as it exceeds the limit."""
    _reject_declared_size(request, max_size_bytes)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        validate_pdf_size_limit(len(body), max_size_bytes)
    return bytes(body)


async def _read_multipart_file(request: Request, max_size_bytes: int) -> bytes:
    """Read the `file` field of a multipart form, keeping it in memory."""
    _reject_declared_size(request, max_size_bytes + MULTIPART_OVERHEAD_BYTES)
    parser = MultiPartParser(
        request.headers, request.stream(), max_files=1, max_fields=10
    )
    # Starlette pasa a un archivo temporal en disco cualquier parte de mas de
    # 1 MB. Con el limite en el tamano maximo del PDF, el archivo queda en
    # memoria: los mas grandes ya se rechazaron por Content-Length.
    parser.spool_max_size = max_size_bytes
    try:
        form = await parser.parse()
    except (MultiPartException, FormParserError) as exc:
        # MultiPartException: limites de Starlette; FormParserError: body que
        # no respeta el formato multipart (lo lanza python-multipart).
        raise InvalidPdfError(f"Multipart invalido: {exc}") from exc

    try:
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
    finally:
        await form.close()


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
    responses={400: _PROBLEM, 413: _PROBLEM, 422: _PROBLEM, 503: _PROBLEM},
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
    gate: AdmissionGate = Depends(get_admission_gate),
) -> ExtractResponse:
    """Extract the content and page count of a PDF.

    Acepta el PDF como body crudo (`application/pdf`, como los scripts de
    carga del TP) o como campo `file` de un multipart. No persiste nada: el
    mismo PDF se puede enviar las veces que haga falta.

    Si la replica ya tiene mas trabajo del que puede terminar a tiempo,
    responde 503 con Retry-After antes de leer el PDF (backpressure).
    """
    with gate.admit() as ticket:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            content = await _read_multipart_file(request, service.max_pdf_size_bytes)
        else:
            content = await _read_raw_body(request, service.max_pdf_size_bytes)

        async def work() -> PdfExtraction:
            return await run_in_threadpool(service.extract, content)

        # El body ya se leyo entero: consultar la desconexion no pierde datos.
        result = await ticket.run(work, request.is_disconnected)
    return ExtractResponse(content=result.text, page_count=result.page_count)
