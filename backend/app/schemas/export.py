from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


ExportFormat = Literal["pdf", "html", "csv"]
AnimationFormat = Literal["gif", "frames"]


class ExportRequest(BaseModel):
    """Schema for export requests."""

    region_id: str
    format: ExportFormat
    start_date: date | None = None
    end_date: date | None = None
    metrics: list[str] | None = None
    include_charts: bool = True
    include_maps: bool = True
    title: str | None = None
    description: str | None = None


class ExportResponse(BaseModel):
    """Schema for export response."""

    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    format: ExportFormat
    progress: float = Field(0.0, ge=0.0, le=100.0)
    message: str | None = None
    download_url: str | None = None
    file_size: int | None = None
    created_at: str
    completed_at: str | None = None


class AnimationRequest(BaseModel):
    """Schema for animation export requests."""

    region_id: str
    metric: str
    format: AnimationFormat = "gif"
    start_date: date
    end_date: date
    frame_duration_ms: int = Field(500, ge=100, le=5000)
    width: int = Field(800, ge=200, le=1920)
    height: int = Field(600, ge=200, le=1080)
    lock_view: bool = Field(
        False,
        description="If true, use view_center/view_zoom instead of auto fitBounds for the animation viewport.",
    )
    view_center: tuple[float, float] | None = Field(
        None,
        description="Locked map center as (lat, lon).",
    )
    view_zoom: int | None = Field(
        None,
        ge=4,
        le=11,
        description="Locked map zoom (matches frontend constraints).",
    )


class AnimationResponse(BaseModel):
    """Schema for animation response."""

    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    format: AnimationFormat
    progress: float = Field(0.0, ge=0.0, le=100.0)
    message: str | None = None
    frame_count: int | None = None
    download_url: str | None = None
    file_size: int | None = None
    created_at: str
    completed_at: str | None = None


class CSVExportRequest(BaseModel):
    """Schema for CSV data export."""

    region_ids: list[str] | None = Field(
        None, description="Region IDs to export. If None, exports all."
    )
    metrics: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    include_metadata: bool = False
