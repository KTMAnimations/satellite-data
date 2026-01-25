from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)


class APIKeyResponse(BaseModel):
    """Schema for API key response."""

    id: str
    name: str
    key: str | None = None  # Only populated on creation
    created_at: datetime
    last_used: datetime | None = None
    is_active: bool

    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Schema for listing API keys."""

    keys: list[APIKeyResponse]
    total: int
