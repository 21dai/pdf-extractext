"""Reading of uploaded PDFs in memory, cut off as soon as they exceed the limit.

Lo usan los dos routers que reciben PDFs (`/extract` y el alta de documentos):

- El PDF nunca se escribe a disco (requisito 8): Starlette pasa a un archivo
  temporal las partes de un multipart de mas de 1 MB; aca el umbral es el
  tamano maximo aceptado, asi que todo lo que se acepta queda en memoria.
- Un body demasiado grande se rechaza con 413 sin leerlo entero: por
  `Content-Length` si el cliente lo manda, y si no, apenas se pasa del limite.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from python_multipart.exceptions import FormParserError
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.core.exceptions import InvalidPdfError
from app.core.validators import validate_pdf_size_limit

# Margen para lo que agrega multipart alrededor del PDF (boundaries, headers de
# cada parte y los campos de texto): el limite se aplica al archivo.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def reject_declared_size(request: Request, max_size_bytes: int) -> None:
    """Reject by Content-Length before reading anything, when the client sends it."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit():
        validate_pdf_size_limit(int(declared), max_size_bytes)


async def _limited(
    stream: AsyncIterator[bytes], max_size_bytes: int
) -> AsyncGenerator[bytes, None]:
    """Pass the chunks through, raising PdfTooLargeError past the limit."""
    received = 0
    async for chunk in stream:
        received += len(chunk)
        validate_pdf_size_limit(received, max_size_bytes)
        yield chunk


async def read_raw_body(request: Request, max_size_bytes: int) -> bytes:
    """Read the raw body in memory, cutting it off as soon as it exceeds the limit."""
    reject_declared_size(request, max_size_bytes)
    body = bytearray()
    async for chunk in _limited(request.stream(), max_size_bytes):
        body.extend(chunk)
    return bytes(body)


@asynccontextmanager
async def multipart_form(
    request: Request, max_file_bytes: int
) -> AsyncIterator[FormData]:
    """Parse a multipart form in memory and close it when the block ends.

    Raises:
        PdfTooLargeError: If the body exceeds the file limit plus the overhead.
        InvalidPdfError: If the body is not a valid multipart form.
    """
    limit = max_file_bytes + MULTIPART_OVERHEAD_BYTES
    reject_declared_size(request, limit)
    parser = MultiPartParser(
        request.headers,
        _limited(request.stream(), limit),
        max_files=1,
        max_fields=10,
    )
    # Ninguna parte supera el limite (lo corta _limited): todas quedan en memoria.
    parser.spool_max_size = limit
    try:
        form = await parser.parse()
    except (MultiPartException, FormParserError) as exc:
        # MultiPartException: limites de Starlette; FormParserError: body que
        # no respeta el formato multipart (lo lanza python-multipart).
        raise InvalidPdfError(f"Multipart invalido: {exc}") from exc
    try:
        yield form
    finally:
        await form.close()


async def form_file(form: FormData, field: str) -> tuple[bytes, str | None]:
    """Content and filename of a file field, or a 422 if it is missing."""
    upload = form.get(field)
    if not isinstance(upload, UploadFile):
        raise missing_field(field)
    return await upload.read(), upload.filename


def form_text(form: FormData, field: str) -> str:
    """Value of a text field, or a 422 if it is missing."""
    value = form.get(field)
    if not isinstance(value, str):
        raise missing_field(field)
    return value


def is_multipart(request: Request) -> bool:
    """Whether the body is a multipart form."""
    return request.headers.get("content-type", "").startswith("multipart/form-data")


def missing_field(field: str) -> RequestValidationError:
    """422 for a required field that is not in the request, like FastAPI."""
    return RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", field),
                "msg": "Field required",
                "input": None,
            }
        ]
    )
