"""PDF text extraction."""

import codecs
import ctypes
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

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
    pages, page_count = _read_pages(source, lambda textpage: textpage.text().strip())
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


class PdfExtractor(Protocol):
    """Engine that turns PDF bytes into Markdown and a page count.

    El servicio depende de esta interfaz y no de PDFium: otro motor se prueba
    y se mide sin tocar el servicio ni el router.
    """

    def extract(self, source: bytes) -> PdfExtraction:
        """Extract the content as Markdown, raising PdfUnreadableError if it fails."""
        ...


class PdfiumExtractor:
    """Default engine: PDFium, the fastest of the ones measured in the TP."""

    def extract(self, source: bytes) -> PdfExtraction:
        return extract_pdf_markdown(source)


class _TextPage:
    """Text of one PDF page, straight from the PDFium handle.

    pypdfium2 envuelve cada pagina y cada pagina de texto en objetos Python con
    finalizadores (weakref) para cerrarlas solas; con 90 paginas por PDF eso
    era ~10 % del CPU en el perfil. Aca se usan los handles crudos y se cierran
    a mano en `_read_pages`.
    """

    __slots__ = ("handle", "char_count")

    def __init__(self, handle) -> None:
        self.handle = handle
        self.char_count = pdfium_c.FPDFText_CountChars(handle)
        if self.char_count < 0:
            raise RuntimeError("PDFium no pudo contar los caracteres de la pagina")

    def text(self) -> str:
        """Every char of the page, lines separated by CRLF as PDFium returns them."""
        if self.char_count == 0:
            return ""
        # Pagina completa: PDFium escribe a lo sumo count chars mas el NUL final.
        buffer = (ctypes.c_ushort * (self.char_count + 1))()
        written = pdfium_c.FPDFText_GetText(self.handle, 0, self.char_count, buffer)
        if written <= 1:
            return ""
        return codecs.decode(memoryview(buffer)[: written - 1], "utf-16-le", "ignore")


def _read_pages(
    source: bytes, read_page: Callable[[_TextPage], PageResult]
) -> tuple[list[PageResult], int]:
    """Open the PDF and apply `read_page` to the text of each page, under the lock."""
    try:
        with _pdfium_lock:
            document = pdfium.PdfDocument(source)
            try:
                page_count = len(document)
                results = []
                for index in range(page_count):
                    results.append(_read_page(document.raw, index, read_page))
                return results, page_count
            finally:
                document.close()
    except Exception as exc:
        raise PdfUnreadableError(f"Error al extraer el texto: {str(exc)}") from exc


def _read_page(
    document, index: int, read_page: Callable[[_TextPage], PageResult]
) -> PageResult:
    """Load one page and its text, and close both even if reading fails."""
    page = pdfium_c.FPDF_LoadPage(document, index)
    if not page:
        raise RuntimeError(f"PDFium no pudo cargar la pagina {index + 1}")
    try:
        textpage = pdfium_c.FPDFText_LoadPage(page)
        if not textpage:
            raise RuntimeError(f"PDFium no pudo leer el texto de la pagina {index + 1}")
        try:
            return read_page(_TextPage(textpage))
        finally:
            pdfium_c.FPDFText_ClosePage(textpage)
    finally:
        pdfium_c.FPDF_ClosePage(page)


def _page_lines(textpage: _TextPage) -> list[TextLine]:
    """Split the text of a page in lines and measure the height of their letters."""
    lines = []
    offset = 0
    for text in textpage.text().split(_LINE_BREAK):
        height = _line_height(textpage, text, offset)
        lines.append(TextLine(text=text, height=height))
        offset += len(text) + len(_LINE_BREAK)
    return lines


def _line_height(textpage: _TextPage, text: str, offset: int) -> float:
    """Height of the letter closest to the middle of the line.

    Se mide una letra del centro y no el primer caracter: las vinetas y las
    letras capitales son mas grandes que el texto de la linea. Medir una sola
    letra da el mismo Markdown que la mediana de tres en los PDFs de prueba,
    con la mitad del costo extra.
    """
    middle = _letter_near_middle(text)
    if middle is None or offset + middle >= textpage.char_count:
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


def _char_height(textpage: _TextPage, index: int) -> float:
    box = pdfium_c.FS_RECTF()
    if not pdfium_c.FPDFText_GetLooseCharBox(textpage.handle, index, ctypes.byref(box)):
        return 0.0
    return abs(box.top - box.bottom)
