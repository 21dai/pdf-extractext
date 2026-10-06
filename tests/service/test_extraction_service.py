"""Tests for ExtractionService: validation and the pluggable extraction engine."""

import pytest

from app.core.exceptions import InvalidPdfError, PdfTooLargeError
from app.core.pdf_extraction import PdfExtraction, PdfiumExtractor
from app.services import ExtractionService
from tests.support.pdf import DEFAULT_PDF_TEXT, MINIMAL_PDF_BYTES


class FakeExtractor:
    """Engine that records what it receives and returns a fixed result."""

    def __init__(self) -> None:
        self.received: list[bytes] = []

    def extract(self, source: bytes) -> PdfExtraction:
        self.received.append(source)
        return PdfExtraction(text="# Falso", page_count=7)


class TestEngineIsPluggable:
    """The engine can be swapped without touching the service or the router."""

    def test_uses_the_engine_it_receives(self):
        engine = FakeExtractor()
        service = ExtractionService(max_pdf_size_bytes=1024, extractor=engine)

        result = service.extract(MINIMAL_PDF_BYTES)

        assert result == PdfExtraction(text="# Falso", page_count=7)
        assert engine.received == [MINIMAL_PDF_BYTES]

    def test_uses_pdfium_by_default(self):
        service = ExtractionService(max_pdf_size_bytes=1024)

        assert isinstance(service.extractor, PdfiumExtractor)
        assert DEFAULT_PDF_TEXT in service.extract(MINIMAL_PDF_BYTES).text


class TestValidationRunsBeforeTheEngine:
    """Invalid input never reaches the engine."""

    def test_content_that_is_not_a_pdf_is_rejected(self):
        engine = FakeExtractor()
        service = ExtractionService(max_pdf_size_bytes=1024, extractor=engine)

        with pytest.raises(InvalidPdfError):
            service.extract(b"esto no es un PDF")
        assert engine.received == []

    def test_pdf_over_the_limit_is_rejected(self):
        engine = FakeExtractor()
        limit = len(MINIMAL_PDF_BYTES) - 1
        service = ExtractionService(max_pdf_size_bytes=limit, extractor=engine)

        with pytest.raises(PdfTooLargeError):
            service.extract(MINIMAL_PDF_BYTES)
        assert engine.received == []
