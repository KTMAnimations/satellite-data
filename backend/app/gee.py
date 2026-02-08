from __future__ import annotations

import concurrent.futures
import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

# Timeout (seconds) for individual Earth Engine getInfo() calls.
_GEE_GETINFO_TIMEOUT = 120

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
        # NDBI-derived values typically cluster in a narrow mid-band; use a
        # tighter render range so block-level differences are visible.
        tile_viz_range=(0.2, 0.6),
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
        # Keep common near-surface aerosol variation from collapsing to a flat tint.
        tile_viz_range=(-0.5, 1.5),
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
}

# Extended global metrics (must stay in sync with frontend/src/config/*).
METRICS.update(
    {
        "co_column_density": MetricDefinition(
            id="co_column_density",
            label="CO Column Density",
            unit="mol/m²",
            value_range=(0.0, 0.06),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "so2_column_density": MetricDefinition(
            id="so2_column_density",
            label="SO2 Column Density",
            unit="mol/m²",
            value_range=(0.0, 0.0005),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "o3_total_column": MetricDefinition(
            id="o3_total_column",
            label="O3 Total Column",
            unit="mol/m²",
            value_range=(0.1, 0.2),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "tropospheric_ozone_column": MetricDefinition(
            id="tropospheric_ozone_column",
            label="Tropospheric Ozone",
            unit="mol/m²",
            value_range=(0.0, 0.06),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=55000,
            transparent_below_normalized=0.0,
        ),
        "methane_mixing_ratio": MetricDefinition(
            id="methane_mixing_ratio",
            label="Methane Mixing Ratio",
            unit="mol fraction",
            value_range=(1500.0, 2200.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "formaldehyde_column": MetricDefinition(
            id="formaldehyde_column",
            label="Formaldehyde Column",
            unit="mol/m²",
            value_range=(0.0, 0.001),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "aerosol_layer_height": MetricDefinition(
            id="aerosol_layer_height",
            label="Aerosol Layer Height",
            unit="m",
            value_range=(0.0, 10000.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "cloud_fraction": MetricDefinition(
            id="cloud_fraction",
            label="Cloud Fraction",
            unit="fraction (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.001,
        ),
        "cloud_top_height": MetricDefinition(
            id="cloud_top_height",
            label="Cloud Top Height",
            unit="m",
            value_range=(0.0, 20000.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "aod_550": MetricDefinition(
            id="aod_550",
            label="AOD 550nm",
            unit="aod",
            value_range=(0.0, 2.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "active_fire_hotspots": MetricDefinition(
            id="active_fire_hotspots",
            label="Active Fire Hotspots",
            unit="hotspots per pixel",
            value_range=(0.0, 1.0),
            palette=["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "fc4e2a", "e31a1c", "bd0026", "800026", "4d0018"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "burned_area_fraction": MetricDefinition(
            id="burned_area_fraction",
            label="Burned Area Fraction",
            unit="ratio (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "fc4e2a", "e31a1c", "bd0026", "800026", "4d0018"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "burn_day_of_year": MetricDefinition(
            id="burn_day_of_year",
            label="Burn Day Of Year",
            unit="day of year",
            value_range=(1.0, 366.0),
            palette=["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "fc4e2a", "e31a1c", "bd0026", "800026", "4d0018"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "river_flood_depth_rp100": MetricDefinition(
            id="river_flood_depth_rp100",
            label="Flood Depth RP100",
            unit="m",
            value_range=(0.0, 15.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=90,
            transparent_below_normalized=0.0,
        ),
        "water_recurrence": MetricDefinition(
            id="water_recurrence",
            label="Water Recurrence",
            unit="percent",
            value_range=(0.0, 100.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "snow_cover": MetricDefinition(
            id="snow_cover",
            label="Snow Cover",
            unit="percent",
            value_range=(0.0, 100.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "6a51a3", "54278f", "3f007d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "snow_albedo": MetricDefinition(
            id="snow_albedo",
            label="Snow Albedo",
            unit="percent",
            value_range=(0.0, 100.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "6a51a3", "54278f", "3f007d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "terrestrial_water_storage": MetricDefinition(
            id="terrestrial_water_storage",
            label="Terrestrial Water Storage",
            unit="cm",
            value_range=(-50.0, 50.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "ffffbf", "fee090", "fdae61", "f46d43", "a50026"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=55660,
            transparent_below_normalized=0.0,
        ),
        "drought_pdsi": MetricDefinition(
            id="drought_pdsi",
            label="Drought PDSI",
            unit="pdsi",
            value_range=(-10.0, 10.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "ffffbf", "fee090", "fdae61", "f46d43", "a50026"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "climatic_water_deficit": MetricDefinition(
            id="climatic_water_deficit",
            label="Climatic Water Deficit",
            unit="mm",
            value_range=(0.0, 500.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "ffffbf", "fee090", "fdae61", "f46d43", "a50026"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "runoff": MetricDefinition(
            id="runoff",
            label="Runoff",
            unit="mm",
            value_range=(0.0, 1000.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "snow_water_equivalent": MetricDefinition(
            id="snow_water_equivalent",
            label="Snow Water Equivalent",
            unit="mm",
            value_range=(0.0, 2000.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "6a51a3", "54278f", "3f007d"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "vegetation_water_deficit": MetricDefinition(
            id="vegetation_water_deficit",
            label="Vegetation Water Deficit",
            unit="kPa",
            value_range=(0.0, 6.0),
            palette=["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "ffffbf", "fee090", "fdae61", "f46d43", "a50026"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "wind_speed_climate": MetricDefinition(
            id="wind_speed_climate",
            label="Wind Speed Climate",
            unit="m/s",
            value_range=(0.0, 30.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "041a3d"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "evi_modis": MetricDefinition(
            id="evi_modis",
            label="EVI MODIS",
            unit="index",
            value_range=(-0.2, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=250,
            transparent_below_normalized=0.001,
        ),
        "lai": MetricDefinition(
            id="lai",
            label="Leaf Area Index",
            unit="m²/m²",
            value_range=(0.0, 10.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "fpar": MetricDefinition(
            id="fpar",
            label="FPAR",
            unit="fraction (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "gpp_8day": MetricDefinition(
            id="gpp_8day",
            label="GPP 8-Day",
            unit="kg*C/m²",
            value_range=(0.0, 0.004),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "npp_annual": MetricDefinition(
            id="npp_annual",
            label="NPP Annual",
            unit="kg*C/m²",
            value_range=(0.0, 0.02),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "phenology_greenup": MetricDefinition(
            id="phenology_greenup",
            label="Phenology Greenup",
            unit="day of year",
            value_range=(1.0, 366.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "phenology_senescence": MetricDefinition(
            id="phenology_senescence",
            label="Phenology Senescence",
            unit="day of year",
            value_range=(1.0, 366.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "landsat_ndwi_8day": MetricDefinition(
            id="landsat_ndwi_8day",
            label="Landsat NDWI 8-Day",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "landsat_evi_8day": MetricDefinition(
            id="landsat_evi_8day",
            label="Landsat EVI 8-Day",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "forest_loss_year": MetricDefinition(
            id="forest_loss_year",
            label="Forest Loss Year",
            unit="year",
            value_range=(2001.0, 2024.0),
            palette=["ffffe5", "f7fcb9", "d9f0a3", "addd8e", "78c679", "41ab5d", "238443", "006837", "004529", "002a1f"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "forest_loss_fraction": MetricDefinition(
            id="forest_loss_fraction",
            label="Forest Loss Fraction",
            unit="ratio (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["ffffe5", "f7fcb9", "d9f0a3", "addd8e", "78c679", "41ab5d", "238443", "006837", "004529", "002a1f"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "tree_cover_2000": MetricDefinition(
            id="tree_cover_2000",
            label="Tree Cover 2000",
            unit="percent",
            value_range=(0.0, 100.0),
            palette=["ffffe5", "f7fcb9", "d9f0a3", "addd8e", "78c679", "41ab5d", "238443", "006837", "004529", "002a1f"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "forest_gain": MetricDefinition(
            id="forest_gain",
            label="Forest Gain",
            unit="ratio (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["ffffe5", "f7fcb9", "d9f0a3", "addd8e", "78c679", "41ab5d", "238443", "006837", "004529", "002a1f"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "population_count_ghsl": MetricDefinition(
            id="population_count_ghsl",
            label="Population Count GHSL",
            unit="people per cell",
            value_range=(0.0, 10000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "population_count_worldpop": MetricDefinition(
            id="population_count_worldpop",
            label="Population Count WorldPop",
            unit="people per cell",
            value_range=(0.0, 1000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "population_density_gpw": MetricDefinition(
            id="population_density_gpw",
            label="Population Density GPW",
            unit="people/km²",
            value_range=(0.0, 50000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "built_height": MetricDefinition(
            id="built_height",
            label="Built Height",
            unit="m",
            value_range=(0.0, 100.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "built_volume_total": MetricDefinition(
            id="built_volume_total",
            label="Built Volume Total",
            unit="m³",
            value_range=(0.0, 10000000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "built_volume_nonres": MetricDefinition(
            id="built_volume_nonres",
            label="Built Volume Non-Residential",
            unit="m³",
            value_range=(0.0, 10000000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "degree_of_urbanization": MetricDefinition(
            id="degree_of_urbanization",
            label="Degree Of Urbanization",
            unit="class code",
            value_range=(0.0, 30.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "radar_backscatter_vv": MetricDefinition(
            id="radar_backscatter_vv",
            label="Radar Backscatter VV",
            unit="dB",
            value_range=(-25.0, 5.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "radar_backscatter_vh": MetricDefinition(
            id="radar_backscatter_vh",
            label="Radar Backscatter VH",
            unit="dB",
            value_range=(-30.0, 0.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "elevation_dem30": MetricDefinition(
            id="elevation_dem30",
            label="Elevation DEM30",
            unit="m",
            value_range=(-500.0, 9000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "elevation_srtm": MetricDefinition(
            id="elevation_srtm",
            label="Elevation SRTM",
            unit="m",
            value_range=(-500.0, 9000.0),
            palette=["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"],
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "dw_trees": MetricDefinition(
            id="dw_trees",
            label="Dynamic World Trees",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dw_grass": MetricDefinition(
            id="dw_grass",
            label="Dynamic World Grass",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dw_flooded_vegetation": MetricDefinition(
            id="dw_flooded_vegetation",
            label="Dynamic World Flooded Vegetation",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dw_shrub_scrub": MetricDefinition(
            id="dw_shrub_scrub",
            label="Dynamic World Shrub Scrub",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dw_bare": MetricDefinition(
            id="dw_bare",
            label="Dynamic World Bare",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["8c510a", "bf812d", "dfc27d", "f6e8c3", "c7eae5", "80cdc1", "35978f", "1f6d6f", "01665e", "003c30"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dw_snow_ice": MetricDefinition(
            id="dw_snow_ice",
            label="Dynamic World Snow Ice",
            unit="probability (0 to 1)",
            value_range=(0.0, 1.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "6a51a3", "54278f", "3f007d"],
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "wind_speed_10m": MetricDefinition(
            id="wind_speed_10m",
            label="Wind Speed 10m",
            unit="m/s",
            value_range=(0.0, 40.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "041a3d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "relative_humidity_2m": MetricDefinition(
            id="relative_humidity_2m",
            label="Relative Humidity 2m",
            unit="percent",
            value_range=(0.0, 100.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "041a3d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "surface_pressure": MetricDefinition(
            id="surface_pressure",
            label="Surface Pressure",
            unit="hPa",
            value_range=(800.0, 1100.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "041a3d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "solar_radiation_down": MetricDefinition(
            id="solar_radiation_down",
            label="Solar Radiation Down",
            unit="MJ/m²",
            value_range=(0.0, 40.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "08519c", "08306b", "041a3d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "snow_depth_era5": MetricDefinition(
            id="snow_depth_era5",
            label="Snow Depth ERA5",
            unit="m",
            value_range=(0.0, 5.0),
            palette=["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6", "4292c6", "2171b5", "6a51a3", "54278f", "3f007d"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "runoff_era5": MetricDefinition(
            id="runoff_era5",
            label="Runoff ERA5",
            unit="mm",
            value_range=(0.0, 500.0),
            palette=["ffffff", "f0f9ff", "d6eaf8", "aed6f1", "85c1e9", "5dade2", "3498db", "2980b9", "1f618d", "154360"],
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
    }
)


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


def _select_year_image_or_latest(collection, target_year):
    """
    Select an annual image for `target_year`, with fallback to latest available.
    """
    import ee

    by_year = collection.filter(ee.Filter.calendarRange(target_year, target_year, "year"))
    latest = ee.Image(collection.sort("system:time_start", False).first())
    return ee.Image(ee.Algorithms.If(by_year.size().gt(0), by_year.first(), latest))


def _select_epoch_image_by_index(collection, target_year, epochs: list[int]):
    """
    Pick the latest epoch <= target_year from a collection indexed by `system:index` year strings.
    """
    import ee

    epoch_list = ee.List(epochs)
    first_epoch = ee.Number(epoch_list.get(0))

    def pick_epoch(e, acc):
        e_num = ee.Number(e)
        acc_num = ee.Number(acc)
        return ee.Number(ee.Algorithms.If(e_num.lte(target_year), e_num, acc_num))

    epoch = ee.Number(epoch_list.iterate(pick_epoch, first_epoch))
    idx = epoch.format()
    filtered = collection.filter(ee.Filter.eq("system:index", idx))
    latest = ee.Image(collection.sort("system:time_start", False).first())
    return ee.Image(ee.Algorithms.If(filtered.size().gt(0), filtered.first(), latest))


def build_metric_image(metric: MetricId, start, end, geom):
    """
    Build an ee.Image with a single band named after the metric.

    `start` and `end` are ee.Date. `geom` is ee.Geometry.
    """
    import ee

    band = metric

    def _s5p_daily_metric(
        collection_id: str,
        source_band: str,
        *,
        qa_band: str | None = None,
        qa_min: float | None = None,
        qa_max: float | None = None,
    ):
        col = ee.ImageCollection(collection_id).filterBounds(geom)
        if qa_band is not None:
            def apply_qa(img):
                qa = img.select([qa_band])
                mask = ee.Image(1)
                if qa_min is not None:
                    mask = mask.And(qa.gte(qa_min))
                if qa_max is not None:
                    mask = mask.And(qa.lte(qa_max))
                return img.updateMask(mask)

            col = col.map(apply_qa)
        col = col.select([source_band], [band])
        has_images = col.filterDate(start, end).size().gt(0)
        image = _mean_of_daily_means(col, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    def _dynamic_world_probability(dw_band: str):
        dw = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select([dw_band], [band])
        )
        has_images = dw.size().gt(0)
        image = dw.median().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

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

    if metric == "urban_density":
        # Built surface fraction from GHSL, provided as ~5-year epoch snapshots.
        # `system:index` for this collection is the epoch year (e.g. "2020").
        # Pick the latest available epoch <= the requested year so time series
        # don't "peek" into future projections.
        year = ee.Number.parse(start.format("YYYY"))
        epochs = ee.List([1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030])

        def pick_epoch(e, acc):
            e_num = ee.Number(e)
            acc_num = ee.Number(acc)
            return ee.Number(ee.Algorithms.If(e_num.lte(year), e_num, acc_num))

        epoch = ee.Number(epochs.iterate(pick_epoch, ee.Number(epochs.get(0))))
        idx = epoch.format()

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
        # Blend in ERA5-Land precipitation to avoid a hard latitude cutoff.
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
        return chirps_img.unmask(era5_img).clip(geom)

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

        # S5P daily coverage can have masked gaps (orbit seams / QA), which show
        # up as streaks at tile-scale. Fill masked pixels with a short rolling
        # composite to keep the overlay visually continuous.
        fill_days = 7
        fill_start = start.advance(-fill_days, "day")
        fill_end = end.advance(fill_days, "day")
        has_fill = s5p.filterDate(fill_start, fill_end).size().gt(0)
        fill = _mean_of_daily_means(s5p, fill_start, fill_end, band)

        base = ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band)))
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

    if metric == "co_column_density":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density")

    if metric == "so2_column_density":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density")

    if metric == "o3_total_column":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_O3", "O3_column_number_density")

    if metric == "tropospheric_ozone_column":
        return _s5p_daily_metric(
            "COPERNICUS/S5P/OFFL/L3_O3_TCL",
            "ozone_tropospheric_vertical_column",
            qa_band="qa_value",
            qa_min=70,
        )

    if metric == "methane_mixing_ratio":
        return _s5p_daily_metric(
            "COPERNICUS/S5P/OFFL/L3_CH4",
            "CH4_column_volume_mixing_ratio_dry_air_bias_corrected",
        )

    if metric == "formaldehyde_column":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_HCHO", "tropospheric_HCHO_column_number_density")

    if metric == "aerosol_layer_height":
        return _s5p_daily_metric(
            "COPERNICUS/S5P/OFFL/L3_AER_LH",
            "aerosol_height",
            qa_band="aerosol_optical_depth",
            qa_min=0.0,
        )

    if metric == "cloud_fraction":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_fraction")

    if metric == "cloud_top_height":
        return _s5p_daily_metric("COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_top_height")

    if metric == "aod_550":
        collection = (
            ee.ImageCollection("MODIS/061/MCD19A2_GRANULES")
            .filterBounds(geom)
            .filterDate(start, end)
        )
        has_images = collection.size().gt(0)

        def prep_aod(img):
            aod = img.select(["Optical_Depth_055"]).multiply(0.001).rename([band])
            qa = img.select(["AOD_QA"])
            qa_mask = qa.bitwiseAnd(3).lte(1)
            return aod.updateMask(qa_mask)

        prepared = collection.map(prep_aod)
        image = _mean_of_daily_means(prepared, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "active_fire_hotspots":
        collection = (
            ee.ImageCollection("FIRMS")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["confidence"])
        )
        has_images = collection.size().gt(0)

        def hotspot_mask(img):
            return img.select(["confidence"]).gte(50).toFloat().rename([band])

        hotspots = collection.map(hotspot_mask)
        image = _mean_of_daily_means(hotspots, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "burned_area_fraction":
        collection = (
            ee.ImageCollection("MODIS/061/MCD64A1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["BurnDate"])
        )
        has_images = collection.size().gt(0)

        def burned_mask(img):
            burn = img.select(["BurnDate"])
            return burn.gt(0).toFloat().rename([band])

        image = collection.map(burned_mask).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "burn_day_of_year":
        collection = (
            ee.ImageCollection("MODIS/061/MCD64A1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["BurnDate"])
        )
        has_images = collection.size().gt(0)

        def burn_day(img):
            burn = img.select(["BurnDate"])
            return burn.updateMask(burn.gt(0)).rename([band])

        image = collection.map(burn_day).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "river_flood_depth_rp100":
        collection = ee.ImageCollection("JRC/CEMS_GLOFAS/FloodHazard/v2_1").filterBounds(geom)
        has_images = collection.size().gt(0)
        image = ee.Image(
            ee.Algorithms.If(
                has_images,
                ee.Image(collection.first()).select(["RP100_depth"]).rename([band]),
                _empty_masked_image(band),
            )
        )
        return image.clip(geom)

    if metric == "water_recurrence":
        month = ee.Number.parse(start.format("M"))
        collection = ee.ImageCollection("JRC/GSW1_4/MonthlyRecurrence").filterBounds(geom)
        monthly = collection.filter(ee.Filter.eq("month", month))
        has_images = monthly.size().gt(0)

        empty_monthly = _empty_masked_image("monthly_recurrence").addBands(_empty_masked_image("has_observations"))
        month_img = ee.Image(ee.Algorithms.If(has_images, monthly.first(), empty_monthly))
        recurrence = month_img.select(["monthly_recurrence"]).rename([band])
        has_obs = month_img.select(["has_observations"]).gt(0)
        image = recurrence.updateMask(has_obs)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "snow_cover":
        collection = (
            ee.ImageCollection("MODIS/061/MOD10A1")
            .filterBounds(geom)
            .filterDate(start, end)
        )
        has_images = collection.size().gt(0)

        def snow_cover_img(img):
            snow = img.select(["NDSI_Snow_Cover"])
            qa = img.select(["NDSI_Snow_Cover_Basic_QA"])
            return snow.updateMask(qa.lte(2)).rename([band])

        prepared = collection.map(snow_cover_img)
        image = _mean_of_daily_means(prepared, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "snow_albedo":
        collection = (
            ee.ImageCollection("MODIS/061/MOD10A1")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["Snow_Albedo_Daily_Tile"])
        )
        has_images = collection.size().gt(0)

        def snow_albedo_img(img):
            albedo = img.select(["Snow_Albedo_Daily_Tile"]).clamp(0, 100)
            return albedo.rename([band])

        prepared = collection.map(snow_albedo_img)
        image = _mean_of_daily_means(prepared, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "terrestrial_water_storage":
        collection = (
            ee.ImageCollection("NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["lwe_thickness"], [band])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {
        "drought_pdsi",
        "climatic_water_deficit",
        "runoff",
        "snow_water_equivalent",
        "vegetation_water_deficit",
        "wind_speed_climate",
    }:
        terra_specs: dict[str, tuple[str, float]] = {
            "drought_pdsi": ("pdsi", 0.01),
            "climatic_water_deficit": ("def", 0.1),
            "runoff": ("ro", 1.0),
            "snow_water_equivalent": ("swe", 1.0),
            "vegetation_water_deficit": ("vpd", 0.01),
            "wind_speed_climate": ("vs", 0.01),
        }
        source_band, scale = terra_specs[metric]
        collection = (
            ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE")
            .filterBounds(geom)
            .filterDate(start, end)
            .select([source_band])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().multiply(scale).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "evi_modis":
        buffer_days = 16
        collection = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(geom)
            .filterDate(start.advance(-buffer_days, "day"), end.advance(buffer_days, "day"))
        )
        has_images = collection.size().gt(0)

        def evi_img(img):
            evi = img.select(["EVI"]).multiply(0.0001).rename([band])
            qa = img.select(["SummaryQA"])
            return evi.updateMask(qa.lt(3))

        image = collection.map(evi_img).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"lai", "fpar"}:
        modis_specs: dict[str, tuple[str, float]] = {
            "lai": ("Lai", 0.1),
            "fpar": ("Fpar", 0.01),
        }
        source_band, scale = modis_specs[metric]
        collection = (
            ee.ImageCollection("MODIS/061/MCD15A3H")
            .filterBounds(geom)
            .filterDate(start, end)
        )
        has_images = collection.size().gt(0)

        def lai_fpar_img(img):
            value = img.select([source_band]).multiply(scale).rename([band])
            qc = img.select(["FparLai_QC"])
            qc_mask = qc.bitwiseAnd(3).lte(1)
            return value.updateMask(qc_mask)

        image = collection.map(lai_fpar_img).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "gpp_8day":
        collection = (
            ee.ImageCollection("MODIS/061/MOD17A2HGF")
            .filterBounds(geom)
            .filterDate(start, end)
        )
        has_images = collection.size().gt(0)

        def gpp_img(img):
            gpp = img.select(["Gpp"]).multiply(0.0001).rename([band])
            qc = img.select(["Psn_QC"])
            qc_mask = qc.bitwiseAnd(3).lte(1)
            return gpp.updateMask(qc_mask)

        image = collection.map(gpp_img).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "npp_annual":
        collection = ee.ImageCollection("MODIS/061/MOD17A3HGF").filterBounds(geom)
        has_images = collection.size().gt(0)
        latest = ee.Image(collection.sort("system:time_start", False).first())
        latest_year = ee.Number.parse(latest.date().format("YYYY"))
        year = ee.Number.parse(start.format("YYYY")).min(latest_year).max(2001)
        image_for_year = _select_year_image_or_latest(collection, year)
        npp = image_for_year.select(["Npp"]).multiply(0.0001).rename([band])
        # Keep native projection to avoid SR-ORG:6974 -> EPSG:4326 edge transform
        # failures in world tiles; reduceRegion callers already supply geometry.
        return ee.Image(ee.Algorithms.If(has_images, npp, _empty_masked_image(band)))

    if metric in {"phenology_greenup", "phenology_senescence"}:
        phase_band = "Greenup_1" if metric == "phenology_greenup" else "Senescence_1"
        collection = ee.ImageCollection("MODIS/061/MCD12Q2").filterBounds(geom)
        has_images = collection.size().gt(0)

        latest = ee.Image(collection.sort("system:time_start", False).first())
        latest_year = ee.Number.parse(latest.date().format("YYYY"))
        year = ee.Number.parse(start.format("YYYY")).min(latest_year).max(2001)
        phase = _select_year_image_or_latest(collection, year)

        qa = phase.select(["QA_Overall_1"])
        phase_days_since_epoch = phase.select([phase_band])
        year_start_days = ee.Date.fromYMD(year, 1, 1).difference(ee.Date("1970-01-01"), "day")
        doy = phase_days_since_epoch.subtract(year_start_days).add(1).rename([band])
        image = doy.updateMask(qa.lte(2)).updateMask(doy.gte(1).And(doy.lte(366)))
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"landsat_ndwi_8day", "landsat_evi_8day"}:
        collection_id = (
            "LANDSAT/COMPOSITES/C02/T1_L2_8DAY_NDWI"
            if metric == "landsat_ndwi_8day"
            else "LANDSAT/COMPOSITES/C02/T1_L2_8DAY_EVI"
        )
        source_band = "NDWI" if metric == "landsat_ndwi_8day" else "EVI"

        primary = (
            ee.ImageCollection(collection_id)
            .filterBounds(geom)
            .filterDate(start, end)
            .select([source_band], [band])
        )
        has_primary = primary.size().gt(0)
        primary_img = primary.mean().rename([band])

        fallback = (
            ee.ImageCollection(collection_id)
            .filterBounds(geom)
            .filterDate(start.advance(-8, "day"), end.advance(8, "day"))
            .select([source_band], [band])
        )
        has_fallback = fallback.size().gt(0)
        fallback_img = fallback.mean().rename([band])

        image = ee.Image(
            ee.Algorithms.If(
                has_primary,
                primary_img,
                ee.Image(ee.Algorithms.If(has_fallback, fallback_img, _empty_masked_image(band))),
            )
        )
        return image.clip(geom)

    if metric in {"forest_loss_year", "forest_loss_fraction", "tree_cover_2000", "forest_gain"}:
        hansen = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")

        if metric == "forest_loss_year":
            lossyear = hansen.select(["lossyear"])
            image = lossyear.add(2000).updateMask(lossyear.gt(0)).rename([band])
            return image.clip(geom)

        if metric == "forest_loss_fraction":
            year = ee.Number.parse(start.format("YYYY")).min(2024).max(2001)
            max_idx = year.subtract(2000)
            lossyear = hansen.select(["lossyear"])
            image = lossyear.gt(0).And(lossyear.lte(max_idx)).toFloat().rename([band])
            return image.clip(geom)

        if metric == "tree_cover_2000":
            return hansen.select(["treecover2000"]).rename([band]).clip(geom)

        if metric == "forest_gain":
            return hansen.select(["gain"]).toFloat().rename([band]).clip(geom)

    if metric == "population_count_ghsl":
        year = ee.Number.parse(start.format("YYYY"))
        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_POP").filterBounds(geom)
        has_images = collection.size().gt(0)
        image = _select_epoch_image_by_index(collection, year, [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030])
        pop = image.select(["population_count"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, pop, _empty_masked_image(band))).clip(geom)

    if metric == "population_count_worldpop":
        collection = ee.ImageCollection("WorldPop/GP/100m/pop").filterBounds(geom)
        has_images = collection.size().gt(0)
        year = ee.Number.parse(start.format("YYYY")).min(2021).max(2000)
        image_for_year = _select_year_image_or_latest(collection, year)
        pop = image_for_year.select(["population"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, pop, _empty_masked_image(band))).clip(geom)

    if metric == "population_density_gpw":
        year = ee.Number.parse(start.format("YYYY"))
        collection = ee.ImageCollection("CIESIN/GPWv411/GPW_Population_Density").filterBounds(geom)
        has_images = collection.size().gt(0)
        epoch_list = ee.List([2000, 2005, 2010, 2015, 2020])
        first_epoch = ee.Number(epoch_list.get(0))

        def pick_epoch(e, acc):
            e_num = ee.Number(e)
            acc_num = ee.Number(acc)
            return ee.Number(ee.Algorithms.If(e_num.lte(year), e_num, acc_num))

        epoch = ee.Number(epoch_list.iterate(pick_epoch, first_epoch))
        by_year = collection.filter(ee.Filter.calendarRange(epoch, epoch, "year"))
        latest = ee.Image(collection.sort("system:time_start", False).first())
        image = ee.Image(ee.Algorithms.If(by_year.size().gt(0), by_year.first(), latest))
        density = image.select(["population_density"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, density, _empty_masked_image(band))).clip(geom)

    if metric == "built_height":
        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_H").filterBounds(geom)
        has_images = collection.size().gt(0)
        image = ee.Image(ee.Algorithms.If(has_images, collection.first(), _empty_masked_image("built_height")))
        out = image.select(["built_height"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, out, _empty_masked_image(band))).clip(geom)

    if metric in {"built_volume_total", "built_volume_nonres"}:
        year = ee.Number.parse(start.format("YYYY"))
        source_band = "built_volume_total" if metric == "built_volume_total" else "built_volume_nres"
        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_V").filterBounds(geom)
        has_images = collection.size().gt(0)
        image = _select_epoch_image_by_index(collection, year, [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030])
        out = image.select([source_band]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, out, _empty_masked_image(band))).clip(geom)

    if metric == "degree_of_urbanization":
        year = ee.Number.parse(start.format("YYYY"))
        collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_SMOD_V2-0").filterBounds(geom)
        has_images = collection.size().gt(0)
        image = _select_epoch_image_by_index(collection, year, [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030])
        smod = image.select(["smod_code"]).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, smod, _empty_masked_image(band))).clip(geom)

    if metric in {"radar_backscatter_vv", "radar_backscatter_vh"}:
        pol = "VV" if metric == "radar_backscatter_vv" else "VH"
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", pol))
            .select([pol], [band])
        )
        has_images = collection.size().gt(0)
        image = collection.median().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "elevation_dem30":
        dem_collection = ee.ImageCollection("COPERNICUS/DEM/GLO30").select(["DEM"])
        has_dem = dem_collection.size().gt(0)
        dem = dem_collection.mosaic().rename([band])
        srtm = ee.Image("USGS/SRTMGL1_003").select(["elevation"]).rename([band])
        image = dem.unmask(srtm)
        return ee.Image(ee.Algorithms.If(has_dem, image, srtm)).clip(geom)

    if metric == "elevation_srtm":
        return ee.Image("USGS/SRTMGL1_003").select(["elevation"]).rename([band]).clip(geom)

    if metric in {"dw_trees", "dw_grass", "dw_flooded_vegetation", "dw_shrub_scrub", "dw_bare", "dw_snow_ice"}:
        dw_band_map: dict[str, str] = {
            "dw_trees": "trees",
            "dw_grass": "grass",
            "dw_flooded_vegetation": "flooded_vegetation",
            "dw_shrub_scrub": "shrub_and_scrub",
            "dw_bare": "bare",
            "dw_snow_ice": "snow_and_ice",
        }
        return _dynamic_world_probability(dw_band_map[metric])

    if metric in {"wind_speed_10m", "relative_humidity_2m", "surface_pressure", "solar_radiation_down", "snow_depth_era5", "runoff_era5"}:
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(geom)
            .filterDate(start, end)
        )
        has_images = collection.size().gt(0)

        if metric == "wind_speed_10m":
            def wind_speed_img(img):
                u = img.select(["u_component_of_wind_10m"])
                v = img.select(["v_component_of_wind_10m"])
                return u.pow(2).add(v.pow(2)).sqrt().rename([band])

            image = collection.map(wind_speed_img).mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "relative_humidity_2m":
            def relative_humidity_img(img):
                t_c = img.select(["temperature_2m"]).subtract(273.15)
                td_c = img.select(["dewpoint_temperature_2m"]).subtract(273.15)
                sat = t_c.multiply(17.625).divide(t_c.add(243.04)).exp()
                vap = td_c.multiply(17.625).divide(td_c.add(243.04)).exp()
                rh = vap.divide(sat).multiply(100).clamp(0, 100)
                return rh.rename([band])

            image = collection.map(relative_humidity_img).mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "surface_pressure":
            image = collection.select(["surface_pressure"]).mean().divide(100).rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "solar_radiation_down":
            image = collection.select(["surface_solar_radiation_downwards_sum"]).mean().divide(1e6).rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "snow_depth_era5":
            image = collection.select(["snow_depth"]).mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "runoff_era5":
            image = collection.select(["runoff_sum"]).sum().multiply(1000).rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

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

        # Low-zoom parking: reuse coarse built-surface fraction proxy.
        if metric == "parking":
            # GHSL built-surface fractions are often very small outside dense
            # cores, which can render as effectively invisible at global zooms.
            # Apply a gentle sqrt contrast boost so sparse urbanized areas stay
            # visible while preserving the 0..1 range and ordering.
            urban = build_metric_image("urban_density", start, end, geom)
            return urban.sqrt().clamp(0, 1).rename([metric])

        # Low-zoom built-up layer: use annual MODIS land-cover built-up class.
        if metric == "land_cover":
            lc_type1 = _modis_land_cover_for_year().select(["LC_Type1"])
            built_up = lc_type1.eq(13).toFloat().rename([metric])
            return built_up.clip(geom)

        # Low-zoom cropland: MODIS cropland classes (12=croplands, 14=mosaic).
        if metric == "cropland":
            lc_type1 = _modis_land_cover_for_year().select(["LC_Type1"])
            croplands = lc_type1.eq(12).toFloat()
            mosaic = lc_type1.eq(14).toFloat().multiply(0.5)
            cropland = croplands.add(mosaic).clamp(0, 1).rename([metric])
            return cropland.clip(geom)

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
        ee_dates = ee.List(dates)
        fc = ee.FeatureCollection(ee_dates.map(per_bucket))
        try:
            # Use a thread-pool future so we can enforce a timeout on getInfo().
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(fc.getInfo)
                info = future.result(timeout=_GEE_GETINFO_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Earth Engine getInfo() timed out after {_GEE_GETINFO_TIMEOUT}s "
                f"for {len(dates)} date buckets. Try a smaller date range or coarser granularity."
            )
        except Exception as e:
            # Common when mapping reduceRegion over many dates.
            if "Too many concurrent aggregations" in str(e) and len(dates) > 1:
                mid = len(dates) // 2
                return fetch_dates(dates[:mid]) + fetch_dates(dates[mid:])
            raise
        return _parse_features(info)

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
_tile_cache_version = 28


def _tile_visualization_range(metric_def: MetricDefinition) -> tuple[float, float]:
    return metric_def.tile_viz_range or metric_def.value_range


def _tile_render_variant(metric: MetricId, *, z: int | None) -> str:
    if z is not None and z <= 6 and metric in {"ndvi", "parking", "land_cover", "cropland", "surface_water"}:
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
        "attribution": "Earth Engine / source datasets",
    }

    _tile_template_cache[cache_key] = (now, payload)
    return payload
