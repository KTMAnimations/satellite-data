from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

# Timeout (seconds) for individual Earth Engine getInfo() calls.
_GEE_GETINFO_TIMEOUT = 120
_GEE_TRANSIENT_RETRY_ATTEMPTS = 3
_GEE_TRANSIENT_RETRY_BASE_DELAY_SECONDS = 0.75

from app.schemas import MetricId
from app.settings import get_settings


Granularity = Literal["daily", "weekly", "monthly"]

# Web Mercator (EPSG:3857) is only defined up to this latitude. Leaflet's default
# CRS clamps the map to this range, and the XYZ tiling scheme expects the full
# extent. If we clip to a smaller latitude (e.g. ±85°), the outermost tile rows
# (y=0 / y=2^z-1) become partially or fully transparent at higher zooms, which
# looks like overlays being "cut off" near the poles.
WEB_MERCATOR_MAX_LAT = 85.05112878

# Avoid using +/-180 exactly: the antimeridian can produce half-world tiles
# (western hemisphere only) depending on Earth Engine tile rendering internals.
GLOBAL_TILE_BOUNDS_WGS84 = (-179.999, -WEB_MERCATOR_MAX_LAT, 179.999, WEB_MERCATOR_MAX_LAT)

# CHIRPS precipitation coverage is approximately 50°S..50°N.
# Feather the transition to ERA5 over a latitude band so the source switch
# does not appear as a hard horizontal seam near North America and Europe.
_PRECIP_CHIRPS_MAX_ABS_LAT = 50.0
_PRECIP_CHIRPS_ERA5_BLEND_HALF_WIDTH_DEG = 6.0


def _precipitation_blend_lat_bounds() -> tuple[float, float]:
    start = _PRECIP_CHIRPS_MAX_ABS_LAT - _PRECIP_CHIRPS_ERA5_BLEND_HALF_WIDTH_DEG
    end = _PRECIP_CHIRPS_MAX_ABS_LAT + _PRECIP_CHIRPS_ERA5_BLEND_HALF_WIDTH_DEG
    return start, end


def _precipitation_era5_weight_for_abs_lat(abs_lat: float) -> float:
    start, end = _precipitation_blend_lat_bounds()
    if abs_lat <= start:
        return 0.0
    if abs_lat >= end:
        return 1.0
    return (abs_lat - start) / (end - start)


@dataclass(frozen=True)
class MetricDefinition:
    id: MetricId
    label: str
    unit: str
    value_range: tuple[float, float]
    palette: list[str]  # hex without '#'
    default_granularity: Granularity
    supported_granularities: set[Granularity]
    scale_m: int | None
    # Transparent cutoff expressed in normalized 0..1 (applied using value_range)
    transparent_below_normalized: float
    # Optional tile-only visualization range. This affects overlay contrast
    # without changing underlying metric values used for analytics.
    tile_viz_range: tuple[float, float] | None = None


