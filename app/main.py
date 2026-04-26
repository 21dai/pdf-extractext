"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api import document_router
from app.config import settings
from app.utils.database import create_tables, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown events for the FastAPI application.

    Args:
        app: FastAPI application
    """
    create_tables()
    print(f"[OK] {settings.app_name} started successfully")

    yield

    print(f"[OK] {settings.app_name} shutdown")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
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

    app.include_router(document_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["inicio"], summary="Ver informacion basica de la API")
    async def root():
        """Mostrar informacion general de la API."""
        return {
            "message": f"Bienvenido a {settings.app_name}",
            "version": settings.app_version,
            "docs": settings.api_docs_url,
            "database": "mongodb",
            "database_name": settings.database_name,
        }

    @app.get("/health", tags=["inicio"], summary="Verificar estado de la API")
    async def health(db: Any = Depends(get_db)):
        """Verificar que la API y MongoDB esten disponibles."""
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

    return app
