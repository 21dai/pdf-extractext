"""Reusable pure validators for the PDFs that POST /extract receives.

All functions are stateless and raise a domain error with a clear message on
failure.
"""

from app.core.exceptions import InvalidPdfError, PdfTooLargeError


# ---------------------------------------------------------------------------
# PDF size
# ---------------------------------------------------------------------------
def validate_pdf_size(file_content: bytes, max_size_bytes: int) -> None:
    """Validate that the uploaded content is within the allowed size.

    Args:
        file_content: Raw bytes of the uploaded file.
        max_size_bytes: Maximum permitted size in bytes.

    Raises:
        InvalidPdfError: If the file is empty.
        PdfTooLargeError: If the file exceeds the size limit.
    """
    file_size = len(file_content)

    if file_size == 0:
        raise InvalidPdfError("Archivo PDF invalido")

    validate_pdf_size_limit(file_size, max_size_bytes)


def validate_pdf_size_limit(size_bytes: int, max_size_bytes: int) -> None:
    """Validate a size in bytes against the limit, before reading the content.

    Lets the API reject an upload by its declared Content-Length without
    loading it into memory.

    Args:
        size_bytes: Size of the content in bytes.
        max_size_bytes: Maximum permitted size in bytes.

    Raises:
        PdfTooLargeError: If the size exceeds the limit.
    """
    if size_bytes > max_size_bytes:
        raise PdfTooLargeError(
            f"El PDF supera el tamano maximo permitido de {max_size_bytes} bytes"
        )


# ---------------------------------------------------------------------------
# PDF magic signature
# ---------------------------------------------------------------------------
PDF_SIGNATURE = b"%PDF-"


def validate_pdf_signature(file_content: bytes) -> None:
    """Ensure the content starts with the PDF magic signature.

    Args:
        file_content: Raw bytes of the uploaded file.

    Raises:
        InvalidPdfError: If the content does not start with the PDF signature.
    """
    if not file_content.startswith(PDF_SIGNATURE):
        raise InvalidPdfError("Archivo PDF invalido")
