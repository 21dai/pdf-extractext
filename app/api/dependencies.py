"""Dependencies shared by the routers."""

from fastapi import Request

from app.services.admission import AdmissionGate


def get_admission_gate(request: Request) -> AdmissionGate:
    """Admission gate of this process: every PDF extraction goes through it.

    PDFium no es thread-safe: cada proceso extrae un PDF por vez. Los dos
    endpoints que extraen (`/extract` y el alta de documentos) comparten la
    misma cola, asi un pico en uno no deja sin turnos al otro (Bulkhead).
    """
    return request.app.state.admission_gate
