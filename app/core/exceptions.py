"""Domain exceptions raised by the business layer."""

CANNOT_REPROCESS_MESSAGE = (
    "La API procesa el PDF solo en el upload y no lo guarda en disco, "
    "por lo que no puede reprocesar."
)


class DocumentNotFoundError(Exception):
    """Raised when a document does not exist."""

    def __init__(self, document_id: int):
        """Initialize with the missing document ID.

        Args:
            document_id: Document ID that was not found
        """
        super().__init__(f"Documento {document_id} no encontrado")


class CannotReprocessError(ValueError):
    """Raised when a document cannot be reprocessed.

    Subclasses ValueError so existing call sites that catch validation
    errors keep working.
    """

    def __init__(self, detail: str = CANNOT_REPROCESS_MESSAGE):
        """Initialize with an explanatory detail message.

        Args:
            detail: Human-readable reason why reprocessing is not possible
        """
        super().__init__(detail)


class DuplicateDocumentError(Exception):
    """A document with the same content (checksum) already exists: 409."""

    def __init__(self) -> None:
        super().__init__("Ya existe un documento con el mismo checksum")


class InvalidPdfError(ValueError):
    """Raised when the uploaded content is empty or is not a PDF."""


class PdfTooLargeError(ValueError):
    """Raised when the uploaded PDF exceeds the configured size limit."""


class PdfUnreadableError(ValueError):
    """Raised when the content looks like a PDF but the engine cannot read it."""


class ServiceOverloadedError(Exception):
    """Raised when a request would wait longer than allowed: reject it now."""

    def __init__(self, retry_after_seconds: int):
        """Initialize with how many seconds the client should wait to retry.

        Args:
            retry_after_seconds: Value for the Retry-After header
        """
        super().__init__(
            "El servicio esta saturado: la espera superaria el tiempo maximo. "
            f"Reintentar en {retry_after_seconds} s."
        )
        self.retry_after_seconds = retry_after_seconds


class ClientDisconnectedError(Exception):
    """Raised when the client left before its turn: its work is skipped."""
