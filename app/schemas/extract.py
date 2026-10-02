"""Schemas for the stateless extraction endpoint."""

from pydantic import BaseModel, Field


class ExtractResponse(BaseModel):
    """Response of POST /extract, as defined by the TP contract."""

    content: str = Field(..., description="Contenido del PDF en Markdown")
    page_count: int = Field(..., ge=0, description="Cantidad de paginas del PDF")
