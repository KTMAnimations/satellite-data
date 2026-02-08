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

PALETTE_VEG = ["f7fcf5", "e5f5e0", "c7e9c0", "a1d99b", "74c476", "41ab5d", "238b45", "006d2c", "00441b", "00290f"]
PALETTE_WATER = ["ffffe5", "edf8fb", "ccece6", "99d8c9", "66c2a4", "41ae76", "238b45", "006d2c", "00441b", "002d1a"]
PALETTE_COOL_WARM = ["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "fee090", "fdae61", "f46d43", "d73027", "a50026"]
PALETTE_EARTH = ["fff7ec", "fee8c8", "fdd49e", "fdbb84", "fc8d59", "ef6548", "d7301f", "b30000", "7f0000", "4a0000"]
PALETTE_GREY = ["ffffff", "f0f0f0", "d9d9d9", "bdbdbd", "969696", "737373", "525252", "363636", "1f1f1f", "000000"]
PALETTE_SNOW = ["0b1f3a", "174a7e", "2b8cbe", "41b6c4", "7fcdbb", "c7e9b4", "edf8b1", "ffffd9", "ffffff", "f7f7f7"]

METRICS.update(
    {
        "evi": MetricDefinition(
            id="evi",
            label="EVI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_VEG,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "ndre": MetricDefinition(
            id="ndre",
            label="NDRE",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_VEG,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "ndmi": MetricDefinition(
            id="ndmi",
            label="NDMI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_WATER,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "ndwi": MetricDefinition(
            id="ndwi",
            label="NDWI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_WATER,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "mndwi": MetricDefinition(
            id="mndwi",
            label="MNDWI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_WATER,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "savi": MetricDefinition(
            id="savi",
            label="SAVI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_VEG,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "bsi": MetricDefinition(
            id="bsi",
            label="Bare Soil Index",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_EARTH,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "nbr": MetricDefinition(
            id="nbr",
            label="NBR",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "dnbr": MetricDefinition(
            id="dnbr",
            label="dNBR",
            unit="index change",
            value_range=(-2.0, 2.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "gci": MetricDefinition(
            id="gci",
            label="GCI",
            unit="index",
            value_range=(-1.0, 10.0),
            palette=PALETTE_VEG,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "ndsi": MetricDefinition(
            id="ndsi",
            label="NDSI",
            unit="index (-1 to 1)",
            value_range=(-1.0, 1.0),
            palette=PALETTE_SNOW,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "s1_vv": MetricDefinition(
            id="s1_vv",
            label="Sentinel-1 VV Backscatter",
            unit="dB",
            value_range=(-25.0, 5.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "s1_vh": MetricDefinition(
            id="s1_vh",
            label="Sentinel-1 VH Backscatter",
            unit="dB",
            value_range=(-35.0, 0.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "s1_vh_vv_ratio": MetricDefinition(
            id="s1_vh_vv_ratio",
            label="Sentinel-1 VH/VV Ratio",
            unit="dB difference",
            value_range=(-20.0, 5.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "s1_rvi": MetricDefinition(
            id="s1_rvi",
            label="Sentinel-1 RVI",
            unit="index",
            value_range=(0.0, 4.0),
            palette=PALETTE_VEG,
            default_granularity="weekly",
            supported_granularities={"weekly", "monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "lst_day": MetricDefinition(
            id="lst_day",
            label="Land Surface Temperature (Day)",
            unit="°C",
            value_range=(-30.0, 60.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "lst_night": MetricDefinition(
            id="lst_night",
            label="Land Surface Temperature (Night)",
            unit="°C",
            value_range=(-40.0, 40.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "lst_diurnal_range": MetricDefinition(
            id="lst_diurnal_range",
            label="LST Diurnal Range",
            unit="°C",
            value_range=(0.0, 30.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "albedo_black_sky": MetricDefinition(
            id="albedo_black_sky",
            label="Black-sky Albedo",
            unit="reflectance",
            value_range=(0.0, 1.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "albedo_white_sky": MetricDefinition(
            id="albedo_white_sky",
            label="White-sky Albedo",
            unit="reflectance",
            value_range=(0.0, 1.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "par": MetricDefinition(
            id="par",
            label="Photosynthetically Active Radiation",
            unit="MJ/m²/day (proxy)",
            value_range=(0.0, 25.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"daily", "monthly"},
            scale_m=11000,
            transparent_below_normalized=0.0,
        ),
        "lai": MetricDefinition(
            id="lai",
            label="Leaf Area Index",
            unit="m²/m²",
            value_range=(0.0, 10.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "fpar": MetricDefinition(
            id="fpar",
            label="FPAR",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "gpp": MetricDefinition(
            id="gpp",
            label="Gross Primary Productivity",
            unit="kg C/m²",
            value_range=(0.0, 10.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "npp": MetricDefinition(
            id="npp",
            label="Net Primary Productivity",
            unit="kg C/m²",
            value_range=(0.0, 10.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "biomass_agb_carbon": MetricDefinition(
            id="biomass_agb_carbon",
            label="Aboveground Biomass Carbon",
            unit="Mg C/ha",
            value_range=(0.0, 400.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.001,
        ),
        "biomass_bgb_carbon": MetricDefinition(
            id="biomass_bgb_carbon",
            label="Belowground Biomass Carbon",
            unit="Mg C/ha",
            value_range=(0.0, 200.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.001,
        ),
        "gedi_agbd": MetricDefinition(
            id="gedi_agbd",
            label="GEDI Aboveground Biomass Density",
            unit="Mg/ha",
            value_range=(0.0, 500.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.001,
        ),
        "active_fire_temp": MetricDefinition(
            id="active_fire_temp",
            label="Active Fire Brightness Temperature",
            unit="K",
            value_range=(250.0, 500.0),
            palette=PALETTE_EARTH,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "active_fire_confidence": MetricDefinition(
            id="active_fire_confidence",
            label="Active Fire Confidence",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_EARTH,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "burned_area_date": MetricDefinition(
            id="burned_area_date",
            label="Burn Date",
            unit="day of year",
            value_range=(1.0, 366.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "burned_area_fraction": MetricDefinition(
            id="burned_area_fraction",
            label="Burned Area Fraction",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.001,
        ),
        "treecover_2000": MetricDefinition(
            id="treecover_2000",
            label="Tree Cover 2000",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "forest_loss_year": MetricDefinition(
            id="forest_loss_year",
            label="Forest Loss Year",
            unit="year",
            value_range=(2001.0, 2025.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "forest_gain": MetricDefinition(
            id="forest_gain",
            label="Forest Gain",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_VEG,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "forest_loss_fraction": MetricDefinition(
            id="forest_loss_fraction",
            label="Forest Loss Fraction",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "snow_cover": MetricDefinition(
            id="snow_cover",
            label="Snow Cover",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_SNOW,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "fractional_snow_cover": MetricDefinition(
            id="fractional_snow_cover",
            label="Fractional Snow Cover",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_SNOW,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "snow_albedo": MetricDefinition(
            id="snow_albedo",
            label="Snow Albedo",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_SNOW,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "snow_cover_8day": MetricDefinition(
            id="snow_cover_8day",
            label="8-day Snow Cover",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_SNOW,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=500,
            transparent_below_normalized=0.0,
        ),
        "tws_anomaly": MetricDefinition(
            id="tws_anomaly",
            label="Terrestrial Water Storage Anomaly",
            unit="cm",
            value_range=(-50.0, 50.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=50000,
            transparent_below_normalized=0.0,
        ),
        "flood_max_extent": MetricDefinition(
            id="flood_max_extent",
            label="Flood Max Extent",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.001,
        ),
        "flood_duration_days": MetricDefinition(
            id="flood_duration_days",
            label="Flood Duration",
            unit="days",
            value_range=(0.0, 365.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "flood_observation_quality": MetricDefinition(
            id="flood_observation_quality",
            label="Flood Observation Quality",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "drought_pdsi": MetricDefinition(
            id="drought_pdsi",
            label="PDSI",
            unit="index",
            value_range=(-10.0, 10.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "vpd": MetricDefinition(
            id="vpd",
            label="Vapor Pressure Deficit",
            unit="kPa",
            value_range=(0.0, 5.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "runoff": MetricDefinition(
            id="runoff",
            label="Runoff",
            unit="mm",
            value_range=(0.0, 500.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "clim_water_deficit": MetricDefinition(
            id="clim_water_deficit",
            label="Climatic Water Deficit",
            unit="mm",
            value_range=(0.0, 500.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "elevation": MetricDefinition(
            id="elevation",
            label="Elevation",
            unit="m",
            value_range=(-500.0, 9000.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "slope": MetricDefinition(
            id="slope",
            label="Slope",
            unit="degrees",
            value_range=(0.0, 90.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "aspect": MetricDefinition(
            id="aspect",
            label="Aspect",
            unit="degrees",
            value_range=(0.0, 360.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "terrain_ruggedness": MetricDefinition(
            id="terrain_ruggedness",
            label="Terrain Ruggedness",
            unit="stddev(m)",
            value_range=(0.0, 1000.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.0,
        ),
        "soil_organic_carbon": MetricDefinition(
            id="soil_organic_carbon",
            label="Soil Organic Carbon",
            unit="g/kg (proxy)",
            value_range=(0.0, 200.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "soil_ph": MetricDefinition(
            id="soil_ph",
            label="Soil pH",
            unit="pH",
            value_range=(3.0, 10.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "soil_sand_fraction": MetricDefinition(
            id="soil_sand_fraction",
            label="Soil Sand Fraction",
            unit="%",
            value_range=(0.0, 100.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "soil_field_capacity": MetricDefinition(
            id="soil_field_capacity",
            label="Soil Field Capacity",
            unit="volumetric %",
            value_range=(0.0, 100.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=250,
            transparent_below_normalized=0.0,
        ),
        "population_count": MetricDefinition(
            id="population_count",
            label="Population Count",
            unit="people per cell",
            value_range=(0.0, 1000.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "population_density": MetricDefinition(
            id="population_density",
            label="Population Density",
            unit="people/km²",
            value_range=(0.0, 30000.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=100,
            transparent_below_normalized=0.0,
        ),
        "building_presence": MetricDefinition(
            id="building_presence",
            label="Building Presence",
            unit="confidence (0-1)",
            value_range=(0.0, 1.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=10,
            transparent_below_normalized=0.001,
        ),
        "building_height": MetricDefinition(
            id="building_height",
            label="Building Height",
            unit="m",
            value_range=(0.0, 100.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=10,
            transparent_below_normalized=0.0,
        ),
        "building_count_proxy": MetricDefinition(
            id="building_count_proxy",
            label="Building Count Proxy",
            unit="fractional count",
            value_range=(0.0, 100.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=10,
            transparent_below_normalized=0.0,
        ),
        "building_footprints_density": MetricDefinition(
            id="building_footprints_density",
            label="Building Footprint Density",
            unit="fraction",
            value_range=(0.0, 1.0),
            palette=PALETTE_GREY,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=30,
            transparent_below_normalized=0.001,
        ),
        "travel_time_to_cities": MetricDefinition(
            id="travel_time_to_cities",
            label="Travel Time to Cities",
            unit="minutes",
            value_range=(0.0, 720.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.0,
        ),
        "human_modification": MetricDefinition(
            id="human_modification",
            label="Human Modification Index",
            unit="index (0-1)",
            value_range=(0.0, 1.0),
            palette=PALETTE_EARTH,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
            transparent_below_normalized=0.001,
        ),
        "co": MetricDefinition(
            id="co",
            label="Carbon Monoxide",
            unit="mol/m²",
            value_range=(0.0, 0.1),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "so2": MetricDefinition(
            id="so2",
            label="Sulfur Dioxide",
            unit="mol/m²",
            value_range=(0.0, 0.001),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "o3": MetricDefinition(
            id="o3",
            label="Ozone",
            unit="mol/m²",
            value_range=(0.0, 0.2),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "hcho": MetricDefinition(
            id="hcho",
            label="Formaldehyde",
            unit="mol/m²",
            value_range=(0.0, 0.001),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "ch4": MetricDefinition(
            id="ch4",
            label="Methane",
            unit="ppb",
            value_range=(1600.0, 2000.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=10000,
            transparent_below_normalized=0.0,
        ),
        "pm25": MetricDefinition(
            id="pm25",
            label="PM2.5",
            unit="µg/m³",
            value_range=(0.0, 200.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=25000,
            transparent_below_normalized=0.0,
        ),
        "sst": MetricDefinition(
            id="sst",
            label="Sea Surface Temperature",
            unit="°C",
            value_range=(-2.0, 35.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="daily",
            supported_granularities={"daily", "monthly"},
            scale_m=25000,
            transparent_below_normalized=0.0,
        ),
        "ocean_chlorophyll": MetricDefinition(
            id="ocean_chlorophyll",
            label="Ocean Chlorophyll-a",
            unit="mg/m³",
            value_range=(0.0, 50.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "ocean_poc": MetricDefinition(
            id="ocean_poc",
            label="Ocean Particulate Organic Carbon",
            unit="mg/m³",
            value_range=(0.0, 2000.0),
            palette=PALETTE_WATER,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=5000,
            transparent_below_normalized=0.0,
        ),
        "bathymetry": MetricDefinition(
            id="bathymetry",
            label="Bathymetry / Relief",
            unit="m",
            value_range=(-11000.0, 9000.0),
            palette=PALETTE_COOL_WARM,
            default_granularity="monthly",
            supported_granularities={"monthly"},
            scale_m=1000,
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


def _mask_s2_sr_clouds(image):
    """Mask cloud/shadow classes from Sentinel-2 SR harmonized scenes."""
    scl = image.select("SCL")
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return image.updateMask(mask)


def _s2_sr_collection(start, end, geom):
    import ee

    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
    )


def _s1_grd_collection(start, end, geom, *, require_vh: bool):
    import ee

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    )
    if require_vh:
        collection = collection.filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    return collection


def _to_linear_backscatter(db_image):
    import ee

    return ee.Image.constant(10).pow(db_image.divide(10))


def _hansen_forest_change_image():
    import ee

    return ee.Image("UMD/hansen/global_forest_change_2024_v1_12")


def build_metric_image(metric: MetricId, start, end, geom):
    """
    Build an ee.Image with a single band named after the metric.

    `start` and `end` are ee.Date. `geom` is ee.Geometry.
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

    if metric in {"evi", "ndre", "ndmi", "ndwi", "mndwi", "savi", "bsi", "nbr", "gci", "ndsi"}:
        s2 = _s2_sr_collection(start, end, geom)
        has_images = s2.size().gt(0)
        composite = s2.map(_mask_s2_sr_clouds).median()

        if metric == "evi":
            image = (
                composite.expression(
                    "2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))",
                    {"nir": composite.select("B8"), "red": composite.select("B4"), "blue": composite.select("B2")},
                )
                .clamp(-1, 1)
                .rename([band])
            )
        elif metric == "ndre":
            image = composite.normalizedDifference(["B8A", "B5"]).rename([band])
        elif metric == "ndmi":
            image = composite.normalizedDifference(["B8", "B11"]).rename([band])
        elif metric == "ndwi":
            image = composite.normalizedDifference(["B3", "B8"]).rename([band])
        elif metric == "mndwi":
            image = composite.normalizedDifference(["B3", "B11"]).rename([band])
        elif metric == "savi":
            l = 0.5
            image = (
                composite.expression(
                    "((1 + l) * (nir - red)) / (nir + red + l)",
                    {"nir": composite.select("B8"), "red": composite.select("B4"), "l": l},
                )
                .clamp(-1, 1)
                .rename([band])
            )
        elif metric == "bsi":
            image = (
                composite.expression(
                    "((swir + red) - (nir + blue)) / ((swir + red) + (nir + blue))",
                    {
                        "swir": composite.select("B11"),
                        "red": composite.select("B4"),
                        "nir": composite.select("B8"),
                        "blue": composite.select("B2"),
                    },
                )
                .clamp(-1, 1)
                .rename([band])
            )
        elif metric == "nbr":
            image = composite.normalizedDifference(["B8", "B12"]).rename([band])
        elif metric == "gci":
            image = composite.select("B8").divide(composite.select("B3")).subtract(1).rename([band])
        else:
            image = composite.normalizedDifference(["B3", "B11"]).rename([band])

        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "dnbr":
        pre_start = start.advance(-30, "day")
        pre_end = start
        post_start = end.advance(-30, "day")
        post_end = end

        pre = _s2_sr_collection(pre_start, pre_end, geom)
        post = _s2_sr_collection(post_start, post_end, geom)
        has_images = pre.size().gt(0).And(post.size().gt(0))

        pre_nbr = pre.map(_mask_s2_sr_clouds).median().normalizedDifference(["B8", "B12"])
        post_nbr = post.map(_mask_s2_sr_clouds).median().normalizedDifference(["B8", "B12"])
        image = pre_nbr.subtract(post_nbr).rename([band])

        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"s1_vv", "s1_vh", "s1_vh_vv_ratio", "s1_rvi"}:
        require_vh = metric != "s1_vv"
        s1 = _s1_grd_collection(start, end, geom, require_vh=require_vh)
        has_images = s1.size().gt(0)
        s1 = s1.map(lambda img: img.focal_median(radius=30, units="meters"))

        vv_db = s1.select(["VV"]).median()
        if metric == "s1_vv":
            image = vv_db.rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        vh_db = s1.select(["VH"]).median()
        if metric == "s1_vh":
            image = vh_db.rename([band])
        elif metric == "s1_vh_vv_ratio":
            image = vh_db.subtract(vv_db).rename([band])
        else:
            vv_lin = _to_linear_backscatter(vv_db)
            vh_lin = _to_linear_backscatter(vh_db)
            image = vh_lin.multiply(4).divide(vv_lin.add(vh_lin)).rename([band])

        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"lst_day", "lst_night", "lst_diurnal_range"}:
        collection = ee.ImageCollection("MODIS/061/MOD11A2").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)

        def prep_day(image):
            mask = image.select("QC_Day").bitwiseAnd(3).lte(1)
            return image.select(["LST_Day_1km"]).multiply(0.02).subtract(273.15).updateMask(mask).rename(["day"])

        def prep_night(image):
            mask = image.select("QC_Night").bitwiseAnd(3).lte(1)
            return image.select(["LST_Night_1km"]).multiply(0.02).subtract(273.15).updateMask(mask).rename(["night"])

        day = collection.map(prep_day).mean()
        night = collection.map(prep_night).mean()

        if metric == "lst_day":
            image = day.rename([band])
        elif metric == "lst_night":
            image = night.rename([band])
        else:
            image = day.subtract(night).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"albedo_black_sky", "albedo_white_sky"}:
        collection = ee.ImageCollection("MODIS/061/MCD43A3").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        band_name = "Albedo_BSA_shortwave" if metric == "albedo_black_sky" else "Albedo_WSA_shortwave"
        image = collection.select([band_name]).mean().multiply(0.001).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "par":
        # ERA5-Land downward shortwave radiation proxy -> PAR-equivalent energy.
        collection = (
            ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["surface_solar_radiation_downwards_sum"])
        )
        has_images = collection.size().gt(0)
        image = collection.mean().multiply(0.45).divide(1e6).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"lai", "fpar"}:
        collection = ee.ImageCollection("MODIS/061/MCD15A3H").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)

        def with_qa(image):
            qc = image.select("FparLai_QC")
            return image.updateMask(qc.bitwiseAnd(3).lte(1))

        qa_collection = collection.map(with_qa)
        if metric == "lai":
            image = qa_collection.select(["Lai"]).mean().multiply(0.1).rename([band])
        else:
            image = qa_collection.select(["Fpar"]).mean().multiply(0.01).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "gpp":
        collection = ee.ImageCollection("MODIS/061/MOD17A2HGF").filterBounds(geom).filterDate(start, end).select(["Gpp"])
        has_images = collection.size().gt(0)
        image = collection.sum().multiply(0.0001).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "npp":
        collection = ee.ImageCollection("MODIS/061/MOD17A3HGF").filterBounds(geom).filterDate(start, end).select(["Npp"])
        has_images = collection.size().gt(0)
        image = collection.mean().multiply(0.0001).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"biomass_agb_carbon", "biomass_bgb_carbon"}:
        biomass = ee.ImageCollection("NASA/ORNL/biomass_carbon_density/v1").mosaic()
        band_name = "agb" if metric == "biomass_agb_carbon" else "bgb"
        image = biomass.select([band_name]).rename([band])
        return image.clip(geom)

    if metric == "gedi_agbd":
        # GEDI L4B in EE is exposed as a single gridded image asset.
        image = ee.Image("LARSE/GEDI/GEDI04_B_002").select(["MU"]).rename([band])
        return image.clip(geom)

    if metric in {"active_fire_temp", "active_fire_confidence"}:
        collection = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        if metric == "active_fire_temp":
            image = collection.select(["T21"]).max().rename([band])
        else:
            image = collection.select(["confidence"]).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"burned_area_date", "burned_area_fraction"}:
        collection = ee.ImageCollection("MODIS/061/MCD64A1").filterBounds(geom).filterDate(start, end).select(["BurnDate"])
        has_images = collection.size().gt(0)
        if metric == "burned_area_date":
            image = collection.map(lambda img: img.updateMask(img.gt(0))).mean().rename([band])
        else:
            image = collection.map(lambda img: img.gt(0).toFloat()).max().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"treecover_2000", "forest_loss_year", "forest_gain", "forest_loss_fraction"}:
        hansen = _hansen_forest_change_image()
        if metric == "treecover_2000":
            image = hansen.select(["treecover2000"]).rename([band])
        elif metric == "forest_loss_year":
            lossyear = hansen.select(["lossyear"])
            image = lossyear.updateMask(lossyear.gt(0)).add(2000).rename([band])
        elif metric == "forest_gain":
            image = hansen.select(["gain"]).toFloat().rename([band])
        else:
            image = hansen.select(["loss"]).toFloat().rename([band])
        return image.clip(geom)

    if metric in {"snow_cover", "fractional_snow_cover", "snow_albedo"}:
        collection = ee.ImageCollection("MODIS/061/MOD10A1").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        if metric == "snow_cover":
            image = collection.select(["NDSI_Snow_Cover"]).mean().rename([band])
        elif metric == "fractional_snow_cover":
            def pick_fractional(img):
                return ee.Image(
                    ee.Algorithms.If(
                        img.bandNames().contains("Fractional_Snow_Cover"),
                        img.select(["Fractional_Snow_Cover"]),
                        img.select(["NDSI_Snow_Cover"]),
                    )
                )

            image = collection.map(pick_fractional).mean().rename([band])
        else:
            def pick_albedo(img):
                return ee.Image(
                    ee.Algorithms.If(
                        img.bandNames().contains("Snow_Albedo_Daily_Tile"),
                        img.select(["Snow_Albedo_Daily_Tile"]),
                        img.select(["NDSI_Snow_Cover"]),
                    )
                )

            image = collection.map(pick_albedo).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "snow_cover_8day":
        collection = ee.ImageCollection("MODIS/061/MOD10A2").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)

        def pick_extent(img):
            return ee.Image(
                ee.Algorithms.If(
                    img.bandNames().contains("Maximum_Snow_Extent"),
                    img.select(["Maximum_Snow_Extent"]),
                    img.select([0]),
                )
            )

        image = collection.map(pick_extent).max().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "tws_anomaly":
        collection = ee.ImageCollection("NASA/GRACE/MASS_GRIDS_V04/LAND").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        mean_sources = collection.select(["lwe_thickness_csr", "lwe_thickness_gfz", "lwe_thickness_jpl"]).mean()
        image = mean_sources.reduce(ee.Reducer.mean()).rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"flood_max_extent", "flood_duration_days", "flood_observation_quality"}:
        collection = ee.ImageCollection("GLOBAL_FLOOD_DB/MODIS_EVENTS/V1").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        if metric == "flood_max_extent":
            image = collection.select(["flooded"]).max().rename([band])
        elif metric == "flood_duration_days":
            image = collection.select(["duration"]).mean().rename([band])
        else:
            image = collection.select(["clear_perc"]).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"drought_pdsi", "vpd", "runoff", "clim_water_deficit"}:
        collection = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)
        source_band = {
            "drought_pdsi": "pdsi",
            "vpd": "vpd",
            "runoff": "ro",
            "clim_water_deficit": "def",
        }[metric]
        image = collection.select([source_band]).mean().rename([band])
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"elevation", "slope", "aspect", "terrain_ruggedness"}:
        dem = ee.Image("USGS/SRTMGL1_003").select(["elevation"])
        if metric == "elevation":
            image = dem.rename([band])
        elif metric == "slope":
            image = ee.Terrain.slope(dem).rename([band])
        elif metric == "aspect":
            image = ee.Terrain.aspect(dem).rename([band])
        else:
            image = dem.reduceNeighborhood(
                reducer=ee.Reducer.stdDev(),
                kernel=ee.Kernel.square(radius=3, units="pixels"),
            ).rename([band])
        return image.clip(geom)

    if metric in {"soil_organic_carbon", "soil_ph", "soil_sand_fraction", "soil_field_capacity"}:
        source = {
            "soil_organic_carbon": "OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02",
            "soil_ph": "OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02",
            "soil_sand_fraction": "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02",
            "soil_field_capacity": "OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01",
        }[metric]
        topsoil = ee.Image(source).select(["b0", "b10", "b30"]).reduce(ee.Reducer.mean())
        if metric == "soil_ph":
            topsoil = topsoil.divide(10)
        image = topsoil.rename([band])
        return image.clip(geom)

    if metric in {
        "population_count",
        "population_density",
        "building_presence",
        "building_height",
        "building_count_proxy",
        "building_footprints_density",
        "travel_time_to_cities",
        "human_modification",
    }:
        if metric in {"population_count", "population_density"}:
            all_pop = ee.ImageCollection("WorldPop/GP/100m/pop").filterBounds(geom)
            has_any = all_pop.size().gt(0)
            year = ee.Number.parse(start.format("YYYY"))
            y0 = ee.Date.fromYMD(year, 1, 1)
            y1 = y0.advance(1, "year")
            by_year = all_pop.filterDate(y0, y1)
            latest = all_pop.sort("system:time_start", False).first()
            pop = ee.Image(
                ee.Algorithms.If(
                    has_any,
                    ee.Algorithms.If(by_year.size().gt(0), by_year.mean(), latest),
                    _empty_masked_image("population"),
                )
            ).select([0], ["population"])
            if metric == "population_count":
                image = pop.rename([band])
            else:
                image = pop.divide(ee.Image.pixelArea().divide(1e6)).rename([band])
            return image.clip(geom)

        if metric in {"building_presence", "building_height", "building_count_proxy"}:
            collection = (
                ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
                .filterBounds(geom)
                .filterDate(start, end)
            )
            has_images = collection.size().gt(0)
            source_band = {
                "building_presence": "building_presence",
                "building_height": "building_height",
                "building_count_proxy": "building_fractional_count",
            }[metric]
            image = collection.select([source_band]).mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "building_footprints_density":
            # Vector polygon reduction is very expensive at global tile scale.
            # Use temporal raster building-presence as a footprint-density proxy.
            collection = (
                ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
                .filterBounds(geom)
                .filterDate(start, end)
                .select(["building_presence"])
            )
            has_images = collection.size().gt(0)
            image = collection.mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        if metric == "travel_time_to_cities":
            image = ee.Image(
                "projects/malariaatlasproject/assets/accessibility/accessibility_to_cities/2015_v1_0"
            ).select([0]).rename([band])
            return image.clip(geom)

        hm = ee.ImageCollection("CSP/HM/GlobalHumanModification")
        has_images = hm.size().gt(0)
        image = ee.Image(
            ee.Algorithms.If(
                has_images,
                hm.sort("system:time_start", False).first(),
                _empty_masked_image("gHM"),
            )
        ).select(["gHM"]).rename([band])
        return image.clip(geom)

    if metric in {"co", "so2", "o3", "hcho", "ch4"}:
        source = {
            "co": ("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density"),
            "so2": ("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density"),
            "o3": ("COPERNICUS/S5P/OFFL/L3_O3", "O3_column_number_density"),
            "hcho": ("COPERNICUS/S5P/OFFL/L3_HCHO", "tropospheric_HCHO_column_number_density"),
            "ch4": ("COPERNICUS/S5P/OFFL/L3_CH4", "CH4_column_volume_mixing_ratio_dry_air"),
        }[metric]
        collection = ee.ImageCollection(source[0]).filterBounds(geom).filterDate(start, end)
        has_images = collection.size().gt(0)

        def with_qa(image):
            selected = image.select([source[1]], [band])

            # These OFFL/L3 collections in EE do not consistently expose
            # `qa_value`. For products with `cloud_fraction`, use a simple cloud
            # screen; otherwise keep all pixels to avoid hard failures.
            if metric in {"so2", "o3", "hcho"}:
                cloud_mask = ee.Image(
                    ee.Algorithms.If(
                        image.bandNames().contains("cloud_fraction"),
                        image.select(["cloud_fraction"]).lte(0.3),
                        ee.Image(1),
                    )
                )
                selected = selected.updateMask(cloud_mask)

            return selected

        prepared = collection.map(with_qa)
        image = _mean_of_daily_means(prepared, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric == "pm25":
        collection = (
            ee.ImageCollection("NASA/GEOS-CF/v1/rpl/htf")
            .filterBounds(geom)
            .filterDate(start, end)
            .select(["PM25_RH35_GCC"], [band])
        )
        has_images = collection.size().gt(0)
        image = _mean_of_daily_means(collection, start, end, band)
        return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

    if metric in {"sst", "ocean_chlorophyll", "ocean_poc", "bathymetry"}:
        if metric == "sst":
            collection = ee.ImageCollection("NOAA/CDR/OISST/V2_1").filterBounds(geom).filterDate(start, end).select(["sst"])
            has_images = collection.size().gt(0)
            image = collection.mean().multiply(0.01).rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)
        if metric == "ocean_chlorophyll":
            collection = (
                ee.ImageCollection("NASA/OCEANDATA/MODIS-Aqua/L3SMI")
                .filterBounds(geom)
                .filterDate(start, end)
                .select(["chlor_a"])
            )
            has_images = collection.size().gt(0)
            image = collection.mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)
        if metric == "ocean_poc":
            collection = (
                ee.ImageCollection("NASA/OCEANDATA/MODIS-Aqua/L3SMI")
                .filterBounds(geom)
                .filterDate(start, end)
                .select(["poc"])
            )
            has_images = collection.size().gt(0)
            image = collection.mean().rename([band])
            return ee.Image(ee.Algorithms.If(has_images, image, _empty_masked_image(band))).clip(geom)

        image = ee.Image("NOAA/NGDC/ETOPO1").select(["bedrock"]).rename([band])
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

        # Low-zoom dNBR: use burned-area fraction proxy to avoid expensive global
        # dual-window Sentinel-2 composites while preserving higher=more impact.
        if metric == "dnbr":
            burned = (
                ee.ImageCollection("MODIS/061/MCD64A1")
                .filterBounds(geom)
                .filterDate(start, end)
                .select(["BurnDate"])
            )
            has_images = burned.size().gt(0)
            frac = burned.map(lambda img: img.gt(0).toFloat()).max().multiply(2).rename([metric])
            return ee.Image(ee.Algorithms.If(has_images, frac, _empty_masked_image(metric))).clip(geom)

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
_tile_cache_version = 27


def _tile_visualization_range(metric_def: MetricDefinition) -> tuple[float, float]:
    return metric_def.tile_viz_range or metric_def.value_range


def _tile_render_variant(metric: MetricId, *, z: int | None) -> str:
    if z is not None and z <= 6 and metric in {"ndvi", "parking", "land_cover", "cropland", "surface_water", "dnbr"}:
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
