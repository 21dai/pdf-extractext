"""PDF text extraction."""

from io import BytesIO


def extract_pdf_text(source: bytes) -> str:
    """Extract text from PDF bytes using pypdf.

    Args:
        source: PDF file content as bytes

    Returns:
        Extracted text with normalized page separation
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError(
            "La dependencia de extraccion de PDF no esta instalada"
        ) from exc

    try:
        reader = PdfReader(BytesIO(source))
        page_texts = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                page_texts.append(text)
        return "\n\n".join(page_texts)
    except Exception as exc:
        raise ValueError(f"Error al extraer el texto: {str(exc)}") from exc