METRICS: dict[MetricId, MetricDefinition] = {
    "ndvi": MetricDefinition(
        id="ndvi",
        label="NDVI",
        unit="index (-1 to 1)",
        value_range=(-1.0, 1.0),
        palette=["a50026", "d73027", "f46d43", "fdae61", "fee08b", "d9ef8b", "a6d96a", "66bd63", "1a9850", "006837"],
        default_granularity="weekly",
        supported_granularities={"weekly", "monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
    ),
    "nightlights": MetricDefinition(
        id="nightlights",
        label="Nighttime Lights",
        unit="nW/cm²/sr",
        value_range=(0.0, 100.0),
        # Keep all visible nightlight intensity in a light range so dim areas
        # appear softly lit and bright areas trend toward white.
        palette=["e8c36a", "efd084", "f3db9d", "f7e5b6", "faedcb", "fdf3dc", "fef8ea", "fffbf2", "fffdf8", "ffffff"],
        default_granularity="monthly",
        supported_granularities={"daily", "monthly"},
        scale_m=500,
        transparent_below_normalized=0.02,
    ),
    "surface_water": MetricDefinition(
        id="surface_water",
        label="Surface Water",
        unit="ratio (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
    ),
    "no2": MetricDefinition(
        id="no2",
        label="NO₂",
        unit="mol/m²",
        value_range=(0.0, 0.0002),
        palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=10000,
        transparent_below_normalized=0.001,
        # Typical S5P tropospheric NO2 sits well below the full hard cap.
        tile_viz_range=(0.0, 0.00008),
    ),
    "temperature": MetricDefinition(
        id="temperature",
        label="Temperature",
        unit="°C",
        value_range=(-30.0, 45.0),
        palette=["053061", "2166ac", "4393c3", "92c5de", "d1e5f0", "fddbc7", "f4a582", "d6604d", "b2182b", "67001f"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=11000,
        transparent_below_normalized=0.0,
    ),
    "precipitation": MetricDefinition(
        id="precipitation",
        label="Precipitation",
        unit="mm",
        value_range=(0.0, 500.0),
        palette=["ffffff", "f0f9e8", "ccebc5", "a8ddb5", "7bccc4", "4eb3d3", "2b8cbe", "0868ac", "084081", "252556"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=5500,
        transparent_below_normalized=0.0,
        # Monthly totals are usually concentrated in low-to-mid values.
        tile_viz_range=(0.0, 180.0),
    ),
    "aerosol": MetricDefinition(
        id="aerosol",
        label="Aerosol Index",
        unit="index",
        value_range=(-2.0, 5.0),
        palette=["ffffff", "fdf5e6", "fce0c5", "f9c496", "f4a267", "dd8541", "b2672d", "8a4a1c", "64320e", "321405"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=10000,
        transparent_below_normalized=0.0,
        # Increase contrast for typical urban aerosol values so overlays don't
        # appear almost white in low/negative-index conditions.
        tile_viz_range=(-1.0, 1.0),
    ),
    "cropland": MetricDefinition(
        id="cropland",
        label="Cropland",
        unit="ratio (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["ffffb2", "fed976", "feb24c", "fd8d3c", "f03b20", "bd0026", "228b22", "32cd32", "90ee90", "ffff00"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
    ),
    "evapotranspiration": MetricDefinition(
        id="evapotranspiration",
        label="Evapotranspiration",
        unit="mm",
        # Narrow ET viz range so map overlays use more of the palette. Current
        # ET values (mean of MOD16 8-day ET) are often in the low-to-mid teens.
        value_range=(0.0, 40.0),
        palette=["a6611a", "bf812d", "dfc27d", "e6d8b2", "f5f5dc", "c7eae5", "80cdc1", "35978f", "01665e", "003c30"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=500,
        transparent_below_normalized=0.001,
    ),
    "soil_moisture": MetricDefinition(
        id="soil_moisture",
        label="Soil Moisture",
        unit="m³/m³",
        value_range=(0.0, 0.5),
        palette=["8b4513", "a0522d", "bc8f5f", "d2b48c", "f5deb3", "add8e6", "87ceeb", "4682b4", "4169e1", "00008b"],
        default_granularity="weekly",
        supported_granularities={"weekly", "monthly"},
        scale_m=10000,
        transparent_below_normalized=0.001,
    ),
    "impervious": MetricDefinition(
        id="impervious",
        label="Impervious Surface",
        unit="ratio (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1a1a1a", "000000"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
    ),
    "canopy_height": MetricDefinition(
        id="canopy_height",
        label="Canopy Height",
        unit="m",
        value_range=(0.0, 60.0),
        palette=["f7fcf5", "e5f5e0", "c7e9c0", "a1d99b", "74c476", "41ab5d", "238b45", "006d2c", "004d1c", "00280f"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=1000,
        transparent_below_normalized=0.001,
    ),
    "forest_loss_year": MetricDefinition(
        id="forest_loss_year",
        label="Forest Loss Year",
        unit="year",
        value_range=(2001.0, 2025.0),
        palette=["fff7ec", "fee8c8", "fdd49e", "fdbb84", "fc8d59", "ef6548", "d7301f", "b30000", "7f0000", "4a0000"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=30,
        transparent_below_normalized=0.0,
    ),
    "snow_cover": MetricDefinition(
        id="snow_cover",
        label="Snow Cover",
        unit="%",
        value_range=(0.0, 100.0),
        palette=["0b1f3a", "174a7e", "2b8cbe", "41b6c4", "7fcdbb", "c7e9b4", "edf8b1", "ffffd9", "ffffff", "f7f7f7"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=500,
        # Keep no-snow pixels (value ~= 0) transparent.
        transparent_below_normalized=0.0001,
    ),
    "travel_time_to_cities": MetricDefinition(
        id="travel_time_to_cities",
        label="Travel Time to Cities",
        unit="minutes",
        value_range=(0.0, 720.0),
        palette=["fff7ec", "fee8c8", "fdd49e", "fdbb84", "fc8d59", "ef6548", "d7301f", "b30000", "7f0000", "4a0000"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=1000,
        transparent_below_normalized=0.0,
    ),
}


_ee_initialized = False


def initialize_ee() -> None:
    global _ee_initialized
    if _ee_initialized:
        return

    import ee

    settings = get_settings()
    key_path = settings.gee_key_path
    if key_path.exists():
        with open(key_path, encoding="utf-8") as f:
            key_data = json.load(f)
        service_account_email = key_data.get("client_email")
        if not service_account_email:
            raise RuntimeError("GEE service account key missing client_email")

        # Fall back to the key's own project_id if one isn't configured via env.
        project = settings.gee_project_id or key_data.get("project_id")
        credentials = ee.ServiceAccountCredentials(service_account_email, str(key_path))
        ee.Initialize(credentials, project=project)
    else:
        # Uses `earthengine authenticate` credentials.
        ee.Initialize(project=settings.gee_project_id or None)

    _ee_initialized = True


def reinitialize_ee() -> None:
    """
    Force Earth Engine to re-initialize after the service-account key changes
    (e.g. uploaded via the admin UI). Safe to call at runtime.
    """
    global _ee_initialized

    import ee

    try:
        ee.Reset()
    except Exception:
        # Older earthengine-api versions may lack Reset(); the flag reset below
        # plus a fresh Initialize() is still sufficient.
        pass
    _ee_initialized = False
    initialize_ee()


def geojson_to_ee_geometry(geojson: dict[str, Any]):
    import ee

    geom_type = geojson.get("type")
    if geom_type == "Polygon":
        return ee.Geometry.Polygon(geojson["coordinates"])
    if geom_type == "MultiPolygon":
        return ee.Geometry.MultiPolygon(geojson["coordinates"])
    raise ValueError(f"Unsupported geometry type: {geom_type}")


def _empty_masked_image(band_name: str):
    import ee

    zero = ee.Image(0).rename([band_name])
    return zero.updateMask(ee.Image(0))


def _surface_water_static_fallback(band_name: str):
    """
    Build a global static fallback for surface water.

    Primary static source is JRC occurrence. At very high latitudes where JRC
    is masked/no-data, fill from MOD44W inland-water mask while excluding
    ocean QA classes.
    """
    import ee

    occurrence = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select(["occurrence"])
        .divide(100)
        .toFloat()
        .rename([band_name])
    )

    mod44_latest = ee.Image(ee.ImageCollection("MODIS/006/MOD44W").sort("system:time_start", False).first())
    mod44_water = mod44_latest.select(["water_mask"]).eq(1)
    mod44_qa = mod44_latest.select(["water_mask_QA"])
    # MOD44W QA classes 4/5 are ocean masks; keep only inland-water classes.
    mod44_inland = mod44_water.And(mod44_qa.lt(4)).toFloat().rename([band_name])

    return occurrence.unmask(mod44_inland).unmask(0)


def _mean_of_daily_means(collection, start, end, band_name: str):
    """
    Reduce an ImageCollection into a single Image by:
    1) computing a per-day mean composite, then
    2) averaging those daily composites across the full window.

    This is much faster for collections with many images per day (e.g. Sentinel-5P
    per-orbit products and CAMS sub-daily analyses), and it avoids huge month-long
    reductions that can make tile generation feel "chunky".
    """
    import ee

    day_count = ee.Number(end.difference(start, "day")).ceil().max(1)
    day_offsets = ee.List.sequence(0, day_count.subtract(1))

    # Build a fully-masked image with the same band type as the collection, so
    # empty days can be represented without introducing heterogeneous band types
    # in the daily ImageCollection.
    template = ee.Image(
        ee.Algorithms.If(
            collection.size().gt(0),
            collection.first(),
            _empty_masked_image(band_name),
        )
    ).rename([band_name])
    empty_day = template.updateMask(ee.Image(0))

    def per_day(day_offset):
        d0 = start.advance(day_offset, "day")
        d1 = d0.advance(1, "day")
        day_col = collection.filterDate(d0, d1)
        day_img = ee.Image(ee.Algorithms.If(day_col.size().gt(0), day_col.mean().rename([band_name]), empty_day))
        return day_img.set("system:time_start", d0.millis())

    daily = ee.ImageCollection.fromImages(day_offsets.map(per_day))
    return daily.mean().rename([band_name])


def build_metric_image(
    metric: MetricId,
    start,
    end,
    geom,
    *,
    use_visual_gap_filling: bool = True,
):
    """
    Build an ee.Image with a single band named after the metric.

    `start` and `end` are ee.Date. `geom` is ee.Geometry.
    `use_visual_gap_filling` applies tile-focused seam filling for metrics where
    visual continuity matters. Disable for analytics paths to keep EE graphs
    lighter and more reliable.
    """
    import ee

    band = metric

    if metric == "ndvi":
        # High-resolution NDVI from Sentinel-2 where available. At low zoom
        # levels a single week can have sparse overpasses / clouds, producing
        # visible striping. Fill masked gaps with a lightweight MODIS NDVI
        # composite to keep the overlay visually continuous.
        s2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        )
        s2_has_images = s2.size().gt(0)

        def mask_s2_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        s2_composite = s2.map(mask_s2_clouds).median()
        s2_ndvi = s2_composite.normalizedDifference(["B8", "B4"]).rename([band])

        modis_buffer_days = 16
        modis = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(geom)
            .filterDate(start.advance(-modis_buffer_days, "day"), end.advance(modis_buffer_days, "day"))
        )
        modis_has_images = modis.size().gt(0)

        land_cover = ee.ImageCollection("MODIS/061/MCD12Q1").sort("system:time_start", False).first()
        land_mask = land_cover.select(["LC_Type1"]).neq(0)

        modis_median = modis.median()
        modis_ndvi_raw = modis_median.select(["NDVI"]).multiply(0.0001).clamp(-1, 1).rename([band])
        # SummaryQA: 0=good, 1=marginal, 2=snow/ice, 3=cloudy. Since MODIS is
        # used only as a fill layer, keep everything except cloudy.
        modis_qa_mask = modis_median.select(["SummaryQA"]).lt(3)
        modis_ndvi = modis_ndvi_raw.updateMask(modis_qa_mask).updateMask(land_mask)
        modis_ndvi = ee.Image(ee.Algorithms.If(modis_has_images, modis_ndvi, _empty_masked_image(band)))

        filled = ee.Image(ee.Algorithms.If(s2_has_images, s2_ndvi.unmask(modis_ndvi), modis_ndvi))
        return filled.clip(geom)

    if metric == "nightlights":
        # Daily: NASA Black Marble VNP46A2. Monthly: NOAA composites.
        # Decide daily vs monthly based on bucket duration (<= 2 days => daily).
        bucket_days = end.difference(start, "day")
        use_daily = bucket_days.lte(2)

        def daily_image():
            daily_col = (
                ee.ImageCollection("NASA/VIIRS/002/VNP46A2")
                .filterBounds(geom)
                .filterDate(start, end)
            )
            has_daily = daily_col.size().gt(0)
            image = daily_col.select(["DNB_BRDF_Corrected_NTL"]).median()
            qa = daily_col.select(["Mandatory_Quality_Flag"]).median()
            quality_mask = qa.lt(3)
            image = image.updateMask(quality_mask).clamp(0, 200).rename([band])

            # Fallback to monthly composites for missing days.
            month_start = start.format("YYYY-MM-01")
            month_end = ee.Date(month_start).advance(1, "month")
            monthly_col = (
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                .filterBounds(geom)
                .filterDate(month_start, month_end)
                .select(["avg_rad"])
            )
            monthly = monthly_col.median().clamp(0, 200).rename([band])
            monthly = ee.Image(ee.Algorithms.If(monthly_col.size().gt(0), monthly, _empty_masked_image(band)))

            return ee.Image(ee.Algorithms.If(has_daily, image, monthly)).clip(geom)

        def monthly_image():
            monthly_col = (
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                .filterBounds(geom)
                .filterDate(start, end)
                .select(["avg_rad"])
            )
            has_images = monthly_col.size().gt(0)
            image = monthly_col.median().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        return ee.Image(ee.Algorithms.If(use_daily, daily_image(), monthly_image()))

    if metric == "surface_water":
        # Primary: JRC MonthlyHistory (ends at 2021-12). system:index uses YYYY_MM.
        # Per-pixel fallback chain:
        #   monthly class -> Dynamic World water probability -> static fallback.
        # Static fallback fills JRC's high-latitude no-data with MOD44W inland water.
        target_month = start.format("YYYY_MM")
        monthly = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterBounds(geom).select(["water"])
        filtered = monthly.filter(ee.Filter.eq("system:index", target_month))
        has_month = filtered.size().gt(0)

        monthly_img = ee.Image(
            ee.Algorithms.If(
                has_month,
                filtered.first(),
                _empty_masked_image("water").rename(["water"]),
            )
        )
        monthly_band = monthly_img.select(["water"])
        # In MonthlyHistory: 0=no observation, 1=not water, 2=water.
        # Keep no-observation pixels masked so fallbacks can fill them.
        monthly_valid = monthly_band.neq(0)
        monthly_water = monthly_band.eq(2).toFloat().rename([band]).updateMask(monthly_valid)

        # Dynamic World water probability for recent dates where JRC has no monthly
        # history (e.g. >2021). Keep masked gaps for static fallback filling.
        dw = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["water"])
        )
        dw_has = dw.size().gt(0)
        dw_img = ee.Image(ee.Algorithms.If(dw_has, dw.median().rename([band]), _empty_masked_image(band)))

        static_fallback = _surface_water_static_fallback(band)
        fallback = dw_img.unmask(static_fallback)
        return monthly_water.unmask(fallback).clip(geom)

    if metric == "no2":
        # Sentinel-5P NO2 is per-orbit (many images per day). Reduce to daily
        # means first so monthly tiles stay responsive at low zoom.
        s5p = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
            .filterBounds(geom)
            .select(["tropospheric_NO2_column_number_density"], [band])
        )
        has_images = s5p.filterDate(start, end).size().gt(0)
        image = _mean_of_daily_means(s5p, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "temperature":
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["temperature_2m"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().subtract(273.15).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "precipitation":
        # CHIRPS has better spatial resolution but only covers ~50°S..50°N.
        # Blend in ERA5-Land precipitation with a feathered latitude transition
        # so there is no hard source seam at the CHIRPS coverage edge.
        chirps = (
            ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["precipitation"])
        )
        chirps_has_images = chirps.size().gt(0)
        chirps_img = chirps.sum().rename([band])

        era5 = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["total_precipitation_sum"])
        )
        era5_has_images = era5.size().gt(0)
        # ERA5-Land precip is in meters; convert to mm.
        era5_img = era5.sum().multiply(1000).rename([band])

        chirps_img = ee.Image(ee.Algorithms.If(chirps_has_images, chirps_img, _empty_masked_image(band)))
        era5_img = ee.Image(ee.Algorithms.If(era5_has_images, era5_img, _empty_masked_image(band)))

        has_both = chirps_has_images.And(era5_has_images)
        blend_start_lat, blend_end_lat = _precipitation_blend_lat_bounds()
        abs_lat = ee.Image.pixelLonLat().select(["latitude"]).abs()
        era5_weight = abs_lat.subtract(blend_start_lat).divide(blend_end_lat - blend_start_lat).clamp(0, 1)
        chirps_weight = ee.Image(1).subtract(era5_weight)

        blended = (
            chirps_img.unmask(0)
            .multiply(chirps_weight)
            .add(era5_img.unmask(0).multiply(era5_weight))
            .rename([band])
        )
        combined_mask = chirps_img.mask().unmask(0).max(era5_img.mask().unmask(0))
        blended = blended.updateMask(combined_mask.gt(0))

        fallback = chirps_img.unmask(era5_img)
        image = ee.Image(ee.Algorithms.If(has_both, blended, fallback))
        return image.clip(geom)

    if metric == "aerosol":
        # Sentinel-5P (S5P) collections are per-orbit (many images per day). A
        # naive monthly `.mean()` can involve hundreds of images and produces
        # very slow cold tile renders. Reduce to daily means first to keep
        # monthly tiles responsive.
        s5p = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
            .filterBounds(geom)
            .select(["absorbing_aerosol_index"], [band])
        )

        has_images = s5p.filterDate(start, end).size().gt(0)
        image = _mean_of_daily_means(s5p, start, end, band)

        base = ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band)))
        if not use_visual_gap_filling:
            return base.clip(geom)

        # S5P daily coverage can have masked gaps (orbit seams / QA), which show
        # up as streaks at tile-scale. Fill masked pixels with a short rolling
        # composite to keep the overlay visually continuous.
        fill_days = 7
        fill_start = start.advance(-fill_days, "day")
        fill_end = end.advance(fill_days, "day")
        has_fill = s5p.filterDate(fill_start, fill_end).size().gt(0)
        fill = _mean_of_daily_means(s5p, fill_start, fill_end, band)

        fill = ee.Image(ee.Algorithms.If(has_fill, fill, _empty_masked_image(band)))
        filled = base.unmask(fill)

        # Final pass: fill any remaining thin masked seams using a small spatial
        # neighborhood mean that ignores masked neighbors. (Earth Engine's
        # focal_mean preserves masks, so it won't populate values into the
        # missing pixels we want to fill.)
        kernel_radius_px = 3
        kernel = ee.Kernel.square(radius=kernel_radius_px, units="pixels", normalize=False)

        # A single pass is usually enough after temporal filling, and keeps tile
        # generation fast (especially for monthly buckets).
        for _ in range(1):
            numerator = filled.unmask(0).convolve(kernel)
            denominator = filled.mask().unmask(0).convolve(kernel)
            seam_fill = numerator.divide(denominator).updateMask(denominator.gt(0))
            filled = filled.unmask(seam_fill)

        # Polar night (and other retrieval constraints) can leave large regions
        # completely masked, which looks like the layer is "misaligned" near the
        # top of the Web Mercator map. Fill remaining gaps with a CAMS aerosol
        # optical depth proxy so the overlay stays continuous.
        cams = (
            ee.ImageCollection("ECMWF/CAMS/NRT")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["total_aerosol_optical_depth_at_550nm_surface"], ["aod"])
        )
        cams_has_images = cams.size().gt(0)
        cams_aod = _mean_of_daily_means(cams, start, end, "aod")
        # Scale AOD (typically ~0..1+) into the aerosol-index visualization range
        # so low-AOD regions remain near-white instead of strongly tinting the map.
        cams_scaled = cams_aod.multiply(7).subtract(2).clamp(-2, 5).rename([band])
        cams_scaled = ee.Image(ee.Algorithms.If(cams_has_images, cams_scaled, _empty_masked_image(band)))
        filled = filled.unmask(cams_scaled)

        return filled.clip(geom)

    if metric == "cropland":
        # Cropland proxy:
        # - Base mask from ESA WorldCover (2021): Map class 40 = cropland.
        # - Temporal signal from Dynamic World crops probability (near real-time).
        #
        # This keeps the metric interpretable as a fraction (0..1) over the AOI,
        # while allowing month-to-month variation for recent years.
        worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select(["Map"])
        cropland_mask = worldcover.eq(40).unmask(0).rename(["mask"])

        dw = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["crops"])
        )
        dw_has = dw.size().gt(0)
        dw_crops = dw.median().unmask(0).rename(["crops"])
        dw_crops = ee.Image(ee.Algorithms.If(dw_has, dw_crops, cropland_mask.rename(["crops"])))

        # Only count crop probability within the WorldCover cropland extent.
        cropland = dw_crops.multiply(cropland_mask.rename(["crops"])).rename([band])
        return cropland.clip(geom)

    if metric == "evapotranspiration":
        collection = (
            ee.ImageCollection("MODIS/061/MOD16A2GF")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["ET"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().multiply(0.1).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "soil_moisture":
        # SMAP L4 soil moisture is sub-daily. Reduce to daily means first so
        # weekly/monthly buckets don't require aggregating hundreds of images.
        collection = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["sm_surface"], [band])
        )
        has_images = collection.size().gt(0)
        native_proj = ee.Image(ee.Algorithms.If(has_images, collection.first(), _empty_masked_image(band))).projection()
        image = _mean_of_daily_means(collection, start, end, band).setDefaultProjection(native_proj).resample("bilinear")
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "impervious":
        # GAIA stores the year of urbanization as an index:
        #   1 => 1985 ... 34 => 2018. Non-urban pixels are masked.
        #
        # Convert requested year -> index and unmask to 0 so reduceRegion means
        # represent a true fraction of the AOI (not "mean over only urban pixels").
        year = ee.Number.parse(start.format("YYYY"))
        year_clamped = year.min(2018).max(1985)
        year_index = year_clamped.subtract(1984)

        gaia = ee.Image("Tsinghua/FROM-GLC/GAIA/v10").select(["change_year_index"]).unmask(0)
        urbanized = gaia.lte(year_index).And(gaia.gt(0)).unmask(0).rename([band])
        return urbanized.clip(geom)

    if metric == "forest_loss_year":
        # Hansen `lossyear`: 1..24 -> 2001..2024, with 0 meaning "no loss".
        hansen = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")
        lossyear = hansen.select(["lossyear"])
        image = lossyear.updateMask(lossyear.gt(0)).add(2000).rename([band])
        return image.clip(geom)

    if metric == "snow_cover":
        collection = ee.ImageCollection("MODIS/061/MOD10A1").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        image = collection.select(["NDSI_Snow_Cover"]).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "canopy_height":
        # GEDI gridded vegetation structure: use RH98 (proxy for canopy height).
        # Note: GEDI is mounted on the ISS (inclination ~51.6°), so the gridded
        # product has no coverage north of ~51.6°N / south of ~51.6°S.
        #
        # To avoid a hard "break" line at the GEDI swath edge, fall back to the
        # global 1km canopy height (2005) product where GEDI has no data.
        year = ee.Number.parse(start.format("YYYY"))
        # Use year-specific composites when available so time series can vary.
        idx = ee.String(
            ee.Algorithms.If(
                year.lte(2019),
                "gediv002_rh-98-a0_vf_20190417_20191231",
                ee.Algorithms.If(
                    year.eq(2020),
                    "gediv002_rh-98-a0_vf_20200101_20201231",
                    ee.Algorithms.If(
                        year.eq(2021),
                        "gediv002_rh-98-a0_vf_20210101_20211231",
                        ee.Algorithms.If(
                            year.eq(2022),
                            "gediv002_rh-98-a0_vf_20220101_20221231",
                            ee.Algorithms.If(
                                year.eq(2023),
                                "gediv002_rh-98-a0_vf_20230101_20230316",
                                # Fallback: full GEDI window (static).
                                "gediv002_rh-98-a0_vf_20190417_20230316",
                            ),
                        ),
                    ),
                ),
            )
        )

        gedi_rh98 = ee.ImageCollection("LARSE/GEDI/GRIDDEDVEG_002/V1/1KM").filter(ee.Filter.eq("system:index", idx))
        has_gedi = gedi_rh98.size().gt(0)
        gedi = ee.Image(
            ee.Algorithms.If(
                has_gedi,
                ee.Image(gedi_rh98.first()).select(["median"]).rename([band]),
                _empty_masked_image(band),
            )
        )

        simard = ee.Image("NASA/JPL/global_forest_canopy_height_2005").select(["1"]).rename([band])
        # Prefer GEDI where present, fall back to Simard elsewhere. Mosaic unions
        # footprints; unmask alone won't expand the GEDI swath footprint.
        image = ee.ImageCollection.fromImages([gedi, simard]).mosaic()
        return image.clip(geom)

    if metric == "travel_time_to_cities":
        image = ee.Image("projects/malariaatlasproject/assets/accessibility/accessibility_to_cities/2015_v1_0")
        image = image.select([0]).rename([band])
        return image.clip(geom)

    raise ValueError(f"Unsupported metric: {metric}")


