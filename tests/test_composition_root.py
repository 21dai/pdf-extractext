"""Tests for the composition root: the parts the app wires together.

El motor de extraccion se elige aqui, en un solo lugar. El router lo recibe
por dependencia: si lo creara el mismo, cada endpoint tendria su motor y
cambiarlo seria editar el router.
"""

from fastapi.testclient import TestClient

from app.core.pdf_extraction import PdfiumExtractor


def test_the_composition_root_chooses_the_extraction_engine(client: TestClient):
    """Test the composition root picks the extraction engine of the process."""
    assert isinstance(client.app.state.pdf_extractor, PdfiumExtractor)
