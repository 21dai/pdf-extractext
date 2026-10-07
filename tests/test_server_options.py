"""Options of the uvicorn server that runs the service."""

import pytest

from app.config import settings
from main import uvicorn_options

# Traefik mantiene abiertas las conexiones inactivas con cada replica hasta
# 90 s (idleConnTimeout por defecto) para reusarlas.
TRAEFIK_IDLE_CONN_SECONDS = 90


def test_keeps_idle_connections_longer_than_traefik():
    """Si uvicorn cierra antes, Traefik reusa una conexion que se esta cerrando.

    Ese request falla con 502: los errores sueltos del spike (0,2 % en una
    corrida y uno en la emulacion a escala).
    """
    assert uvicorn_options()["timeout_keep_alive"] > TRAEFIK_IDLE_CONN_SECONDS


def test_keep_alive_comes_from_the_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "http_keep_alive_seconds", 200)

    assert uvicorn_options()["timeout_keep_alive"] == 200


def test_logs_go_through_the_json_handler():
    assert uvicorn_options()["log_config"] is None
