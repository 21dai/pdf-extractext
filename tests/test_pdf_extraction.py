"""Direct tests for the public PDF text extraction interface.

La extraccion devuelve el contenido como Markdown: los titulos se reconstruyen
midiendo la altura de las letras (ver app/core/markdown.py). No hay un camino
de texto plano: con el CRUD retirado (ADR-0008) nada lo consume.
"""

import pytest

from app.core.exceptions import PdfUnreadableError
from app.core.pdf_extraction import PdfiumExtractor, extract_pdf
from tests.support.pdf import build_pdf_bytes, build_pdf_with_lines


def test_extract_pdf_returns_the_content_as_markdown():
    """Test the extraction returns a PDF with a title, a section and body text."""
    source = build_pdf_with_lines(
        [
            ("Informe anual", 24),
            ("Este es el cuerpo del informe con varias palabras", 12),
            ("Resultados", 18),
            ("Los resultados fueron buenos para todo el equipo", 12),
        ]
    )

    result = extract_pdf(source)

    assert result.page_count == 1
    assert result.text == (
        "# Informe anual\n\n"
        "Este es el cuerpo del informe con varias palabras\n\n"
        "## Resultados\n\n"
        "Los resultados fueron buenos para todo el equipo"
    )


def test_extract_pdf_returns_an_empty_content_when_the_pdf_has_no_text():
    """Test a PDF without text extracts to an empty content."""
    result = extract_pdf(build_pdf_bytes(""))

    assert result.text == ""
    assert result.page_count == 1


def test_extract_pdf_raises_unreadable_error_for_corrupt_pdf():
    """Test a PDF the engine cannot open raises a domain error, still a ValueError."""
    corrupt = b"%PDF-1.4\n" + b"\x00basura" * 50

    with pytest.raises(PdfUnreadableError):
        extract_pdf(corrupt)

    with pytest.raises(ValueError):
        extract_pdf(corrupt)


def test_the_pdfium_engine_returns_the_same_content_as_the_extraction():
    """Test the default engine is the one behind the extraction."""
    source = build_pdf_with_lines([("Titulo", 24), ("Cuerpo del texto", 12)])

    result = PdfiumExtractor().extract(source)

    assert result.text == extract_pdf(source).text
    assert result.page_count == 1
