from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from geojson_pydantic import Polygon


class RegionBase(BaseModel):
    """Base schema for region data."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    country: str | None = Field(None, max_length=100)
    state_province: str | None = Field(None, max_length=100)
    category: Literal["major_city", "megacity", "migration_hotspot"] | None = None


class RegionCreate(RegionBase):
    """Schema for creating a new region."""

    geometry: dict[str, Any] = Field(
        ...,
        description="GeoJSON Polygon geometry",
        json_schema_extra={
            "example": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.1, 33.4],
                        [-112.1, 33.5],
                        [-111.9, 33.5],
                        [-111.9, 33.4],
                        [-112.1, 33.4],
                    ]
                ],
            }
        },
    )

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that geometry is a valid GeoJSON Polygon."""
        if v.get("type") != "Polygon":
            raise ValueError("Geometry must be a Polygon")
        coords = v.get("coordinates", [])
        if not coords or len(coords) < 1:
            raise ValueError("Polygon must have at least one ring")
        # Validate ring closure
        ring = coords[0]
        if len(ring) < 4:
            raise ValueError("Polygon ring must have at least 4 coordinates")
        if ring[0] != ring[-1]:
            raise ValueError("Polygon ring must be closed")
        return v


class RegionResponse(RegionBase):
    """Schema for region response."""

    id: str
    geometry: dict[str, Any]
    type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegionListResponse(BaseModel):
    """Schema for listing regions."""

    regions: list[RegionResponse]
    total: int
    page: int = 1
    page_size: int = 50
