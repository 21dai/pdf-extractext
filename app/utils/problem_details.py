"""RFC 9457 Problem Details helpers."""

import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import (
    CannotReprocessError,
    ClientDisconnectedError,
    DocumentNotFoundError,
    InvalidPdfError,
    PdfTooLargeError,
    PdfUnreadableError,
    ServiceOverloadedError,
)

logger = logging.getLogger(__name__)


async def _rejected_pdf_response(
    request: Request, exc: Exception, status_code: int
) -> JSONResponse:
    """Log why /extract rejected the PDF and build its Problem Details."""
    logger.warning("pdf_rechazado", extra={"status": status_code, "detail": str(exc)})
    return await _domain_exception_response(request, exc, status_code)


async def _domain_exception_response(
    request: Request, exc: Exception, status_code: int
) -> JSONResponse:
    """Build a Problem Details response for a domain exception."""
    payload = _problem_details_payload(
        status_code=status_code,
        detail=str(exc),
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
    )


def _status_title(status_code: int) -> str:
    """Return a short title for an HTTP status code."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP Error"


def _problem_details_payload(
    *,
    status_code: int,
    detail: str,
    instance: str,
    errors: Sequence[Any] | None = None,
) -> dict:
    """Build a Problem Details payload."""
    payload: dict[str, object] = {
        "type": "about:blank",
        "title": _status_title(status_code),
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }
    if errors is not None:
        payload["errors"] = errors
    return payload


def register_problem_details_handlers(app: FastAPI) -> None:
    """Register exception handlers that emit RFC 9457 responses."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        payload = _problem_details_payload(
            status_code=exc.status_code,
            detail=detail,
            instance=str(request.url),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        payload = _problem_details_payload(
            status_code=422,
            detail="La solicitud contiene errores de validación.",
            instance=str(request.url),
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content=payload,
            media_type="application/problem+json",
        )

    @app.exception_handler(DocumentNotFoundError)
    async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
        return await _domain_exception_response(request, exc, status.HTTP_404_NOT_FOUND)

    @app.exception_handler(CannotReprocessError)
    async def cannot_reprocess_handler(request: Request, exc: CannotReprocessError):
        return await _domain_exception_response(request, exc, status.HTTP_409_CONFLICT)

    # Los routers del CRUD capturan ValueError y responden 400 ellos mismos;
    # estos handlers aplican a /extract, que deja propagar los errores.
    @app.exception_handler(InvalidPdfError)
    async def invalid_pdf_handler(request: Request, exc: InvalidPdfError):
        return await _rejected_pdf_response(request, exc, status.HTTP_400_BAD_REQUEST)

    @app.exception_handler(PdfTooLargeError)
    async def pdf_too_large_handler(request: Request, exc: PdfTooLargeError):
        return await _rejected_pdf_response(
            request, exc, status.HTTP_413_CONTENT_TOO_LARGE
        )

    @app.exception_handler(PdfUnreadableError)
    async def pdf_unreadable_handler(request: Request, exc: PdfUnreadableError):
        return await _rejected_pdf_response(
            request, exc, status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(ServiceOverloadedError)
    async def service_overloaded_handler(request: Request, exc: ServiceOverloadedError):
        logger.warning(
            "servicio_saturado", extra={"retry_after": exc.retry_after_seconds}
        )
        response = await _domain_exception_response(
            request, exc, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    @app.exception_handler(ClientDisconnectedError)
    async def client_disconnected_handler(
        request: Request, exc: ClientDisconnectedError
    ):
        # Nadie va a leer la respuesta: 499 (Client Closed Request, convencion
        # de nginx) deja el motivo claro en el access log.
        logger.info("cliente_desconectado")
        return Response(status_code=499)
