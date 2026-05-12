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
            f"El nombre del documento no debe superar los {MAX_DOCUMENT_NAME_LENGTH} caracteres"
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
            f"El nombre del archivo no debe superar los {MAX_ORIGINAL_FILENAME_LENGTH} caracteres"
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


def validate_unique_checksum(checksum: str, *, existing_document: object | None) -> None:
    """Validate that a checksum does not already exist in the store.

    Args:
        checksum: The checksum to validate.
        existing_document: Result of a repository lookup by checksum,
            or None if no document exists.

    Raises:
        ValueError: If a document with the same checksum already exists.
    """
    if existing_document is not None:
        raise ValueError("Ya existe un documento con el mismo checksum")


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


# ---------------------------------------------------------------------------
# Document ID
# ---------------------------------------------------------------------------
def validate_document_id(document_id: int) -> int:
    """Validate that a document ID is a positive integer.

    Args:
        document_id: The ID to validate.

    Returns:
        The validated ID.

    Raises:
        ValueError: If the ID is not a positive integer.
    """
    if not isinstance(document_id, int) or document_id <= 0:
        raise ValueError("El ID del documento debe ser un entero positivo")
    return document_id


# ---------------------------------------------------------------------------
# Legacy file path validation (kept for extract_text path)
# ---------------------------------------------------------------------------
def validate_pdf_file_on_disk(file_path, expected_size: int, max_size_bytes: int) -> None:
    """Validate that the given path points to a stored PDF file with a valid size.

    Args:
        file_path: Path to the file on disk.
        expected_size: Expected size in bytes from the database record.
        max_size_bytes: Maximum permitted size in bytes.

    Raises:
        ValueError: If the file does not exist, is not a PDF, or size is invalid.
    """
    if not file_path.is_file():
        raise ValueError(f"Archivo no encontrado: {file_path}")

    if file_path.suffix.lower() != ".pdf":
        raise ValueError("Solo se permiten archivos PDF")

    actual_size = file_path.stat().st_size
    if actual_size != expected_size:
        raise ValueError(
            f"Tamanio de archivo incorrecto: esperado {expected_size} bytes, encontrado {actual_size}"
        )

    if actual_size > max_size_bytes:
        raise ValueError(
            f"El PDF supera el tamano maximo permitido de {max_size_bytes} bytes"
        )

    with file_path.open("rb") as pdf_file:
        if pdf_file.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
            raise ValueError("Archivo PDF invalido")
