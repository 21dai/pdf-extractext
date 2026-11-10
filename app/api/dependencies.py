"""Dependencies shared by the routers."""

from fastapi import Request

from app.core.pdf_extraction import PdfExtractor
from app.services.admission import AdmissionGate


def get_admission_gate(request: Request) -> AdmissionGate:
    """Admission gate of this process: every PDF extraction goes through it.

    PDFium no es thread-safe: cada proceso extrae un PDF por vez, y la
    compuerta ordena la cola y rechaza con 503 lo que no llegaria a tiempo.
    """
    return request.app.state.admission_gate


def get_pdf_extractor(request: Request) -> PdfExtractor:
    """Extraction engine of this process, chosen in the composition root."""
    return request.app.state.pdf_extractor
