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
    app_version: str = "1.1.0"
    debug: bool = False

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
