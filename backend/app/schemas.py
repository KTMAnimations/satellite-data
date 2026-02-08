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
    "no2",
    "temperature",
    "precipitation",
    "aerosol",
    "cropland",
    "evapotranspiration",
    "soil_moisture",
    "impervious",
    "canopy_height",
    "evi",
    "ndre",
    "ndmi",
    "ndwi",
    "mndwi",
    "savi",
    "bsi",
    "nbr",
    "dnbr",
    "gci",
    "ndsi",
    "s1_vv",
    "s1_vh",
    "s1_vh_vv_ratio",
    "s1_rvi",
    "lst_day",
    "lst_night",
    "lst_diurnal_range",
    "albedo_black_sky",
    "albedo_white_sky",
    "par",
    "lai",
    "fpar",
    "gpp",
    "npp",
    "biomass_agb_carbon",
    "biomass_bgb_carbon",
    "gedi_agbd",
    "active_fire_temp",
    "active_fire_confidence",
    "burned_area_date",
    "burned_area_fraction",
    "treecover_2000",
    "forest_loss_year",
    "forest_gain",
    "forest_loss_fraction",
    "snow_cover",
    "fractional_snow_cover",
    "snow_albedo",
    "snow_cover_8day",
    "tws_anomaly",
    "flood_max_extent",
    "flood_duration_days",
    "flood_observation_quality",
    "drought_pdsi",
    "vpd",
    "runoff",
    "clim_water_deficit",
    "elevation",
    "slope",
    "aspect",
    "terrain_ruggedness",
    "soil_organic_carbon",
    "soil_ph",
    "soil_sand_fraction",
    "soil_field_capacity",
    "population_count",
    "population_density",
    "building_presence",
    "building_height",
    "building_count_proxy",
    "building_footprints_density",
    "travel_time_to_cities",
    "human_modification",
    "co",
    "so2",
    "o3",
    "hcho",
    "ch4",
    "pm25",
    "sst",
    "ocean_chlorophyll",
    "ocean_poc",
    "bathymetry",
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


SeasonalAverage = dict[str, float | None]


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
