from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from app.schemas import MetricId
from app.settings import get_settings


Granularity = Literal["daily", "weekly", "monthly"]


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
        palette=["000000", "1e0032", "3c0064", "640096", "963296", "c86464", "ff9632", "ffc864", "ffff96", "ffffff"],
        default_granularity="monthly",
        supported_granularities={"daily", "monthly"},
        scale_m=500,
        transparent_below_normalized=0.02,
    ),
    "urban_density": MetricDefinition(
        id="urban_density",
        label="Urban Density",
        unit="ratio (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["ffffe5", "fff7bc", "fee391", "fec44f", "fe9929", "ec7014", "cc4c02", "993404", "662506", "331203"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=100,
        transparent_below_normalized=0.001,
    ),
    "parking": MetricDefinition(
        id="parking",
        label="Parking (proxy)",
        unit="index (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "03132b"],
        default_granularity="weekly",
        supported_granularities={"weekly", "monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
    ),
    "land_cover": MetricDefinition(
        id="land_cover",
        label="Built-up (Dynamic World)",
        unit="probability (0 to 1)",
        value_range=(0.0, 1.0),
        palette=["f7f4f9", "e7e1ef", "d4b9da", "c994c7", "ba6eb4", "aa4da0", "98318b", "7a0177", "5c015e", "3f003c"],
        default_granularity="weekly",
        supported_granularities={"weekly", "monthly"},
        scale_m=30,
        transparent_below_normalized=0.001,
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
    "active_fire": MetricDefinition(
        id="active_fire",
        label="Active Fire (FRP)",
        unit="MW",
        value_range=(0.0, 500.0),
        palette=["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "fc4e2a", "e31a1c", "bd0026", "800026", "500000"],
        default_granularity="daily",
        supported_granularities={"daily", "monthly"},
        scale_m=500,
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
        transparent_below_normalized=0.001,
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
        transparent_below_normalized=0.001,
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
        transparent_below_normalized=0.001,
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
        value_range=(0.0, 300.0),
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
    "fire_historical": MetricDefinition(
        id="fire_historical",
        label="Historical Fire (FRP)",
        unit="MW",
        value_range=(0.0, 500.0),
        palette=["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "fc4e2a", "e31a1c", "bd0026", "800026", "500000"],
        default_granularity="monthly",
        supported_granularities={"monthly"},
        scale_m=1000,
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
}


_ee_initialized = False


def initialize_ee() -> None:
    global _ee_initialized
    if _ee_initialized:
        return

    import ee

    settings = get_settings()
    if settings.gee_service_account_key and settings.gee_project_id:
        with open(settings.gee_service_account_key, encoding="utf-8") as f:
            key_data = json.load(f)
        service_account_email = key_data.get("client_email")
        if not service_account_email:
            raise RuntimeError("GEE service account key missing client_email")

        credentials = ee.ServiceAccountCredentials(service_account_email, settings.gee_service_account_key)
        ee.Initialize(credentials, project=settings.gee_project_id)
    else:
        # Uses `earthengine authenticate` credentials.
        ee.Initialize(project=settings.gee_project_id or None)

    _ee_initialized = True


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


def build_metric_image(metric: MetricId, start, end, geom):
    """
    Build an ee.Image with a single band named after the metric.

    `start` and `end` are ee.Date. `geom` is ee.Geometry.
    """
    import ee

    band = metric

    if metric == "ndvi":
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        )
        has_images = collection.size().gt(0)

        def mask_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        composite = collection.map(mask_clouds).median()
        ndvi = composite.normalizedDifference(["B8", "B4"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, ndvi, _empty_masked_image(band))).clip(geom)

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

    if metric == "urban_density":
        year = ee.Number.parse(start.format("YYYY"))
        epochs = ee.List([1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030])
        nearest_epoch = epochs.sort(epochs.map(lambda e: ee.Number(e).subtract(year).abs())).get(0)
        idx = ee.String("GHS_BUILT_S_E").cat(ee.Number(nearest_epoch).format()).cat("_GLOBE_R2023A_54009_100_V1_0")
        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
        filtered = collection.filter(ee.Filter.eq("system:index", idx))
        image = ee.Image(ee.Algorithms.If(filtered.size().gt(0), filtered.first(), collection.mosaic()))
        fraction = image.select(["built_surface"]).divide(10000).clamp(0, 1).rename([band])
        return fraction.clip(geom)

    if metric == "parking":
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        )
        has_images = collection.size().gt(0)

        def mask_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        composite = collection.map(mask_clouds).median()
        ndbi = composite.normalizedDifference(["B11", "B8"]).rename(["ndbi"])
        parking_idx = ndbi.add(1).divide(2).clamp(0, 1).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, parking_idx, _empty_masked_image(band))).clip(geom)

    if metric == "land_cover":
        collection = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["built"])
        )
        has_images = collection.size().gt(0)
        image = collection.median().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "surface_water":
        target_month = start.format("YYYY-MM")
        collection = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterBounds(geom)
        filtered = collection.filter(ee.Filter.eq("system:index", target_month))
        image = ee.Image(ee.Algorithms.If(filtered.size().gt(0), filtered.first(), _empty_masked_image("water").rename(["water"])))
        water_mask = image.select(["water"]).eq(2).rename([band])
        return water_mask.clip(geom)

    if metric == "active_fire":
        collection = (
            ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["FRP"])
        )
        has_images = collection.size().gt(0)
        image = collection.max().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "no2":
        collection = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["tropospheric_NO2_column_number_density"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().rename([band])
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
        collection = (
            ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["precipitation"])
        )
        has_images = collection.size().gt(0)
        image = collection.sum().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "aerosol":
        collection = (
            ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["absorbing_aerosol_index"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "cropland":
        # ESA WorldCover: Map class 40 = cropland. Expose as fraction 0..1.
        worldcover = ee.ImageCollection("ESA/WorldCover/v200").first().select(["Map"])
        cropland = worldcover.eq(40).rename([band])
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
        collection = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["sm_surface"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "impervious":
        year = ee.Number.parse(start.format("YYYY"))
        year_clamped = year.min(2018).max(1985)
        gaia = ee.Image("Tsinghua/FROM-GLC/GAIA/v10")
        urbanized = gaia.lte(year_clamped).And(gaia.gt(0)).rename([band])
        return urbanized.clip(geom)

    if metric == "fire_historical":
        collection = (
            ee.ImageCollection("MODIS/061/MOD14A1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["MaxFRP"])
        )
        has_images = collection.size().gt(0)
        image = collection.max().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "canopy_height":
        return ee.Image("LARSE/GEDI/GRIDDEDVEG_002/V1/1KM").select(["rh98"]).rename([band]).clip(geom)

    raise ValueError(f"Unsupported metric: {metric}")


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

    metric_def = METRICS[metric]
    if granularity not in metric_def.supported_granularities:
        granularity = metric_def.default_granularity

    settings = get_settings()
    starts = bucket_starts(start_date, end_date, granularity)
    if len(starts) > settings.max_timeseries_points:
        raise ValueError(f"Too many points ({len(starts)}). Use a smaller date range or coarser granularity.")

    geom = geojson_to_ee_geometry(geometry_geojson)

    date_strings = [d.isoformat() for d in starts]
    ee_dates = ee.List(date_strings)

    fmt = "YYYY-MM" if granularity == "monthly" else "YYYY-MM-dd"

    reducer = ee.Reducer.mean()

    def per_bucket(ds):
        d0 = ee.Date(ds)
        d1 = ee.Date(ds).advance(1, "day") if granularity == "daily" else (
            ee.Date(ds).advance(7, "day") if granularity == "weekly" else ee.Date(ds).advance(1, "month")
        )
        img = build_metric_image(metric, d0, d1, geom)
        reduced = img.reduceRegion(
            reducer=reducer,
            geometry=geom,
            scale=metric_def.scale_m,
            maxPixels=1e13,
            bestEffort=True,
        )
        value = reduced.get(metric)
        return ee.Feature(None, {"date": d0.format(fmt), "value": value})

    fc = ee.FeatureCollection(ee_dates.map(per_bucket))
    info = fc.getInfo()

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

    out.sort(key=lambda x: x[0])
    return out


_tile_template_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def get_tile_template(metric: MetricId, date_bucket: str, granularity: Granularity, *, opacity: float | None = None) -> dict[str, Any]:
    """
    Return an Earth Engine tile URL template for the requested metric/date bucket.

    Cached in-process with a TTL (tokens expire).
    """
    initialize_ee()
    import ee

    settings = get_settings()
    metric_def = METRICS[metric]
    opacity = settings.default_tile_opacity if opacity is None else float(opacity)

    cache_key = f"{metric}:{granularity}:{date_bucket}:{opacity}"
    now = time.time()
    cached = _tile_template_cache.get(cache_key)
    if cached and now - cached[0] < settings.tile_token_ttl_seconds:
        return cached[1]

    # Parse date bucket
    if granularity == "monthly":
        start_py = date.fromisoformat(f"{date_bucket}-01")
    else:
        start_py = date.fromisoformat(date_bucket)
    end_py = bucket_end(start_py, granularity)

    start = ee.Date(start_py.isoformat())
    end = ee.Date(end_py.isoformat())
    geom = ee.Geometry.Rectangle([-180, -85, 180, 85], proj="EPSG:4326", geodesic=False)
    img = build_metric_image(metric, start, end, geom)

    vmin, vmax = metric_def.value_range
    threshold = vmin + metric_def.transparent_below_normalized * (vmax - vmin)
    img = img.updateMask(img.gt(threshold))

    mapid = img.getMapId({"min": vmin, "max": vmax, "palette": metric_def.palette, "opacity": opacity})
    tile_url = f"https://earthengine.googleapis.com/map/{mapid['mapid']}/{{z}}/{{x}}/{{y}}?token={mapid['token']}"

    payload = {
        "metric": metric,
        "date_bucket": date_bucket,
        "granularity": granularity,
        "tile_url": tile_url,
        "min": vmin,
        "max": vmax,
        "palette": [f"#{c}" for c in metric_def.palette],
        "opacity": opacity,
        "attribution": "Earth Engine / source datasets",
    }

    _tile_template_cache[cache_key] = (now, payload)
    return payload
