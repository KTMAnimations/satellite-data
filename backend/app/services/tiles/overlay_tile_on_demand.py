"""
Shared on-demand overlay tile generator.

This module contains the shared Earth Engine tile generation logic used by:
- `/api/v1/tiles/us/...` (US-only tiles with a quick bounds reject)
- `/api/v1/tiles/world/...` (global tiles)

The output tiles are rendered with the same normalization + colormaps as
`USTileGenerator` so the frontend overlay looks consistent.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from typing import Literal

import numpy as np

from app.core.logging import get_logger
from app.services.satellite.us_data_service import USDataService
from app.services.tiles.generator import create_empty_tile
from app.services.tiles.us_tile_generator import (
    TILE_SIZE,
    USTileGenerator,
    tile_bounds,
    tile_bounds_mercator,
)

logger = get_logger(__name__)

TileGranularity = Literal["daily", "monthly"]

# Only these metrics are eligible for daily (YYYY-MM-DD) tiles.
DAILY_METRICS: set[str] = {"nightlights", "active_fire"}

_service_lock = asyncio.Lock()
_ee_data_service: USDataService | None = None

# Keep a small cap on concurrent EE computePixels calls per process.
_ee_concurrency = asyncio.Semaphore(4)


@dataclass(frozen=True)
class ResolvedTileRequest:
    metric: str
    date_bucket: str  # YYYY-MM (monthly) or YYYY-MM-DD (daily)
    granularity: TileGranularity


async def _get_ee_data_service() -> USDataService:
    global _ee_data_service

    if _ee_data_service is not None and getattr(_ee_data_service, "_initialized", False):
        return _ee_data_service

    async with _service_lock:
        if _ee_data_service is None:
            _ee_data_service = USDataService()
        if not getattr(_ee_data_service, "_initialized", False):
            await _ee_data_service.initialize()
        return _ee_data_service


def resolve_tile_request(
    metric: str,
    date_str: str,
    requested_granularity: TileGranularity | None,
) -> ResolvedTileRequest:
    """
    Resolve the effective granularity and cache bucket for an overlay tile request.

    - If `requested_granularity` is provided, it takes precedence.
    - Otherwise, we infer daily vs monthly from the date string format.
    - Metrics outside DAILY_METRICS always resolve to monthly.
    """
    is_daily_str = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))
    is_monthly_str = bool(re.match(r"^\d{4}-\d{2}$", date_str))
    if not is_daily_str and not is_monthly_str:
        raise ValueError("date must be YYYY-MM or YYYY-MM-DD")

    if metric not in DAILY_METRICS:
        # Non-daily metrics always bucket monthly.
        return ResolvedTileRequest(metric=metric, date_bucket=date_str[:7], granularity="monthly")

    if requested_granularity == "monthly":
        return ResolvedTileRequest(metric=metric, date_bucket=date_str[:7], granularity="monthly")

    if requested_granularity == "daily":
        if not is_daily_str:
            raise ValueError("daily tiles require date in YYYY-MM-DD format")
        return ResolvedTileRequest(metric=metric, date_bucket=date_str, granularity="daily")

    # No explicit granularity: infer from the date string.
    if is_daily_str:
        return ResolvedTileRequest(metric=metric, date_bucket=date_str, granularity="daily")
    return ResolvedTileRequest(metric=metric, date_bucket=date_str, granularity="monthly")


def _month_date_range(year: int, month: int) -> tuple[str, str]:
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    return start_date, end_date


def _day_date_range(year: int, month: int, day: int) -> tuple[str, str]:
    start_dt = datetime(year, month, day)
    end_dt = start_dt + timedelta(days=1)
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _parse_year_month(date_bucket: str) -> tuple[int, int]:
    parts = date_bucket.split("-")
    return int(parts[0]), int(parts[1])


def _parse_year_month_day(date_bucket: str) -> tuple[int, int, int]:
    parts = date_bucket.split("-")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _build_metric_image(ee, metric: str, resolved: ResolvedTileRequest, geom) -> object:
    """
    Build an Earth Engine Image for the requested metric and date bucket.

    The returned image should contain a *single band* with values in the metric's
    native units (we normalize later using USTileGenerator.VALUE_RANGES).
    """
    if resolved.granularity == "daily":
        year, month, day = _parse_year_month_day(resolved.date_bucket)
        start_date, end_date = _day_date_range(year, month, day)
    else:
        year, month = _parse_year_month(resolved.date_bucket)
        start_date, end_date = _month_date_range(year, month)

    # Original metrics
    if metric == "ndvi":
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        )
        has_images = collection.size().gt(0)

        def mask_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        composite = collection.map(mask_clouds).median()
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")
        return ee.Image(ee.Algorithms.If(has_images, ndvi, ee.Image(0).rename(["ndvi"]))).clip(geom)

    if metric == "nightlights":
        if resolved.granularity == "daily":
            # NASA Black Marble VNP46A2 - daily gap-filled nighttime lights
            collection = (
                ee.ImageCollection("NASA/VIIRS/002/VNP46A2")
                .filterBounds(geom)
                .filterDate(start_date, end_date)
            )
            has_images = collection.size().gt(0)
            image = collection.select(["DNB_BRDF_Corrected_NTL"]).median()

            # Apply quality masking using the mandatory QA flags
            qa = collection.select(["Mandatory_Quality_Flag"]).median()
            quality_mask = qa.lt(3)  # 0,1,2 = high/good/gap-filled
            image = image.updateMask(quality_mask)

            # Clamp to a reasonable range (nW/cm²/sr)
            image = image.clamp(0, 200).rename(["nightlights"])

            # Daily data is missing for some dates; fall back to monthly composites.
            month_start, month_end = _month_date_range(year, month)
            monthly_collection = (
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                .filterBounds(geom)
                .filterDate(month_start, month_end)
                .select(["avg_rad"])
            )
            monthly = monthly_collection.median().clamp(0, 200).rename(["nightlights"])
            monthly_fallback = ee.Image(0).rename(["nightlights"])
            monthly = ee.Image(ee.Algorithms.If(monthly_collection.size().gt(0), monthly, monthly_fallback))

            return ee.Image(ee.Algorithms.If(has_images, image, monthly)).clip(geom)

        # NOAA VIIRS monthly composites
        collection = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["avg_rad"])
        )
        has_images = collection.size().gt(0)
        image = collection.median().rename(["nightlights"])
        fallback = ee.Image(0).rename(["nightlights"])
        return ee.Image(ee.Algorithms.If(has_images, image, fallback)).clip(geom)

    if metric == "urban_density":
        # GHSL is available for specific epochs; pick nearest to the requested year.
        epochs = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
        nearest_epoch = min(epochs, key=lambda x: abs(x - year))

        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
        idx = f"GHS_BUILT_S_E{nearest_epoch}_GLOBE_R2023A_54009_100_V1_0"
        filtered = collection.filter(ee.Filter.eq("system:index", idx))
        image = ee.Image(ee.Algorithms.If(filtered.size().gt(0), filtered.first(), collection.mosaic()))

        return image.select(["built_surface"]).divide(10000).clamp(0, 1).clip(geom)

    if metric == "parking":
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        )
        has_images = collection.size().gt(0)

        def mask_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        composite = collection.map(mask_clouds).median()
        ndbi = composite.normalizedDifference(["B11", "B8"]).rename("ndbi")
        ndbi = ndbi.add(1).divide(2).clamp(0, 1)
        return ee.Image(ee.Algorithms.If(has_images, ndbi, ee.Image(0).rename(["ndbi"]))).clip(geom)

    # Phase 1: Core datasets
    if metric == "land_cover":
        collection = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["built"])
        )
        has_images = collection.size().gt(0)
        image = collection.median()
        fallback = ee.Image(0).rename(["built"])
        return ee.Image(ee.Algorithms.If(has_images, image, fallback)).clip(geom)

    if metric == "surface_water":
        # Monthly history keyed by system:index = YYYY-MM
        target_date = resolved.date_bucket[:7]
        collection = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterBounds(geom)
        filtered = collection.filter(ee.Filter.eq("system:index", target_date))
        image = ee.Image(
            ee.Algorithms.If(filtered.size().gt(0), filtered.first(), ee.Image(0).rename(["water"]))
        )
        water_mask = image.select(["water"]).eq(2)
        return water_mask.clip(geom)

    if metric == "active_fire":
        collection = (
            ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["FRP"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.max(), ee.Image(0)))
        return image.clip(geom)

    # Phase 2: Air quality & weather
    if metric == "no2":
        collection = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["tropospheric_NO2_column_number_density"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.mean(), ee.Image(0)))
        return image.clip(geom)

    if metric == "temperature":
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["temperature_2m"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.mean(), ee.Image(0)))
        image = image.subtract(273.15)  # Kelvin to Celsius
        return image.clip(geom)

    if metric == "precipitation":
        collection = (
            ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["precipitation"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.sum(), ee.Image(0)))
        return image.clip(geom)

    if metric == "aerosol":
        collection = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["absorbing_aerosol_index"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.mean(), ee.Image(0)))
        return image.clip(geom)

    # Phase 3: Agriculture
    if metric == "cropland":
        image = ee.ImageCollection("ESA/WorldCover/v200").first().select(["Map"])
        return image.clip(geom)

    if metric == "evapotranspiration":
        collection = (
            ee.ImageCollection("MODIS/061/MOD16A2GF")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["ET"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.mean(), ee.Image(0)))
        image = image.multiply(0.1)  # Scale factor to mm
        return image.clip(geom)

    if metric == "soil_moisture":
        collection = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["sm_surface"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.mean(), ee.Image(0)))
        return image.clip(geom)

    # Phase 4: Historical & specialized
    if metric == "impervious":
        year_clamped = min(max(year, 1985), 2018)
        image = ee.Image("Tsinghua/FROM-GLC/GAIA/v10")
        urbanized = image.lte(year_clamped).And(image.gt(0))
        return urbanized.clip(geom)

    if metric == "fire_historical":
        collection = (
            ee.ImageCollection("MODIS/061/MOD14A1")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .select(["MaxFRP"])
        )
        image = ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.max(), ee.Image(0)))
        return image.clip(geom)

    if metric == "canopy_height":
        return ee.Image("LARSE/GEDI/GRIDDEDVEG_002/V1/1KM").select(["rh98"]).clip(geom)

    raise ValueError(f"Unsupported metric: {metric}")


async def generate_overlay_tile_png(
    metric: str,
    resolved: ResolvedTileRequest,
    z: int,
    x: int,
    y: int,
    *,
    reject_bounds_mercator: dict[str, float] | None = None,
) -> bytes:
    """
    Generate a single overlay tile PNG from real data sources (Earth Engine).

    If `reject_bounds_mercator` is provided, returns a transparent tile when the
    requested tile does not intersect the given bounding box (Web Mercator meters).
    """
    tile_west, tile_south, tile_east, tile_north = tile_bounds_mercator(z, x, y)

    # Optional quick reject for tiles outside a given bounding box.
    if reject_bounds_mercator is not None and (
        tile_east < reject_bounds_mercator["west"]
        or tile_west > reject_bounds_mercator["east"]
        or tile_north < reject_bounds_mercator["south"]
        or tile_south > reject_bounds_mercator["north"]
    ):
        return create_empty_tile()

    data_service = await _get_ee_data_service()
    ee = data_service._ee  # Initialized in _get_ee_data_service()

    lon_west, lat_south, lon_east, lat_north = tile_bounds(z, x, y)
    geom = ee.Geometry.Rectangle([lon_west, lat_south, lon_east, lat_north])

    image = _build_metric_image(ee, metric, resolved, geom)
    bounds_mercator = {
        "west": tile_west,
        "east": tile_east,
        "south": tile_south,
        "north": tile_north,
    }

    async with _ee_concurrency:
        raster = await data_service._fetch_raster(  # pylint: disable=protected-access
            image, bounds_mercator, width=TILE_SIZE, height=TILE_SIZE
        )

    if raster is None:
        return create_empty_tile()

    # Normalize and colormap in the same way as pre-generated tiles.
    generator = USTileGenerator()
    val_min, val_max = generator.VALUE_RANGES.get(metric, (0.0, 1.0))
    if val_max == val_min:
        val_max = val_min + 1.0

    raster_clean = np.nan_to_num(raster, nan=val_min)
    normalized = (raster_clean - val_min) / (val_max - val_min)
    normalized = np.clip(normalized, 0, 1)

    tile_img = generator._apply_colormap(normalized, metric)  # pylint: disable=protected-access
    buffer = BytesIO()
    tile_img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
