"""Summary generation service backed by a local Ollama API."""

from __future__ import annotations

import json
from urllib import error, request

from app.config import settings


class OllamaSummaryService:
    """Generate summaries using a locally running Ollama model."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_input_chars: int | None = None,
    ):
        """Initialize the Ollama client settings."""
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds
        self.max_input_chars = max_input_chars or settings.ollama_summary_max_chars

    def summarize(self, text: str) -> str:
        """Generate a Spanish summary for the provided extracted PDF text."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("El documento no tiene texto extraido para resumir")

        if not self.model:
            raise ValueError("El modelo de Ollama no esta configurado")

        payload = {
            "model": self.model,
            "prompt": self._build_prompt(normalized_text[: self.max_input_chars]),
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        http_request = request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(
                http_request, timeout=self.timeout_seconds
            ) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(
                f"Ollama respondio con error HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise ValueError(
                "No se pudo conectar con Ollama. "
                f"Verifica que este disponible en {self.base_url}"
            ) from exc
        except TimeoutError as exc:
            raise ValueError("Ollama no respondio antes del tiempo limite") from exc

        try:
            parsed_response = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama devolvio una respuesta invalida") from exc

        summary = str(parsed_response.get("response", "")).strip()
        if not summary:
            raise ValueError("Ollama no devolvio un resumen")

        return summary

    def _build_prompt(self, text: str) -> str:
        """Build the summarization prompt sent to Ollama."""
        return (
            "Sos un asistente que resume documentos academicos y administrativos. "
            "Resumi el siguiente texto en espanol claro, en 5 a 8 oraciones. "
            "Menciona los puntos principales y evita inventar informacion.\n\n"
            f"Texto del documento:\n{text}"
        )
