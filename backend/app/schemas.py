from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricId = Literal[
    "ndvi",
    "nightlights",
    "surface_water",
    "no2",
    "temperature",
    "precipitation",
    "aerosol",
    "cropland",
    "evapotranspiration",
    "soil_moisture",
    "impervious",
    "canopy_height",
    "forest_loss_year",
    "snow_cover",
    "travel_time_to_cities",
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
    surface_water: float | None = None
    no2: float | None = None
    temperature: float | None = None
    precipitation: float | None = None
    aerosol: float | None = None
    cropland: float | None = None
    evapotranspiration: float | None = None
    soil_moisture: float | None = None
    impervious: float | None = None
    canopy_height: float | None = None
    forest_loss_year: float | None = None
    snow_cover: float | None = None
    travel_time_to_cities: float | None = None


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


class GEEStatusResponse(BaseModel):
    auth_mode: Literal["user", "service_account"]
    project_id_configured: bool
    service_account_key_configured: bool
    service_account_key_exists: bool
    initialized: bool
    error: str | None = None


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
    include_basemap: bool = True
    overlay_opacity: float = Field(default=0.67, ge=0.0, le=1.0)
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


class PresetRegion(BaseModel):
    name: str
    region_id: str | None = None


class PresetDateRange(BaseModel):
    start_date: date
    end_date: date


class PresetComparePeriod(BaseModel):
    label: str | None = None
    start_date: date
    end_date: date


class PresetCompare(BaseModel):
    period_a: PresetComparePeriod
    period_b: PresetComparePeriod


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str | None = None
    regions: list[PresetRegion]
    metrics: list[MetricId]
    date_range: PresetDateRange | None = None
    compare: PresetCompare | None = None
    methodology_notes: str | None = None


class PresetListResponse(BaseModel):
    presets: list[PresetResponse]


class TelemetryRegisterRequest(BaseModel):
    instance_id: str = Field(..., min_length=1, max_length=64)
    device_id: str | None = Field(None, max_length=64)
    meta: dict[str, Any] = Field(default_factory=dict)
    path: str | None = Field(None, max_length=2048)


class TelemetryRegisterResponse(BaseModel):
    instance_id: str
    ip_address: str
    first_seen_at: datetime
    last_seen_at: datetime


class TelemetryEventIn(BaseModel):
    type: str = Field(..., min_length=1, max_length=64)
    client_ts_ms: int | None = Field(None, ge=0)
    path: str | None = Field(None, max_length=2048)
    data: dict[str, Any] | None = None


class TelemetryEventsRequest(BaseModel):
    instance_id: str = Field(..., min_length=1, max_length=64)
    device_id: str | None = Field(None, max_length=64)
    events: list[TelemetryEventIn] = Field(..., min_length=1, max_length=200)


class TelemetryEventsResponse(BaseModel):
    inserted: int


class AdminIpSummary(BaseModel):
    ip_address: str
    location: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    instance_count: int
    event_count: int


class AdminIpListResponse(BaseModel):
    ips: list[AdminIpSummary]
    total: int


class AdminInstanceSummary(BaseModel):
    instance_id: str
    device_id: str | None
    user_agent: str | None
    accept_language: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_path: str | None
    event_count: int


class AdminIpDetailResponse(BaseModel):
    ip: AdminIpSummary
    instances: list[AdminInstanceSummary]


class AdminInstanceDetailResponse(BaseModel):
    instance_id: str
    device_id: str | None
    ip_address: str
    user_agent: str | None
    accept_language: str | None
    meta: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    last_path: str | None
    total_events: int
    event_type_counts: dict[str, int]
    distinct_paths: int


class AdminTelemetryEvent(BaseModel):
    id: int
    event_type: str
    client_ts_ms: int | None
    received_at: datetime
    path: str | None
    data: dict[str, Any] | None


class AdminInstanceEventsResponse(BaseModel):
    instance_id: str
    events: list[AdminTelemetryEvent]
    total: int
