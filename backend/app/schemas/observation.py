from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricType = Literal[
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


class ObservationBase(BaseModel):
    """Base schema for observation data."""

    date: date
    metric: MetricType
    value: float
    extra_data: dict[str, Any] | None = None


class ObservationResponse(ObservationBase):
    """Schema for observation response."""

    id: str
    region_id: str
    raster_path: str | None = None

    class Config:
        from_attributes = True


class MetricDataPoint(BaseModel):
    """Single data point in a time series."""

    date: str  # YYYY-MM format
    value: float


class MetricData(BaseModel):
    """Time series data for a single metric."""

    unit: str
    data: list[MetricDataPoint]


class SeasonalAverage(BaseModel):
    """Seasonal average values."""

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
    """Summary of seasonal variations."""

    winter_avg: SeasonalAverage
    summer_avg: SeasonalAverage
    change_pct: SeasonalAverage


class MetricsResponse(BaseModel):
    """Response schema for metrics endpoint."""

    region_id: str
    region_name: str
    metrics: dict[MetricType, MetricData]
    seasonal_summary: SeasonalSummary | None = None


class MetricsQuery(BaseModel):
    """Query parameters for metrics."""

    start_date: date | None = Field(None, description="Start date for time range")
    end_date: date | None = Field(None, description="End date for time range")
    metrics: list[MetricType] | None = Field(
        None, description="Specific metrics to retrieve"
    )
    granularity: Literal["daily", "weekly", "monthly"] = Field(
        "monthly", description="Temporal granularity"
    )
