from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


ExportFormat = Literal["pdf", "html", "csv"]
AnimationFormat = Literal["gif", "webm", "frames"]


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


class AnimationResponse(BaseModel):
    """Schema for animation response."""

    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    format: AnimationFormat
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
