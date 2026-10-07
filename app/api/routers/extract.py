"""Stateless extraction endpoint required by the TP: POST /extract."""

from fastapi import APIRouter, Depends, Request, status
from starlette.concurrency import run_in_threadpool

from app.api.uploads import form_file, is_multipart, multipart_form, read_raw_body
from app.config import settings
from app.core.pdf_extraction import PdfExtraction
from app.schemas import ExtractResponse
from app.services import ExtractionService
from app.services.admission import AdmissionGate

router = APIRouter(tags=["extraccion"])

# El endpoint es async para leer el body sin ocupar un hilo, y la extraccion
# (que bloquea) va al threadpool para no frenar el event loop.

_PROBLEM = {"description": "Problem details (RFC 9457)"}


def get_extraction_service() -> ExtractionService:
    """Dependency to obtain the extraction service."""
    return ExtractionService(max_pdf_size_bytes=settings.max_pdf_size_bytes)


def get_admission_gate(request: Request) -> AdmissionGate:
    """Dependency to obtain the admission gate of this process."""
    return request.app.state.admission_gate


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
        if is_multipart(request):
            async with multipart_form(request, service.max_pdf_size_bytes) as form:
                content, _ = await form_file(form, "file")
        else:
            content = await read_raw_body(request, service.max_pdf_size_bytes)
        ticket.body_received()

        async def work() -> PdfExtraction:
            return await run_in_threadpool(service.extract, content)

        # El body ya se leyo entero: consultar la desconexion no pierde datos.
        # El tamano estima el costo: con la cola por tamano sale primero el
        # PDF mas liviano.
        result = await ticket.run(work, request.is_disconnected, cost=len(content))
    return ExtractResponse(content=result.text, page_count=result.page_count)
