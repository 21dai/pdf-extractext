"""Stateless extraction service behind POST /extract."""

import logging
import time

from app.core.pdf_extraction import PdfExtraction, PdfExtractor, PdfiumExtractor
from app.core.validators import validate_pdf_signature, validate_pdf_size

logger = logging.getLogger(__name__)


class ExtractionService:
    """Validate a PDF and extract its content, without persisting anything.

    A diferencia de DocumentService, no usa repositorio: no calcula checksum,
    no busca duplicados y no escribe en MongoDB. Por eso puede escalar en
    replicas sin estado compartido (12-Factor VI).
    """

    def __init__(self, max_pdf_size_bytes: int, extractor: PdfExtractor | None = None):
        """Initialize the service.

        Args:
            max_pdf_size_bytes: Largest PDF accepted, in bytes
            extractor: Extraction engine; PDFium if not given
        """
        self.max_pdf_size_bytes = max_pdf_size_bytes
        self.extractor = extractor or PdfiumExtractor()

    def extract(self, content: bytes) -> PdfExtraction:
        """Validate the PDF bytes and extract their content as Markdown.

        Raises:
            InvalidPdfError: If the content is empty or is not a PDF.
            PdfTooLargeError: If the content exceeds the size limit.
            PdfUnreadableError: If the engine cannot read the PDF.
        """
        validate_pdf_size(content, self.max_pdf_size_bytes)
        validate_pdf_signature(content)
        started = time.perf_counter()
        result = self.extractor.extract(content)
        logger.info(
            "pdf_extraido",
            extra={
                "bytes": len(content),
                "page_count": result.page_count,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return result
