"""Document schema definitions"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)

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


class DocumentSummaryResponse(BaseModel):
    """Schema for document summary response."""

    document_id: int = Field(..., description="Identificador del documento resumido")
    model: str = Field(..., description="Modelo local de Ollama utilizado")
    summary: str = Field(..., description="Resumen generado a partir del texto extraido")
    source_text_length: int = Field(
        ..., description="Cantidad de caracteres del texto original usado como fuente"
    )
