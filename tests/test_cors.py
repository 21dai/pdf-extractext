"""CORS: configurable origins, and credentials only for explicit origins."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import create_app


def preflight(client: TestClient, origin: str):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_by_default_any_origin_is_allowed_without_credentials(db):
    """Con `*` el navegador no manda cookies: la API no las usa."""
    with TestClient(create_app()) as client:
        response = preflight(client, "https://cualquier-sitio.example")

    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_configured_origins_are_the_only_ones_allowed(
    db, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "cors_allow_origins", ["http://localhost:3000"])

    with TestClient(create_app()) as client:
        allowed = preflight(client, "http://localhost:3000")
        other = preflight(client, "https://otro-sitio.example")

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in other.headers


def test_origins_can_come_as_a_comma_separated_list():
    """CORS_ALLOW_ORIGINS=http://a,http://b en el .env (12-Factor III)."""
    configured = Settings(cors_allow_origins="http://a.example, http://b.example")

    assert configured.cors_allow_origins == ["http://a.example", "http://b.example"]
