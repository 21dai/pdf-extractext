"""RFC 9457 Problem Details helpers."""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import CannotReprocessError, DocumentNotFoundError


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
    async def document_not_found_handler(
        request: Request, exc: DocumentNotFoundError
    ):
        return await _domain_exception_response(
            request, exc, status.HTTP_404_NOT_FOUND
        )

    @app.exception_handler(CannotReprocessError)
    async def cannot_reprocess_handler(request: Request, exc: CannotReprocessError):
        return await _domain_exception_response(
            request, exc, status.HTTP_409_CONFLICT
        )
