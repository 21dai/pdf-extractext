"""API routers"""

from .document import router as document_router
from .extract import router as extract_router

__all__ = ["document_router", "extract_router"]
