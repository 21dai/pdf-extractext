"""Application settings and configuration."""

from typing import Annotated, Any, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    app_version: str = "1.4.0"
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
    # Segundos que uvicorn mantiene abierta una conexion inactiva. Tiene que ser
    # mayor que el de Traefik (90 s) para que no reuse una que se esta cerrando.
    http_keep_alive_seconds: int = 120

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
    extract_max_wait_seconds: float = 25.0
    # Requests de /extract admitidos a la vez por proceso (la cola). Llena,
    # el siguiente recibe 503. Acota la memoria de los PDFs que esperan.
    extract_max_pending: int = 60
    # Orden de la cola de /extract: "size" atiende primero el PDF mas liviano
    # (menos bytes); "fifo", por orden de llegada. Con "size", el que ya espero
    # EXTRACT_PRIORITY_AGE_SECONDS pasa primero para que los grandes no se
    # queden sin turno. 7,5 s es lo que mejor dio con un nucleo por replica
    # (informe, experimento 14); en una maquina con menos nucleos que replicas
    # conviene "fifo".
    extract_queue_order: Literal["fifo", "size"] = "size"
    extract_priority_age_seconds: float = 7.5

    # MongoDB Auth
    root_username: str = ""
    root_password: str = ""

    # API
    api_v1_prefix: str = "/api/v1"
    api_docs_url: Optional[str] = "/docs"
    api_redoc_url: Optional[str] = "/redoc"
    api_openapi_url: Optional[str] = "/openapi.json"

    # Origenes permitidos por CORS. "*" (cualquiera) no manda credenciales;
    # con una lista explicita si (ver create_app). En el .env, separados por
    # coma: CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173
    cors_allow_origins: Annotated[list[str], NoDecode] = ["*"]

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: Any) -> Any:
        """Accept a comma separated list, as it comes from the environment."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
