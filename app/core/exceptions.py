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
