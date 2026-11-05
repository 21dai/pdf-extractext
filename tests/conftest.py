"""Pytest configuration and fixtures."""

import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="function")
def client():
    """Test client of a fresh app: the service has no database to set up."""
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def disk_forbidden(monkeypatch):
    """Fail if an upload is moved from memory to a temporary file on disk."""

    def rollover(self):
        raise AssertionError("el upload se escribio en un archivo temporal")

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", rollover)