def build_metric_image_for_tiles(metric: MetricId, start, end, geom, *, z: int | None):
    """
    Build a tile-optimized image graph for map rendering.

    At very low zooms, some high-resolution products are unnecessarily expensive.
    This function swaps in cheaper proxies where appropriate while preserving
    the same value ranges and semantics used by map overlays.
    """
    import ee

    def _modis_land_cover_for_year():
        all_years = ee.ImageCollection("MODIS/061/MCD12Q1")
        latest = ee.Image(all_years.sort("system:time_start", False).first())
        latest_year = ee.Number.parse(latest.date().format("YYYY"))
        year = ee.Number.parse(start.format("YYYY")).min(latest_year).max(2001)
        year_start = ee.Date.fromYMD(year, 1, 1)
        year_end = year_start.advance(1, "year")
        by_year = all_years.filterDate(year_start, year_end)
        return ee.Image(ee.Algorithms.If(by_year.size().gt(0), by_year.first(), latest))

    if z is not None and z <= 6:
        # Low-zoom NDVI: use MODIS-only composite (global, coarse) instead of
        # Sentinel-2 + cloud masking. This keeps z<=6 renders responsive and
        # avoids global S2 graph explosions for world-scale tiles.
        if metric == "ndvi":
            band = metric
            modis_buffer_days = 16
            modis = (
                ee.ImageCollection("MODIS/061/MOD13Q1")
                .filterBounds(geom)
                .filterDate(start.advance(-modis_buffer_days, "day"), end.advance(modis_buffer_days, "day"))
            )
            modis_has_images = modis.size().gt(0)

            land_cover = ee.ImageCollection("MODIS/061/MCD12Q1").sort("system:time_start", False).first()
            land_mask = land_cover.select(["LC_Type1"]).neq(0)

            modis_median = modis.median()
            modis_ndvi_raw = modis_median.select(["NDVI"]).multiply(0.0001).clamp(-1, 1).rename([band])
            modis_qa_mask = modis_median.select(["SummaryQA"]).lt(3)
            modis_ndvi = modis_ndvi_raw.updateMask(modis_qa_mask).updateMask(land_mask)
            modis_ndvi = ee.Image(ee.Algorithms.If(modis_has_images, modis_ndvi, _empty_masked_image(band)))
            return modis_ndvi.clip(geom)

        # Low-zoom surface water: avoid Dynamic World for responsiveness.
        # Fill monthly no-data pixels using the static fallback chain.
        if metric == "surface_water":
            target_month = start.format("YYYY_MM")
            monthly = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterBounds(geom).select(["water"])
            filtered = monthly.filter(ee.Filter.eq("system:index", target_month))
            has_month = filtered.size().gt(0)

            monthly_img = ee.Image(
                ee.Algorithms.If(
                    has_month,
                    filtered.first(),
                    _empty_masked_image("water").rename(["water"]),
                )
            )
            monthly_band = monthly_img.select(["water"])
            monthly_valid = monthly_band.neq(0)
            monthly_water = monthly_band.eq(2).toFloat().rename([metric]).updateMask(monthly_valid)

            static_fallback = _surface_water_static_fallback(metric)
            return monthly_water.unmask(static_fallback).clip(geom)

    return build_metric_image(metric, start, end, geom)


