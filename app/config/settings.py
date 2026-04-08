"""Application Settings and Configuration"""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""

    # Application
    app_name: str = "PDF Extract API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite:///./pdf_extract.db"
    database_echo: bool = False

    # API
    api_v1_prefix: str = "/api/v1"
    api_docs_url: Optional[str] = "/docs"
    api_redoc_url: Optional[str] = "/redoc"
    api_openapi_url: Optional[str] = "/openapi.json"

    class Config:
        """Pydantic config"""

        env_file = ".env"
        case_sensitive = False


# Create a global settings instance
settings = Settings()
