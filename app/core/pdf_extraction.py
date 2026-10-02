"""PDF text extraction."""

import threading
from dataclasses import dataclass

import pypdfium2 as pdfium

from app.core.exceptions import PdfUnreadableError

# PDFium no es thread-safe: dos hilos del mismo proceso no pueden usarlo a la
# vez. Los endpoints sincronicos corren en el threadpool de FastAPI, asi que
# se serializa la extraccion dentro de cada proceso. El paralelismo real viene
# de los workers de uvicorn (WEB_CONCURRENCY), que son procesos distintos.
_pdfium_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    """Result of reading a PDF: its text and how many pages it has."""

    text: str
    page_count: int


def extract_pdf(source: bytes) -> PdfExtraction:
    """Extract the text and the page count from PDF bytes using pypdfium2.

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
    try:
        with _pdfium_lock:
            document = pdfium.PdfDocument(source)
            try:
                page_texts = []
                for page in document:
                    textpage = page.get_textpage()
                    text = textpage.get_text_range().strip()
                    # Cerrar dentro del lock: si lo hace el recolector de
                    # basura, PDFium se usaria desde otro hilo sin proteccion.
                    textpage.close()
                    page.close()
                    if text:
                        page_texts.append(text)
                return PdfExtraction(
                    text="\n\n".join(page_texts), page_count=len(document)
                )
            finally:
                document.close()
    except Exception as exc:
        raise PdfUnreadableError(f"Error al extraer el texto: {str(exc)}") from exc


def extract_pdf_text(source: bytes) -> str:
    """Extract only the text from PDF bytes (see `extract_pdf`)."""
    return extract_pdf(source).text
