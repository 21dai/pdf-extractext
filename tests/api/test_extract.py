"""Tests for POST /extract, the stateless extraction contract of the TP."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.support.pdf import DEFAULT_PDF_TEXT, MINIMAL_PDF_BYTES

STRESS_PDFS = Path(__file__).resolve().parents[1] / "stress" / "pdfs"


def post_raw(client: TestClient, content: bytes, content_type="application/pdf"):
    """Send the PDF as the raw request body, like the TP load scripts."""
    return client.post(
        "/extract", content=content, headers={"Content-Type": content_type}
    )


def post_multipart(client: TestClient, content: bytes, filename="documento.pdf"):
    """Send the PDF as the `file` field of a multipart form."""
    return client.post(
        "/extract", files={"file": (filename, content, "application/pdf")}
    )


class TestExtractSuccess:
    """A valid PDF returns 200 with the content and the page count."""

    def test_raw_body_returns_content_and_page_count(self, client: TestClient):
        response = post_raw(client, MINIMAL_PDF_BYTES)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        body = response.json()
        assert set(body) == {"content", "page_count"}
        assert DEFAULT_PDF_TEXT in body["content"]
        assert body["page_count"] == 1

    def test_multipart_file_returns_content_and_page_count(self, client: TestClient):
        response = post_multipart(client, MINIMAL_PDF_BYTES)

        assert response.status_code == 200
        body = response.json()
        assert DEFAULT_PDF_TEXT in body["content"]
        assert body["page_count"] == 1

    def test_raw_body_is_accepted_without_pdf_content_type(self, client: TestClient):
        """The PDF signature decides, not the header (curl sends form-urlencoded)."""
        response = post_raw(client, MINIMAL_PDF_BYTES, "application/octet-stream")

        assert response.status_code == 200

    @pytest.mark.parametrize(
        ("filename", "pages"),
        [
            ("2020-Scrum-Guide-Spanish-Latin-South-American.pdf", 16),
            ("Essential-Kanban-Condensed-Spanish.pdf", 90),
            ("Filosofia Lean.pdf", 42),
            ("scrum_manager_historias_usuario.pdf", 62),
        ],
    )
    def test_official_stress_pdfs_report_their_page_count(
        self, client: TestClient, filename: str, pages: int
    ):
        response = post_raw(client, (STRESS_PDFS / filename).read_bytes())

        assert response.status_code == 200
        body = response.json()
        assert body["page_count"] == pages
        assert body["content"].strip()


class TestExtractIsStateless:
    """/extract does not persist anything: it is a pure transformation."""

    def test_same_pdf_can_be_extracted_twice(self, client: TestClient):
        first = post_raw(client, MINIMAL_PDF_BYTES)
        second = post_raw(client, MINIMAL_PDF_BYTES)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()

    def test_extracting_does_not_register_documents(self, client: TestClient):
        post_raw(client, MINIMAL_PDF_BYTES)

        assert client.get("/api/v1/documents").json() == []


class TestExtractRejections:
    """Invalid input is rejected with RFC 9457 problem details."""

    def assert_problem(self, response, status_code: int):
        assert response.status_code == status_code
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["status"] == status_code

    def test_content_that_is_not_a_pdf_returns_400(self, client: TestClient):
        self.assert_problem(post_raw(client, b"esto no es un PDF"), 400)

    def test_empty_body_returns_400(self, client: TestClient):
        self.assert_problem(post_raw(client, b""), 400)

    def test_multipart_without_file_field_returns_422(self, client: TestClient):
        response = client.post(
            "/extract", data={"otro": "campo"}, files={"x": ("a", b"b")}
        )

        self.assert_problem(response, 422)

    def test_pdf_over_the_size_limit_returns_413(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)

        self.assert_problem(post_raw(client, MINIMAL_PDF_BYTES), 413)

    def test_multipart_pdf_over_the_size_limit_returns_413(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(settings, "max_pdf_size_bytes", len(MINIMAL_PDF_BYTES) - 1)

        self.assert_problem(post_multipart(client, MINIMAL_PDF_BYTES), 413)

    def test_pdf_that_cannot_be_read_returns_422(self, client: TestClient):
        corrupt = b"%PDF-1.4\n" + b"\x00basura que no es un PDF valido" * 20

        self.assert_problem(post_raw(client, corrupt), 422)
