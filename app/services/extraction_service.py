"""Stateless extraction service behind POST /extract."""

import logging
import time

from app.core.pdf_extraction import PdfExtraction, PdfExtractor
from app.core.validators import validate_pdf_signature, validate_pdf_size

logger = logging.getLogger(__name__)


class ExtractionService:
    """Validate a PDF and extract its content, without persisting anything.

    No calcula checksum, no busca duplicados ni guarda el documento: eso lo
    hace document-store, coordinado por el orquestador (ADR-0008). Por eso
    puede escalar en replicas sin estado compartido (12-Factor VI).
    """

    def __init__(self, max_pdf_size_bytes: int, extractor: PdfExtractor):
        """Initialize the service.

        Args:
            max_pdf_size_bytes: Largest PDF accepted, in bytes
            extractor: Extraction engine; the one the composition root chose
        """
        self.max_pdf_size_bytes = max_pdf_size_bytes
        self.extractor = extractor

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