def bucket_starts(start_date: date, end_date: date, granularity: Granularity) -> list[date]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    if granularity == "daily":
        days = (end_date - start_date).days
        return [start_date + timedelta(days=i) for i in range(days + 1)]

    if granularity == "weekly":
        starts = []
        current = start_date
        while current <= end_date:
            starts.append(current)
            current = current + timedelta(days=7)
        return starts

    # monthly
    starts = []
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        starts.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return starts


def bucket_end(start: date, granularity: Granularity) -> date:
    if granularity == "daily":
        return start + timedelta(days=1)
    if granularity == "weekly":
        return start + timedelta(days=7)
    # monthly
    if start.month == 12:
        return date(start.year + 1, 1, 1)
    return date(start.year, start.month + 1, 1)


def format_bucket_date(d: date, granularity: Granularity) -> str:
    if granularity == "monthly":
        return d.strftime("%Y-%m")
    return d.isoformat()


def _is_transient_gee_error_message(message: str) -> bool:
    msg = message.lower()
    markers = (
        "an internal error has occurred",
        "internal error",
        "computation timed out",
        "deadline exceeded",
        "service unavailable",
        "please try again",
        "connection reset",
        "temporarily unavailable",
    )
    return any(marker in msg for marker in markers)


def compute_time_series(
    *,
    geometry_geojson: dict[str, Any],
    metric: MetricId,
    start_date: date,
    end_date: date,
    granularity: Granularity,
) -> list[tuple[str, float]]:
    """
    Compute a (date, value) time series using Earth Engine server-side reduction.

    Returns a list of (date_str, value) pairs. Missing values are omitted.
    """
    initialize_ee()
    import ee

    # Ensure EE requests fail fast enough to prevent indefinitely stuck export jobs.
    ee.data.setDeadline(_GEE_GETINFO_TIMEOUT * 1000)

    metric_def = METRICS[metric]
    if granularity not in metric_def.supported_granularities:
        granularity = metric_def.default_granularity

    settings = get_settings()
    starts = bucket_starts(start_date, end_date, granularity)
    if len(starts) > settings.max_timeseries_points:
        raise ValueError(f"Too many points ({len(starts)}). Use a smaller date range or coarser granularity.")

    geom = geojson_to_ee_geometry(geometry_geojson)

    date_strings = [d.isoformat() for d in starts]

    fmt = "YYYY-MM" if granularity == "monthly" else "YYYY-MM-dd"

    reducer = ee.Reducer.mean()

    def per_bucket(ds):
        d0 = ee.Date(ds)
        d1 = ee.Date(ds).advance(1, "day") if granularity == "daily" else (
            ee.Date(ds).advance(7, "day") if granularity == "weekly" else ee.Date(ds).advance(1, "month")
        )
        # Disable tile-only visual gap filling for analytics to keep compute graphs
        # smaller and reduce EE internal failures/timeouts on heavier metrics.
        img = build_metric_image(metric, d0, d1, geom, use_visual_gap_filling=False)
        reduced = img.reduceRegion(
            reducer=reducer,
            geometry=geom,
            scale=metric_def.scale_m,
            maxPixels=1e13,
            bestEffort=True,
        )
        value = reduced.get(metric)
        return ee.Feature(None, {"date": d0.format(fmt), "value": value})

    def _parse_features(info: dict[str, Any]) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for feat in info.get("features", []):
            props = feat.get("properties", {})
            d = props.get("date")
            v = props.get("value")
            if d is None or v is None:
                continue
            try:
                out.append((str(d), float(v)))
            except Exception:
                continue
        return out

    # Earth Engine limits the number of concurrent aggregations a single request can
    # trigger. Mapping reduceRegion over long date lists can exceed that limit (e.g.
    # NDVI monthly over 2+ years). Chunk the date list to keep requests reliable.
    chunk_size = 20

    def fetch_dates(dates: list[str]) -> list[tuple[str, float]]:
        """
        Fetch a chunk of dates, recursively splitting if Earth Engine rejects the
        request due to concurrent aggregation limits.
        """
        for attempt in range(_GEE_TRANSIENT_RETRY_ATTEMPTS):
            ee_dates = ee.List(dates)
            fc = ee.FeatureCollection(ee_dates.map(per_bucket))
            try:
                info = fc.getInfo()
                return _parse_features(info)
            except Exception as e:
                message = str(e)
                lowered = message.lower()

                # Common when mapping reduceRegion over many dates.
                if "Too many concurrent aggregations" in message and len(dates) > 1:
                    mid = len(dates) // 2
                    return fetch_dates(dates[:mid]) + fetch_dates(dates[mid:])

                timed_out = "timed out" in lowered or "deadline exceeded" in lowered
                if timed_out:
                    if attempt < _GEE_TRANSIENT_RETRY_ATTEMPTS - 1:
                        delay = _GEE_TRANSIENT_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                        time.sleep(delay)
                        continue

                    if len(dates) > 1:
                        mid = len(dates) // 2
                        return fetch_dates(dates[:mid]) + fetch_dates(dates[mid:])

                    raise TimeoutError(
                        f"Earth Engine getInfo() timed out after {_GEE_GETINFO_TIMEOUT}s "
                        f"for {len(dates)} date buckets. Try a smaller date range or coarser granularity."
                    ) from e

                if _is_transient_gee_error_message(message):
                    if attempt < _GEE_TRANSIENT_RETRY_ATTEMPTS - 1:
                        delay = _GEE_TRANSIENT_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                        time.sleep(delay)
                        continue

                    if len(dates) > 1:
                        mid = len(dates) // 2
                        return fetch_dates(dates[:mid]) + fetch_dates(dates[mid:])

                raise

        raise RuntimeError("Unreachable retry loop state in fetch_dates")

    out: list[tuple[str, float]] = []
    for i in range(0, len(date_strings), chunk_size):
        out.extend(fetch_dates(date_strings[i : i + chunk_size]))

    out.sort(key=lambda x: x[0])
    return out


