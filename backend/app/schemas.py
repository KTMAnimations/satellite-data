from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricId = Literal[
    "nightlights",
    "ndvi",
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
    "co_column_density",
    "so2_column_density",
    "o3_total_column",
    "tropospheric_ozone_column",
    "methane_mixing_ratio",
    "formaldehyde_column",
    "aerosol_layer_height",
    "cloud_fraction",
    "cloud_top_height",
    "aod_550",
    "active_fire_hotspots",
    "burned_area_fraction",
    "burn_day_of_year",
    "river_flood_depth_rp100",
    "water_recurrence",
    "snow_cover",
    "snow_albedo",
    "terrestrial_water_storage",
    "drought_pdsi",
    "climatic_water_deficit",
    "runoff",
    "snow_water_equivalent",
    "vegetation_water_deficit",
    "wind_speed_climate",
    "evi_modis",
    "lai",
    "fpar",
    "gpp_8day",
    "npp_annual",
    "phenology_greenup",
    "phenology_senescence",
    "landsat_ndwi_8day",
    "landsat_evi_8day",
    "forest_loss_year",
    "forest_loss_fraction",
    "tree_cover_2000",
    "forest_gain",
    "population_count_ghsl",
    "population_count_worldpop",
    "population_density_gpw",
    "built_height",
    "built_volume_total",
    "built_volume_nonres",
    "degree_of_urbanization",
    "radar_backscatter_vv",
    "radar_backscatter_vh",
    "elevation_dem30",
    "elevation_srtm",
    "dw_trees",
    "dw_grass",
    "dw_flooded_vegetation",
    "dw_shrub_scrub",
    "dw_bare",
    "dw_snow_ice",
    "wind_speed_10m",
    "relative_humidity_2m",
    "surface_pressure",
    "solar_radiation_down",
    "snow_depth_era5",
    "runoff_era5",
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
    nightlights: float | None = None
    ndvi: float | None = None
    urban_density: float | None = None
    parking: float | None = None
    land_cover: float | None = None
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
    co_column_density: float | None = None
    so2_column_density: float | None = None
    o3_total_column: float | None = None
    tropospheric_ozone_column: float | None = None
    methane_mixing_ratio: float | None = None
    formaldehyde_column: float | None = None
    aerosol_layer_height: float | None = None
    cloud_fraction: float | None = None
    cloud_top_height: float | None = None
    aod_550: float | None = None
    active_fire_hotspots: float | None = None
    burned_area_fraction: float | None = None
    burn_day_of_year: float | None = None
    river_flood_depth_rp100: float | None = None
    water_recurrence: float | None = None
    snow_cover: float | None = None
    snow_albedo: float | None = None
    terrestrial_water_storage: float | None = None
    drought_pdsi: float | None = None
    climatic_water_deficit: float | None = None
    runoff: float | None = None
    snow_water_equivalent: float | None = None
    vegetation_water_deficit: float | None = None
    wind_speed_climate: float | None = None
    evi_modis: float | None = None
    lai: float | None = None
    fpar: float | None = None
    gpp_8day: float | None = None
    npp_annual: float | None = None
    phenology_greenup: float | None = None
    phenology_senescence: float | None = None
    landsat_ndwi_8day: float | None = None
    landsat_evi_8day: float | None = None
    forest_loss_year: float | None = None
    forest_loss_fraction: float | None = None
    tree_cover_2000: float | None = None
    forest_gain: float | None = None
    population_count_ghsl: float | None = None
    population_count_worldpop: float | None = None
    population_density_gpw: float | None = None
    built_height: float | None = None
    built_volume_total: float | None = None
    built_volume_nonres: float | None = None
    degree_of_urbanization: float | None = None
    radar_backscatter_vv: float | None = None
    radar_backscatter_vh: float | None = None
    elevation_dem30: float | None = None
    elevation_srtm: float | None = None
    dw_trees: float | None = None
    dw_grass: float | None = None
    dw_flooded_vegetation: float | None = None
    dw_shrub_scrub: float | None = None
    dw_bare: float | None = None
    dw_snow_ice: float | None = None
    wind_speed_10m: float | None = None
    relative_humidity_2m: float | None = None
    surface_pressure: float | None = None
    solar_radiation_down: float | None = None
    snow_depth_era5: float | None = None
    runoff_era5: float | None = None


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
