"""Domain exceptions raised by the business layer."""


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
