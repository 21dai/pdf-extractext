"""Stateless extraction service behind POST /extract."""

from app.core.pdf_extraction import PdfExtraction, extract_pdf_markdown
from app.core.validators import validate_pdf_signature, validate_pdf_size


class ExtractionService:
    """Validate a PDF and extract its content, without persisting anything.

    A diferencia de DocumentService, no usa repositorio: no calcula checksum,
    no busca duplicados y no escribe en MongoDB. Por eso puede escalar en
    replicas sin estado compartido (12-Factor VI).
    """

    def __init__(self, max_pdf_size_bytes: int):
        """Initialize the service.

        Args:
            max_pdf_size_bytes: Largest PDF accepted, in bytes
        """
        self.max_pdf_size_bytes = max_pdf_size_bytes

    def extract(self, content: bytes) -> PdfExtraction:
        """Validate the PDF bytes and extract their content as Markdown.

        Raises:
            InvalidPdfError: If the content is empty or is not a PDF.
            PdfTooLargeError: If the content exceeds the size limit.
            PdfUnreadableError: If the engine cannot read the PDF.
        """
        validate_pdf_size(content, self.max_pdf_size_bytes)
        validate_pdf_signature(content)
        return extract_pdf_markdown(content)
