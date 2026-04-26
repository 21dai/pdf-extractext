"""Document domain model."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Document(BaseModel):
    """Document representation persisted in the document database."""

    id: int | None = Field(default=None)
    name: str
    original_filename: str | None = Field(default=None)
    file_path: str
    checksum: str
    file_size: int
    extracted_text: str | None = Field(default=None)
    is_processed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
