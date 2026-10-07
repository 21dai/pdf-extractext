"""Application entry point"""

from typing import Any

import uvicorn

from app.config import settings
from app.main import create_app

app = create_app()


def uvicorn_options() -> dict[str, Any]:
    """Options of the uvicorn server, from the settings."""
    return {
        "host": settings.host,
        "port": settings.port,
        "reload": settings.debug,
        "workers": settings.web_concurrency,
        # Mas que las conexiones inactivas de Traefik (90 s): si uvicorn cerrara
        # antes, Traefik podria reusar una conexion que se esta cerrando y ese
        # request fallaria con 502.
        "timeout_keep_alive": settings.http_keep_alive_seconds,
        # Sin la config de logging de uvicorn: sus logs pasan por el handler
        # JSON que instala create_app (una linea JSON por evento en stdout).
        "log_config": None,
    }


if __name__ == "__main__":
    # La app se pasa como import string: uvicorn lo exige para reload y workers.
    uvicorn.run("main:app", **uvicorn_options())
