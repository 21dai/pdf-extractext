"""Unit tests for app.core.validators.

They cover the checks POST /extract runs before extracting: size and PDF
signature. All functions are pure (no I/O), so they run fast and in isolation.
"""

import pytest

from app.core.exceptions import InvalidPdfError, PdfTooLargeError
from app.core.validators import validate_pdf_signature, validate_pdf_size


class TestValidatePdfSize:
    def test_valid_size(self):
        content = b"%PDF-1.4 some content"
        assert validate_pdf_size(content, max_size_bytes=1024) is None

    def test_empty_content(self):
        with pytest.raises(ValueError, match="Archivo PDF invalido"):
            validate_pdf_size(b"", max_size_bytes=1024)

    def test_oversized(self):
        content = b"%PDF-1.4 " + b"x" * 1000
        with pytest.raises(ValueError, match="supera el tamano maximo"):
            validate_pdf_size(content, max_size_bytes=500)

    def test_exactly_max_size(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 8)
        assert validate_pdf_size(content, max_size_bytes=max_size) is None

    def test_max_size_minus_one(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 9)
        assert validate_pdf_size(content, max_size_bytes=max_size) is None

    def test_max_size_plus_one(self):
        max_size = 100
        content = b"%PDF-1.4" + b"x" * (max_size - 7)
        with pytest.raises(ValueError, match="supera el tamano maximo"):
            validate_pdf_size(content, max_size_bytes=max_size)


class TestValidatePdfSignature:
    def test_valid_signature(self):
        assert validate_pdf_signature(b"%PDF-1.4") is None

    def test_valid_signature_variation(self):
        assert validate_pdf_signature(b"%PDF-1.7") is None

    def test_missing_signature(self):
        with pytest.raises(ValueError, match="Archivo PDF invalido"):
            validate_pdf_signature(b"this is not a pdf")

    def test_empty_bytes(self):
        with pytest.raises(ValueError, match="Archivo PDF invalido"):
            validate_pdf_signature(b"")

    def test_signature_at_wrong_position(self):
        # signature not at start
        with pytest.raises(ValueError, match="Archivo PDF invalido"):
            validate_pdf_signature(b"prefix%PDF-1.4")

    def test_partial_signature(self):
        with pytest.raises(ValueError, match="Archivo PDF invalido"):
            validate_pdf_signature(b"%PDF")  # missing the dash


class TestPdfValidationErrorTypes:
    def test_oversized_raises_pdf_too_large(self):
        with pytest.raises(PdfTooLargeError):
            validate_pdf_size(b"%PDF-1.4" + b"x" * 100, max_size_bytes=50)

    def test_empty_content_raises_invalid_pdf(self):
        with pytest.raises(InvalidPdfError):
            validate_pdf_size(b"", max_size_bytes=50)

    def test_missing_signature_raises_invalid_pdf(self):
        with pytest.raises(InvalidPdfError):
            validate_pdf_signature(b"this is not a pdf")
