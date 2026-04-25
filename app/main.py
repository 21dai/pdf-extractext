"""FastAPI application factory"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import document_router
from app.utils.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events

    Args:
        app: FastAPI application
    """
    # Startup
    create_tables()
    print(f"✓ {settings.app_name} started successfully")

    yield

    # Shutdown
    print(f"✓ {settings.app_name} shutdown")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application

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

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(document_router, prefix=settings.api_v1_prefix)

    # Root endpoint
    @app.get("/", tags=["inicio"], summary="Ver informacion basica de la API")
    async def root():
        """Mostrar informacion general de la API."""
        return {
            "message": f"Bienvenido a {settings.app_name}",
            "version": settings.app_version,
            "docs": settings.api_docs_url,
        }

    return app
