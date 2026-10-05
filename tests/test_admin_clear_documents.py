"""Tests for the admin process that deletes stored documents (12-Factor XII).

`python -m app.admin.clear_documents` runs with the same code and settings as
the API, so it reaches the same database the service is using.
"""

import pytest
from fastapi.testclient import TestClient

from app.admin.clear_documents import clear_documents, main
from tests.support.api_documents import create_document_response
from tests.support.pdf import build_pdf_bytes


@pytest.fixture
def stored_documents(client: TestClient) -> TestClient:
    """Two load-test documents and one real document, created through the API."""
    for index, name in enumerate(["carga vu1 iter1", "carga vu2 iter1", "Contrato"]):
        response = create_document_response(
            client, name=name, content=build_pdf_bytes(f"texto {index}")
        )
        assert response.status_code == 201
    return client


def stored_names(client: TestClient) -> list[str]:
    return sorted(doc["name"] for doc in client.get("/api/v1/documents").json())


def test_deletes_only_the_documents_whose_name_matches(stored_documents, db):
    deleted = clear_documents(db, name_regex="^carga vu")

    assert deleted == 2
    assert stored_names(stored_documents) == ["Contrato"]


def test_deletes_every_document_without_a_pattern(stored_documents, db):
    assert clear_documents(db, name_regex=None) == 3
    assert stored_names(stored_documents) == []


def test_cli_deletes_by_pattern_and_reports_the_count(
    stored_documents, capsys: pytest.CaptureFixture[str]
):
    assert main(["--name-regex", "^carga vu"]) == 0

    assert "2 documentos eliminados" in capsys.readouterr().out
    assert stored_names(stored_documents) == ["Contrato"]


def test_cli_dry_run_counts_without_deleting(
    stored_documents, capsys: pytest.CaptureFixture[str]
):
    assert main(["--all", "--dry-run"]) == 0

    assert "3 documentos se eliminarian" in capsys.readouterr().out
    assert len(stored_names(stored_documents)) == 3


def test_cli_refuses_to_run_without_saying_what_to_delete(stored_documents):
    with pytest.raises(SystemExit) as exit_info:
        main([])

    assert exit_info.value.code == 2
    assert len(stored_names(stored_documents)) == 3
