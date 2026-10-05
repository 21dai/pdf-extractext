"""Tests for the structured logging: one JSON object per line on stdout."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.utils.logging import configure_logging
from tests.support.pdf import MINIMAL_PDF_BYTES


@pytest.fixture
def json_logs(capsys: pytest.CaptureFixture[str]):
    """Configure the JSON logging and return a function that reads the lines."""
    configure_logging("INFO")

    def read() -> list[dict]:
        return [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    yield read
    configure_logging("WARNING")


def test_each_record_is_one_json_line_with_its_extra_fields(json_logs):
    logging.getLogger("prueba").info("evento", extra={"paginas": 3})

    record = json_logs()[-1]
    assert record["level"] == "INFO"
    assert record["logger"] == "prueba"
    assert record["message"] == "evento"
    assert record["paginas"] == 3
    assert "time" in record


def test_exceptions_are_logged_in_the_same_line(json_logs):
    try:
        raise ValueError("fallo")
    except ValueError:
        logging.getLogger("prueba").exception("error")

    record = json_logs()[-1]
    assert "ValueError: fallo" in record["exception"]


def test_records_below_the_level_are_not_written(json_logs):
    configure_logging("WARNING")

    logging.getLogger("prueba").info("no se escribe")

    assert json_logs() == []


def test_configuring_twice_does_not_duplicate_lines(json_logs):
    configure_logging("INFO")

    logging.getLogger("prueba").info("una sola vez")

    assert len(json_logs()) == 1


class TestExtractLogs:
    def test_each_extraction_logs_size_pages_and_duration(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ):
        with caplog.at_level(logging.INFO):
            client.post(
                "/extract",
                content=MINIMAL_PDF_BYTES,
                headers={"Content-Type": "application/pdf"},
            )

        record = next(r for r in caplog.records if r.getMessage() == "pdf_extraido")
        assert record.bytes == len(MINIMAL_PDF_BYTES)
        assert record.page_count == 1
        assert record.duration_ms >= 0

    def test_rejected_pdfs_log_the_status_and_reason(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ):
        with caplog.at_level(logging.INFO):
            client.post("/extract", content=b"no es un PDF")

        record = next(r for r in caplog.records if r.getMessage() == "pdf_rechazado")
        assert record.levelno == logging.WARNING
        assert record.status == 400
        assert record.detail == "Archivo PDF invalido"
