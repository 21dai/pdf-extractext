"""Reusable pure validators for the document domain.

All functions are stateless, raise ValueError with a clear message on failure,
and return a validated/transformed value on success.
"""

import hashlib
from pathlib import Path

MAX_DOCUMENT_NAME_LENGTH = 255
MAX_ORIGINAL_FILENAME_LENGTH = 255
MAX_PAGINATION_LIMIT = 100


# ---------------------------------------------------------------------------
# Document name
# ---------------------------------------------------------------------------
def validate_document_name(name: str | None) -> str:
    """Validate and normalize a document name.

    Args:
        name: Raw name from the client.

    Returns:
        Stripped, validated name.

    Raises:
        ValueError: When name is missing, blank, or exceeds length limits.
    """
    if name is None:
        raise ValueError("El nombre del documento es obligatorio")

    if not isinstance(name, str):
        raise ValueError("El nombre del documento debe ser una cadena de texto")

    normalized = name.strip()
    if not normalized:
        raise ValueError("El nombre del documento es obligatorio")

    if len(normalized) > MAX_DOCUMENT_NAME_LENGTH:
        raise ValueError(
            "El nombre del documento no debe superar los "
            f"{MAX_DOCUMENT_NAME_LENGTH} caracteres"
        )

    return normalized


# ---------------------------------------------------------------------------
# Original filename
# ---------------------------------------------------------------------------
def validate_original_filename(original_filename: str | None) -> str:
    """Sanitize and validate the uploaded original filename.

    Args:
        original_filename: Raw filename from the client upload.

    Returns:
        Normalized filename preserving only the basename.

    Raises:
        ValueError: When filename is missing or becomes empty after sanitisation.
    """
    if not original_filename:
        raise ValueError("Se requiere un archivo PDF")

    normalized = Path(original_filename).name.strip()
    if not normalized:
        raise ValueError("Se requiere un archivo PDF")

    if len(normalized) > MAX_ORIGINAL_FILENAME_LENGTH:
        raise ValueError(
            "El nombre del archivo no debe superar los "
            f"{MAX_ORIGINAL_FILENAME_LENGTH} caracteres"
        )

    return normalized


# ---------------------------------------------------------------------------
# PDF extension
# ---------------------------------------------------------------------------
def validate_pdf_extension(filename: str) -> None:
    """Ensure the filename has a .pdf extension.

    Args:
        filename: Filename to validate.

    Raises:
        ValueError: If the extension is not .pdf.
    """
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise ValueError("Solo se permiten archivos PDF")


# ---------------------------------------------------------------------------
# PDF size
# ---------------------------------------------------------------------------
def validate_pdf_size(file_content: bytes, max_size_bytes: int) -> None:
    """Validate that the uploaded content is within the allowed size.

    Args:
        file_content: Raw bytes of the uploaded file.
        max_size_bytes: Maximum permitted size in bytes.

    Raises:
        ValueError: If the file is empty or exceeds the size limit.
    """
    file_size = len(file_content)

    if file_size == 0:
        raise ValueError("Archivo PDF invalido")

    if file_size > max_size_bytes:
        raise ValueError(
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
        ValueError: If the content does not start with the PDF signature.
    """
    if not file_content.startswith(PDF_SIGNATURE):
        raise ValueError("Archivo PDF invalido")


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------
def calculate_checksum(file_content: bytes) -> str:
    """Calculate SHA-256 checksum of raw bytes.

    Args:
        file_content: Raw file bytes.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(file_content).hexdigest()


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
def validate_pagination(skip: int, limit: int) -> tuple[int, int]:
    """Sanitize and validate pagination parameters.

    Args:
        skip: Number of records to skip.
        limit: Maximum number of records to return.

    Returns:
        Validated (skip, limit) tuple.

    Raises:
        ValueError: If skip or limit are negative, or limit exceeds the maximum.
    """
    if not isinstance(skip, int) or skip < 0:
        raise ValueError("skip debe ser un entero no negativo")

    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit debe ser un entero positivo")

    if limit > MAX_PAGINATION_LIMIT:
        limit = MAX_PAGINATION_LIMIT

    return skip, limit
