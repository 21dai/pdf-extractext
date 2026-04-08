"""Document schema definitions"""

from datetime import datetime
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    """Base document schema"""

    name: str = Field(..., description="Document name")
    file_path: str = Field(..., description="Path to the document file")
    file_size: int = Field(..., description="File size in bytes")


class DocumentCreate(DocumentBase):
    """Schema for creating a document"""

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document"""

    name: str | None = None
    extracted_text: str | None = None
    is_processed: bool | None = None


class DocumentResponse(DocumentBase):
    """Schema for document response"""

    id: int
    extracted_text: str | None = None
    is_processed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config"""

        from_attributes = True
