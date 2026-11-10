"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import extract_router
from app.config import settings
from app.core.pdf_extraction import PdfiumExtractor
from app.services.admission import AdmissionGate
from app.utils.metrics import PrometheusGateObserver
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
    logger.info("servicio_iniciado", extra={"version": settings.app_version})

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
        description="API para extraer el texto de documentos PDF, sin guardarlos.",
        version=settings.app_version,
        debug=settings.debug,
        docs_url=settings.api_docs_url,
        redoc_url=settings.api_redoc_url,
        openapi_url=settings.api_openapi_url,
        lifespan=lifespan,
    )

    # Con "*" no se permiten credenciales: Starlette responderia con el origen
    # de cualquier sitio y le dejaria mandar cookies. Solo con origenes
    # explicitos (CORS_ALLOW_ORIGINS) tiene sentido permitirlas.
    any_origin = "*" in settings.cors_allow_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=not any_origin,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # El motor de extraccion se elige aqui, en un solo lugar: el router lo
    # recibe por dependencia, asi no hay un motor implicito que cambiar cada
    # vez que se quiere medir otro.
    app.state.pdf_extractor = PdfiumExtractor()

    # Una compuerta por proceso: cada uno extrae un PDF por vez (PDFium).
    metrics = PrometheusGateObserver()
    app.state.admission_gate = AdmissionGate(
        max_wait_seconds=settings.extract_max_wait_seconds,
        max_pending=settings.extract_max_pending,
        max_pending_bytes=settings.extract_max_pending_bytes,
        queue_order=settings.extract_queue_order,
        priority_age_seconds=settings.extract_priority_age_seconds,
        observer=metrics,
        initial_service_seconds=INITIAL_SERVICE_SECONDS,
    )
    register_problem_details_handlers(app)

    @app.get("/metrics", include_in_schema=False)
    def read_metrics() -> Response:
        """Metrics of this replica in the Prometheus format."""
        body, content_type = metrics.render()
        return Response(content=body, media_type=content_type)

    # Contrato del TP: la ruta es /extract, sin el prefijo versionado. Es el
    # unico endpoint de negocio: guardar documentos es trabajo de
    # document-store, al que llama el orquestador (ADR-0008).
    app.include_router(extract_router)

    @app.get("/", tags=["inicio"], summary="Ver informacion basica de la API")
    async def root() -> dict[str, Any]:
        """Mostrar informacion general de la API."""
        return {
            "message": f"Bienvenido a {settings.app_name}",
            "version": settings.app_version,
            "docs": settings.api_docs_url,
        }

    @app.get("/health", tags=["inicio"], summary="Verificar que el proceso responde")
    def health() -> dict[str, str]:
        """Liveness: el proceso esta vivo. Lo usa el healthcheck de Docker."""
        return {"status": "ok"}

    @app.get("/ready", tags=["inicio"], summary="Verificar que puede atender")
    def ready() -> dict[str, str]:
        """Readiness: el servicio no tiene dependencias externas (ni base de
        datos ni otros servicios), asi que alcanza con que el proceso responda."""
        return {"status": "ok"}

    return app
