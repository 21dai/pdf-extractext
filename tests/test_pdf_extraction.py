"""Direct tests for the public PDF text extraction interface."""

from app.core.pdf_extraction import extract_pdf_text
from tests.support.pdf import build_pdf_bytes


def test_extract_pdf_text_returns_embedded_text():
    """Test extraction returns the text embedded in the PDF bytes."""
    original_text = "Clausula primera del contrato"

    assert extract_pdf_text(build_pdf_bytes(original_text)) == original_text


def test_extract_pdf_text_returns_empty_string_when_no_text_extractable():
    """Test extraction returns empty string for a PDF without text."""
    assert extract_pdf_text(build_pdf_bytes("")) == ""
