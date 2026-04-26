"""Document schema definitions"""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    """Base document schema"""

    name: str = Field(..., description="Nombre del documento")
    original_filename: str = Field(
        ..., description="Nombre original del archivo PDF subido"
    )
    file_size: int = Field(..., description="Tamano del archivo en bytes")


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    name: str | None = Field(None, description="Nuevo nombre del documento")


class DocumentResponse(DocumentBase):
    """Schema for document response."""

    id: int = Field(..., description="Identificador unico del documento")
    checksum: str = Field(..., description="Checksum SHA-256 del archivo PDF")
    extracted_text: str | None = Field(
        None, description="Texto extraido del contenido del PDF"
    )
    is_processed: bool = Field(
        ..., description="Indica si el documento ya fue procesado"
    )
    created_at: datetime = Field(..., description="Fecha de creacion del registro")
    updated_at: datetime = Field(..., description="Fecha de ultima actualizacion")

    class Config:
        """Pydantic config"""

        from_attributes = True
