"""Direct tests for the public PDF text extraction interface."""

import pytest

from app.core.exceptions import PdfUnreadableError
from app.core.pdf_extraction import extract_pdf, extract_pdf_text
from tests.support.pdf import build_pdf_bytes


def test_extract_pdf_text_returns_embedded_text():
    """Test extraction returns the text embedded in the PDF bytes."""
    original_text = "Clausula primera del contrato"

    assert extract_pdf_text(build_pdf_bytes(original_text)) == original_text


def test_extract_pdf_text_returns_empty_string_when_no_text_extractable():
    """Test extraction returns empty string for a PDF without text."""
    assert extract_pdf_text(build_pdf_bytes("")) == ""


def test_extract_pdf_reports_text_and_page_count():
    """Test the structured extraction returns the text and the number of pages."""
    result = extract_pdf(build_pdf_bytes("Primera pagina"))

    assert result.text == "Primera pagina"
    assert result.page_count == 1


def test_extract_pdf_raises_unreadable_error_for_corrupt_pdf():
    """Test a PDF the engine cannot open raises a domain error, still a ValueError."""
    corrupt = b"%PDF-1.4\n" + b"\x00basura" * 50

    with pytest.raises(PdfUnreadableError):
        extract_pdf(corrupt)

    with pytest.raises(ValueError):
        extract_pdf_text(corrupt)
