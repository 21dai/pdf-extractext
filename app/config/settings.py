"""Application settings and configuration."""

from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings"""

    # El .env se comparte con docker-compose, que necesita variables que no son
    # de la aplicacion (por ejemplo IMAGE_TAG, el tag de la imagen). Se ignoran
    # en vez de hacer fallar el arranque.
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # Application
    app_name: str = "API de Extraccion de PDF"
    app_version: str = "1.3.1"
    debug: bool = False
    # Nivel de los logs JSON que se escriben en stdout (12-Factor XI).
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    # Procesos de uvicorn (factor VIII: concurrencia por procesos). La extraccion
    # de PDF es CPU y el GIL limita a un nucleo por proceso: con N workers se
    # procesan N PDFs a la vez. uvicorn lee WEB_CONCURRENCY por convencion.
    web_concurrency: int = 1

    # Database
    database_url: str = "mongodb://localhost:27017"
    database_name: str = "pdf_extract"
    database_timeout_ms: int = 3000
    max_pdf_size_bytes: int = 10 * 1024 * 1024
    # Con false el servicio solo expone POST /extract: no usa MongoDB, arranca
    # sin base de datos y sus replicas no comparten estado (12-Factor VI).
    documents_api_enabled: bool = True
    # Backpressure de POST /extract: tiempo util de un request. Si lo que ya
    # espero mas una extraccion promedio lo supera, se responde 503 sin
    # procesarlo. Tiene que quedar por debajo del timeout de los clientes
    # (30 s en el TP).
    extract_max_wait_seconds: float = 28.0
    # Requests de /extract admitidos a la vez por proceso (la cola). Llena,
    # el siguiente recibe 503. Acota la memoria de los PDFs que esperan.
    extract_max_pending: int = 30

    # MongoDB Auth
    root_username: str = ""
    root_password: str = ""

    # API
    api_v1_prefix: str = "/api/v1"
    api_docs_url: Optional[str] = "/docs"
    api_redoc_url: Optional[str] = "/redoc"
    api_openapi_url: Optional[str] = "/openapi.json"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        """Accept common environment values for debug mode."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {
                "1",
                "true",
                "yes",
                "on",
                "debug",
                "dev",
                "development",
            }:
                return True
            if normalized in {
                "0",
                "false",
                "no",
                "off",
                "release",
                "prod",
                "production",
            }:
                return False
        return value


# Create a global settings instance
settings = Settings()
