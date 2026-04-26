"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.utils.database import create_tables, drop_tables, get_database, reset_client


@pytest.fixture(scope="function")
def db(monkeypatch):
    """Create an isolated Mongo-like database for tests."""
    monkeypatch.setattr(settings, "database_url", "mongomock://localhost")
    monkeypatch.setattr(settings, "database_name", "pdf_extract_test")
    reset_client()
    create_tables()

    yield get_database()

    drop_tables()
    reset_client()


@pytest.fixture(scope="function")
def client(db):
    """Create test client using the isolated test database."""
    app = create_app()

    with TestClient(app) as test_client:
        yield test_client