_TILE_CACHE_MAX_SIZE = 500


class _BoundedTTLCache(dict):
    """Dict with a max size. Evicts oldest entries (FIFO) when full."""

    def __init__(self, maxsize: int = _TILE_CACHE_MAX_SIZE):
        super().__init__()
        self._maxsize = maxsize

    def __setitem__(self, key: str, value: Any) -> None:
        # Evict oldest entries when at capacity
        while len(self) >= self._maxsize:
            oldest_key = next(iter(self))
            dict.__delitem__(self, oldest_key)
        dict.__setitem__(self, key, value)


_tile_template_cache: _BoundedTTLCache = _BoundedTTLCache()
_tile_fetcher_cache: _BoundedTTLCache = _BoundedTTLCache()
_tile_cache_version = 31


def _tile_visualization_range(metric_def: MetricDefinition) -> tuple[float, float]:
    return metric_def.tile_viz_range or metric_def.value_range


def _tile_render_variant(metric: MetricId, *, z: int | None) -> str:
    if z is not None and z <= 6 and metric in {"ndvi", "surface_water"}:
        return f"{metric}_low_zoom_proxy"
    return "default"


def get_tile_fetcher(metric: MetricId, date_bucket: str, granularity: Granularity, *, z: int | None = None) -> Any:
    """
    Return an ee.data.TileFetcher for fetching PNG tiles server-side.

    Newer Earth Engine Python API versions often return an empty `token` for
    service account credentials, which prevents browsers from fetching tiles
    directly from earthengine.googleapis.com. We proxy tiles through the API.
    """
    initialize_ee()
    import ee

    settings = get_settings()
    variant = _tile_render_variant(metric, z=z)
    cache_key = f"v{_tile_cache_version}:{metric}:{granularity}:{date_bucket}:{variant}"
    now = time.time()
    cached = _tile_fetcher_cache.get(cache_key)
    if cached and now - cached[0] < settings.tile_token_ttl_seconds:
        return cached[1]

    metric_def = METRICS[metric]

    # Parse date bucket
    if granularity == "monthly":
        start_py = date.fromisoformat(f"{date_bucket}-01")
    else:
        start_py = date.fromisoformat(date_bucket)
    end_py = bucket_end(start_py, granularity)

    start = ee.Date(start_py.isoformat())
    end = ee.Date(end_py.isoformat())
    geom = ee.Geometry.Rectangle(list(GLOBAL_TILE_BOUNDS_WGS84), proj="EPSG:4326", geodesic=False)
    img = build_metric_image_for_tiles(metric, start, end, geom, z=z)

    vmin, vmax = metric_def.value_range
    img = img.clamp(vmin, vmax)
    threshold = vmin + metric_def.transparent_below_normalized * (vmax - vmin)
    img = img.updateMask(img.gte(threshold))

    viz_min, viz_max = _tile_visualization_range(metric_def)

    # Keep EE tiles fully opaque; Leaflet controls opacity client-side.
    mapid = img.getMapId({"min": viz_min, "max": viz_max, "palette": metric_def.palette, "opacity": 1.0})
    tile_fetcher = mapid.get("tile_fetcher")
    if not tile_fetcher:
        raise RuntimeError("Earth Engine TileFetcher unavailable for this environment.")

    _tile_fetcher_cache[cache_key] = (now, tile_fetcher)
    return tile_fetcher


