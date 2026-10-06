"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api import document_router, extract_router
from app.config import settings
from app.services.admission import AdmissionGate
from app.utils.database import create_tables, get_db
from app.utils.problem_details import register_problem_details_handlers
from app.utils.structured_logging import configure_logging

logger = logging.getLogger(__name__)

# Tiempo de servicio supuesto hasta medir: el promedio de los PDFs de prueba.
INITIAL_SERVICE_SECONDS = 0.3


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown events for the FastAPI application.

    Args:
        app: FastAPI application
    """
    if settings.documents_api_enabled:
        create_tables()
    logger.info(
        "servicio_iniciado",
        extra={
            "version": settings.app_version,
            "documents_api_enabled": settings.documents_api_enabled,
        },
    )

    yield

    logger.info("servicio_detenido")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        description="API para registrar, validar y extraer texto de documentos PDF.",
        version=settings.app_version,
        debug=settings.debug,
        docs_url=settings.api_docs_url,
        redoc_url=settings.api_redoc_url,
        openapi_url=settings.api_openapi_url,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Una compuerta por proceso: cada uno extrae un PDF por vez (PDFium).
    app.state.admission_gate = AdmissionGate(
        max_wait_seconds=settings.extract_max_wait_seconds,
        max_pending=settings.extract_max_pending,
        initial_service_seconds=INITIAL_SERVICE_SECONDS,
    )
    register_problem_details_handlers(app)
    # Contrato del TP: la ruta es /extract, sin el prefijo versionado.
    app.include_router(extract_router)
    if settings.documents_api_enabled:
        app.include_router(document_router, prefix=settings.api_v1_prefix)
        register_database_readiness(app)
    else:
        register_extraction_only_readiness(app)

    @app.get("/", tags=["inicio"], summary="Ver informacion basica de la API")
    async def root() -> dict[str, Any]:
        """Mostrar informacion general de la API."""
        info: dict[str, Any] = {
            "message": f"Bienvenido a {settings.app_name}",
            "version": settings.app_version,
            "docs": settings.api_docs_url,
        }
        if settings.documents_api_enabled:
            info["database"] = "mongodb"
            info["database_name"] = settings.database_name
        return info

    @app.get("/health", tags=["inicio"], summary="Verificar que el proceso responde")
    def health() -> dict[str, str]:
        """Liveness: el proceso esta vivo. No consulta dependencias.

        Lo usa el healthcheck de Docker: si dependiera de MongoDB, una caida
        de la base marcaria las replicas como enfermas y Traefik dejaria de
        mandarles POST /extract, que no usa la base.
        """
        return {"status": "ok"}

    return app


def register_extraction_only_readiness(app: FastAPI) -> None:
    """Readiness of the extractor: it has no dependencies to check."""

    @app.get("/ready", tags=["inicio"], summary="Verificar que puede atender")
    def ready() -> dict[str, str]:
        """Readiness: sin base de datos, alcanza con que el proceso responda."""
        return {"status": "ok"}


def register_database_readiness(app: FastAPI) -> None:
    """Readiness of the full service, which needs MongoDB for the CRUD."""

    @app.get("/ready", tags=["inicio"], summary="Verificar que puede atender")
    def ready(db: Any = Depends(get_db)) -> dict[str, str]:
        """Readiness: la API y MongoDB estan disponibles."""
        try:
            db.command("ping")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Base de datos no disponible",
            ) from exc

        return {
            "status": "ok",
            "database": "mongodb",
            "database_name": settings.database_name,
        }
