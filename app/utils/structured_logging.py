"""Structured logging: one JSON object per line on stdout (12-Factor XI).

La aplicacion no decide donde terminan los logs: los escribe en stdout y el
entorno (Docker, el orquestador de contenedores) los junta. Una linea JSON
por evento se puede filtrar y agregar sin parsear texto libre.
"""

import json
import logging
import sys
from datetime import datetime, timezone

# Atributos que todo LogRecord trae: lo que no este aca vino en `extra`.
_STANDARD_ATTRIBUTES = frozenset(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None))
) | {
    "message",
    "asctime",
    "taskName",
    # uvicorn repite el mensaje con codigos de color de terminal: es ruido.
    "color_message",
}


class JsonFormatter(logging.Formatter):
    """Format each record as a single JSON line, including its extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRIBUTES:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _JsonHandler(logging.StreamHandler):
    """Handler installed by `configure_logging`, so it can find and replace it.

    Escribe siempre en el sys.stdout del momento y no en el que habia al
    crearlo: si algo lo reemplaza despues (pytest al capturar la salida), las
    lineas siguen llegando.
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, value) -> None:
        pass


def configure_logging(level: str) -> None:
    """Send every log record (app and uvicorn) to stdout as JSON lines.

    Reemplaza solo el handler que instalo antes, asi llamarla de nuevo no
    duplica lineas ni quita handlers ajenos (por ejemplo, los de pytest).
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, _JsonHandler):
            root.removeHandler(handler)

    handler = _JsonHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
