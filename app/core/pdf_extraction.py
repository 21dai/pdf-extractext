"""PDF text extraction."""

import ctypes
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.core.exceptions import PdfUnreadableError
from app.core.markdown import TextLine, to_markdown

# PDFium no es thread-safe: dos hilos del mismo proceso no pueden usarlo a la
# vez. Los endpoints sincronicos corren en el threadpool de FastAPI, asi que
# se serializa la extraccion dentro de cada proceso. El paralelismo real viene
# de los workers de uvicorn (WEB_CONCURRENCY), que son procesos distintos.
_pdfium_lock = threading.Lock()

# PDFium separa las lineas de una pagina con CRLF.
_LINE_BREAK = "\r\n"

PageResult = TypeVar("PageResult")


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    """Result of reading a PDF: its text and how many pages it has."""

    text: str
    page_count: int


def extract_pdf(source: bytes) -> PdfExtraction:
    """Extract the plain text and the page count from PDF bytes using pypdfium2.

    pypdfium2 envuelve PDFium (el motor de Chrome): en los PDFs de prueba
    extrae el mismo texto que pypdf entre 10 y 20 veces mas rapido, y su
    licencia (Apache/BSD) es compatible con el proyecto.

    Args:
        source: PDF file content as bytes

    Returns:
        Text of every page with normalized separation, and the page count

    Raises:
        PdfUnreadableError: If PDFium cannot open or read the document.
    """
    pages, page_count = _read_pages(
        source, lambda textpage: textpage.get_text_range().strip()
    )
    text = "\n\n".join(page for page in pages if page)
    return PdfExtraction(text=text, page_count=page_count)


def extract_pdf_markdown(source: bytes) -> PdfExtraction:
    """Extract the content of PDF bytes as Markdown, and the page count.

    Ademas del texto, mide la altura de las letras de cada linea para que
    `to_markdown` reconozca los titulos.

    Raises:
        PdfUnreadableError: If PDFium cannot open or read the document.
    """
    pages, page_count = _read_pages(source, _page_lines)
    return PdfExtraction(text=to_markdown(pages), page_count=page_count)


def extract_pdf_text(source: bytes) -> str:
    """Extract only the plain text from PDF bytes (see `extract_pdf`)."""
    return extract_pdf(source).text


def _read_pages(
    source: bytes, read_page: Callable[[pdfium.PdfTextPage], PageResult]
) -> tuple[list[PageResult], int]:
    """Open the PDF and apply `read_page` to the text of each page, under the lock."""
    try:
        with _pdfium_lock:
            document = pdfium.PdfDocument(source)
            try:
                results = []
                for page in document:
                    textpage = page.get_textpage()
                    results.append(read_page(textpage))
                    # Cerrar dentro del lock: si lo hace el recolector de
                    # basura, PDFium se usaria desde otro hilo sin proteccion.
                    textpage.close()
                    page.close()
                return results, len(document)
            finally:
                document.close()
    except Exception as exc:
        raise PdfUnreadableError(f"Error al extraer el texto: {str(exc)}") from exc


def _page_lines(textpage: pdfium.PdfTextPage) -> list[TextLine]:
    """Split the text of a page in lines and measure the height of their letters."""
    char_count = textpage.count_chars()
    lines = []
    offset = 0
    for text in textpage.get_text_range().split(_LINE_BREAK):
        height = _line_height(textpage, text, offset, char_count)
        lines.append(TextLine(text=text, height=height))
        offset += len(text) + len(_LINE_BREAK)
    return lines


def _line_height(
    textpage: pdfium.PdfTextPage, text: str, offset: int, char_count: int
) -> float:
    """Height of the letter closest to the middle of the line.

    Se mide una letra del centro y no el primer caracter: las vinetas y las
    letras capitales son mas grandes que el texto de la linea. Medir una sola
    letra da el mismo Markdown que la mediana de tres en los PDFs de prueba,
    con la mitad del costo extra.
    """
    middle = _letter_near_middle(text)
    if middle is None or offset + middle >= char_count:
        return 0.0
    return _char_height(textpage, offset + middle)


def _letter_near_middle(text: str) -> int | None:
    """Index of the letter or digit closest to the middle, searching outwards."""
    middle = len(text) // 2
    for distance in range(middle + 1):
        for index in (middle + distance, middle - distance):
            if 0 <= index < len(text) and text[index].isalnum():
                return index
    return None


def _char_height(textpage: pdfium.PdfTextPage, index: int) -> float:
    box = pdfium_c.FS_RECTF()
    if not pdfium_c.FPDFText_GetLooseCharBox(textpage.raw, index, ctypes.byref(box)):
        return 0.0
    return abs(box.top - box.bottom)
