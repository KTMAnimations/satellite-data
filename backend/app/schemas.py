from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricId = Literal[
    "ndvi",
    "nightlights",
    "urban_density",
    "parking",
    "land_cover",
    "surface_water",
    "active_fire",
    "no2",
    "temperature",
    "precipitation",
    "aerosol",
    "cropland",
    "evapotranspiration",
    "soil_moisture",
    "impervious",
    "fire_historical",
    "canopy_height",
]


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class RegionCreate(BaseModel):
    name: str
    description: str | None = None
    geometry: dict[str, Any]
    country: str | None = None
    state_province: str | None = None
    category: str | None = None


class RegionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    geometry: dict[str, Any]
    type: Literal["predefined", "custom"]
    country: str | None
    state_province: str | None
    category: str | None
    created_at: datetime
    updated_at: datetime


class RegionListResponse(BaseModel):
    regions: list[RegionResponse]
    total: int
    page: int
    page_size: int


class MetricDataPoint(BaseModel):
    date: str
    value: float


class MetricData(BaseModel):
    unit: str
    data: list[MetricDataPoint]


class SeasonalAverage(BaseModel):
    # Keep keys stable for the frontend; values are null when unavailable.
    ndvi: float | None = None
    nightlights: float | None = None
    urban_density: float | None = None
    parking: float | None = None
    land_cover: float | None = None
    surface_water: float | None = None
    active_fire: float | None = None
    no2: float | None = None
    temperature: float | None = None
    precipitation: float | None = None
    aerosol: float | None = None
    cropland: float | None = None
    evapotranspiration: float | None = None
    soil_moisture: float | None = None
    impervious: float | None = None
    fire_historical: float | None = None
    canopy_height: float | None = None


class SeasonalSummary(BaseModel):
    winter_avg: SeasonalAverage
    summer_avg: SeasonalAverage
    change_pct: SeasonalAverage


class MetricsResponse(BaseModel):
    region_id: str
    region_name: str
    metrics: dict[str, MetricData]
    seasonal_summary: SeasonalSummary | None


class CompareRequest(BaseModel):
    region_id: str
    period_a_start: date
    period_a_end: date
    period_b_start: date
    period_b_end: date
    metrics: list[MetricId] | None = None


class PeriodSummary(BaseModel):
    start_date: date
    end_date: date
    averages: dict[str, float]
    observation_count: int


class CompareResponse(BaseModel):
    region_id: str
    region_name: str
    period_a: PeriodSummary
    period_b: PeriodSummary
    change: dict[str, float]
    change_absolute: dict[str, float]


class TileTemplateResponse(BaseModel):
    metric: MetricId
    date_bucket: str
    granularity: Literal["daily", "weekly", "monthly"]
    tile_url: str
    attribution: str | None = None
    min: float
    max: float
    palette: list[str]
    opacity: float


class ExportRequest(BaseModel):
    region_id: str
    format: Literal["pdf"]
    start_date: date | None = None
    end_date: date | None = None
    metrics: list[MetricId] | None = None
    include_charts: bool = True
    include_maps: bool = True
    title: str | None = None
    description: str | None = None


class CSVExportRequest(BaseModel):
    region_ids: list[str] | None = None
    metrics: list[MetricId] | None = None
    start_date: date | None = None
    end_date: date | None = None
    include_metadata: bool = False


class AnimationRequest(BaseModel):
    region_id: str
    metric: MetricId
    format: Literal["gif"] = "gif"
    start_date: date
    end_date: date
    frame_duration_ms: int = Field(default=500, ge=50, le=5000)
    width: int = Field(default=800, ge=128, le=2048)
    height: int = Field(default=600, ge=128, le=2048)


class ExportResponse(BaseModel):
    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    format: str
    progress: float | None = None
    message: str | None = None
    download_url: str | None = None
    file_size: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None