def get_tile_template(metric: MetricId, date_bucket: str, granularity: Granularity, *, opacity: float | None = None) -> dict[str, Any]:
    """
    Return the API tile URL template + viz metadata for the requested metric/date bucket.

    Note: this intentionally does **not** call Earth Engine. EE initialization and
    mapId/token creation happens lazily on the first tile PNG fetch.
    """
    settings = get_settings()
    metric_def = METRICS[metric]
    opacity = settings.default_tile_opacity if opacity is None else float(opacity)

    cache_key = f"v{_tile_cache_version}:{metric}:{granularity}:{date_bucket}:{opacity}"
    now = time.time()
    cached = _tile_template_cache.get(cache_key)
    if cached and now - cached[0] < settings.tile_token_ttl_seconds:
        return cached[1]

    vmin, vmax = _tile_visualization_range(metric_def)
    # Add a small cache-buster query param so browser caches don't pin previously
    # bad tiles (e.g. from earlier antimeridian rendering issues).
    tile_url = (
        f"{settings.api_v1_prefix}/tiles/{metric}/{granularity}/{date_bucket}/{{z}}/{{x}}/{{y}}.png"
        f"?v={_tile_cache_version}"
    )

    payload = {
        "metric": metric,
        "date_bucket": date_bucket,
        "granularity": granularity,
        "tile_url": tile_url,
        "min": vmin,
        "max": vmax,
        "palette": [f"#{c}" for c in metric_def.palette],
        "opacity": opacity,
        "attribution": "EE datasets",
    }

    _tile_template_cache[cache_key] = (now, payload)
    return payload
