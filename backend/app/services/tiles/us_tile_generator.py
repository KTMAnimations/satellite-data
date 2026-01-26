"""
US-Wide Tile Generator

Pre-generates map tiles for the entire continental US at zoom levels 8-10.
Tiles are stored in standard XYZ format: /{metric}/{YYYY-MM}/{z}/{x}/{y}.png
Uses Web Mercator (EPSG:3857) projection to match XYZ tile coordinates.
"""

import asyncio
import math
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Tile size in pixels
TILE_SIZE = 256

# Earth circumference at equator in meters (Web Mercator)
EARTH_CIRCUMFERENCE = 40075016.686

# Continental US bounding box (EPSG:4326 - lat/lon)
US_BOUNDS = {
    "west": -125.0,
    "east": -66.0,
    "south": 24.0,
    "north": 50.0,
}


def lon_to_mercator_x(lon: float) -> float:
    """Convert longitude to Web Mercator X (meters)."""
    return lon * 20037508.34 / 180.0


def lat_to_mercator_y(lat: float) -> float:
    """Convert latitude to Web Mercator Y (meters)."""
    lat_rad = math.radians(lat)
    y = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    return y * 20037508.34 / math.pi


# US bounds in Web Mercator (EPSG:3857)
US_BOUNDS_MERCATOR = {
    "west": lon_to_mercator_x(US_BOUNDS["west"]),
    "east": lon_to_mercator_x(US_BOUNDS["east"]),
    "south": lat_to_mercator_y(US_BOUNDS["south"]),
    "north": lat_to_mercator_y(US_BOUNDS["north"]),
}

# Metrics to generate
METRICS = [
    "ndvi", "nightlights", "urban_density", "parking",
    # Phase 1: Core datasets
    "land_cover", "surface_water", "active_fire",
    # Phase 2: Air quality & weather
    "no2", "temperature", "precipitation", "aerosol",
    # Phase 3: Agriculture
    "cropland", "evapotranspiration", "soil_moisture",
    # Phase 4: Historical & specialized
    "impervious", "fire_historical", "canopy_height",
]

# Zoom levels to generate (11 provides good detail for city-level views)
ZOOM_LEVELS = [11]


def lon_to_tile_x(lon: float, zoom: int) -> int:
    """Convert longitude to tile X coordinate."""
    return int((lon + 180) / 360 * (2 ** zoom))


def lat_to_tile_y(lat: float, zoom: int) -> int:
    """Convert latitude to tile Y coordinate."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    return int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Get geographic bounds for a tile in lat/lon (west, south, east, north)."""
    n = 2 ** z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180

    north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))

    south = math.degrees(south_rad)
    north = math.degrees(north_rad)

    return (west, south, east, north)


def tile_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Get tile bounds in Web Mercator meters (west, south, east, north)."""
    n = 2 ** z
    tile_size_meters = EARTH_CIRCUMFERENCE / n

    # Web Mercator origin is at center of map
    origin = EARTH_CIRCUMFERENCE / 2

    west = x * tile_size_meters - origin
    east = (x + 1) * tile_size_meters - origin
    # Y increases downward in tile coordinates, but upward in Mercator
    north = origin - y * tile_size_meters
    south = origin - (y + 1) * tile_size_meters

    return (west, south, east, north)


def get_us_tiles(zoom: int) -> list[tuple[int, int]]:
    """Get all tile coordinates covering the US at a given zoom level."""
    x_min = lon_to_tile_x(US_BOUNDS["west"], zoom)
    x_max = lon_to_tile_x(US_BOUNDS["east"], zoom)
    y_min = lat_to_tile_y(US_BOUNDS["north"], zoom)  # Note: y increases southward
    y_max = lat_to_tile_y(US_BOUNDS["south"], zoom)

    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y))

    return tiles


class USTileGenerator:
    """Generate pre-computed tiles for the entire US."""

    # Color maps for metrics (same as original)
    COLORMAPS = {
        "ndvi": [
            (165, 0, 38), (215, 48, 39), (244, 109, 67), (253, 174, 97),
            (254, 224, 139), (217, 239, 139), (166, 217, 106), (102, 189, 99),
            (26, 152, 80), (0, 104, 55),
        ],
        "nightlights": [
            (0, 0, 0), (30, 0, 50), (60, 0, 100), (100, 0, 150),
            (150, 50, 150), (200, 100, 100), (255, 150, 50), (255, 200, 100),
            (255, 255, 150), (255, 255, 255),
        ],
        "urban_density": [
            (255, 255, 229), (255, 247, 188), (254, 227, 145), (254, 196, 79),
            (254, 153, 41), (236, 112, 20), (204, 76, 2), (153, 52, 4),
            (102, 37, 6), (51, 18, 3),
        ],
        "parking": [
            (247, 251, 255), (222, 235, 247), (198, 219, 239), (158, 202, 225),
            (107, 174, 214), (66, 146, 198), (33, 113, 181), (8, 81, 156),
            (8, 48, 107), (3, 19, 43),
        ],
        # Phase 1: Core datasets
        "land_cover": [  # Built-up probability (purple gradient)
            (247, 244, 249), (231, 225, 239), (212, 185, 218), (201, 148, 199),
            (186, 111, 178), (170, 79, 160), (152, 49, 142), (122, 1, 119),
            (92, 0, 89), (63, 0, 60),
        ],
        "surface_water": [  # Blue water gradient
            (255, 255, 255), (240, 249, 255), (214, 234, 248), (174, 214, 241),
            (133, 193, 233), (93, 173, 226), (52, 152, 219), (41, 128, 185),
            (31, 97, 141), (21, 67, 96),
        ],
        "active_fire": [  # Fire radiative power (orange-red)
            (255, 255, 204), (255, 237, 160), (254, 217, 118), (254, 178, 76),
            (253, 141, 60), (252, 78, 42), (227, 26, 28), (189, 0, 38),
            (128, 0, 38), (80, 0, 0),
        ],
        # Phase 2: Air quality & weather
        "no2": [  # NO2 concentration (blue-yellow-red)
            (49, 54, 149), (69, 117, 180), (116, 173, 209), (171, 217, 233),
            (224, 243, 248), (254, 224, 144), (253, 174, 97), (244, 109, 67),
            (215, 48, 39), (165, 0, 38),
        ],
        "temperature": [  # Temperature (blue-white-red)
            (5, 48, 97), (33, 102, 172), (67, 147, 195), (146, 197, 222),
            (209, 229, 240), (253, 219, 199), (244, 165, 130), (214, 96, 77),
            (178, 24, 43), (103, 0, 31),
        ],
        "precipitation": [  # Precipitation (white-blue-purple)
            (255, 255, 255), (240, 249, 232), (204, 235, 197), (168, 221, 181),
            (123, 204, 196), (78, 179, 211), (43, 140, 190), (8, 104, 172),
            (8, 64, 129), (37, 37, 86),
        ],
        "aerosol": [  # Aerosol index (white-brown-black for smoke)
            (255, 255, 255), (253, 245, 230), (252, 226, 196), (250, 197, 152),
            (242, 165, 117), (221, 132, 82), (186, 101, 56), (145, 72, 36),
            (100, 45, 20), (50, 20, 5),
        ],
        # Phase 3: Agriculture
        "cropland": [  # Categorical crop colors (simplified gradient)
            (255, 255, 178), (254, 217, 118), (254, 178, 76), (253, 141, 60),
            (240, 59, 32), (189, 0, 38), (0, 128, 0), (34, 139, 34),
            (144, 238, 144), (255, 255, 0),
        ],
        "evapotranspiration": [  # ET (brown-green gradient)
            (166, 97, 26), (191, 129, 45), (216, 179, 101), (229, 218, 169),
            (245, 245, 220), (199, 234, 229), (128, 205, 193), (53, 151, 143),
            (1, 102, 94), (0, 60, 48),
        ],
        "soil_moisture": [  # Soil moisture (brown-blue)
            (139, 69, 19), (160, 82, 45), (188, 143, 90), (210, 180, 140),
            (245, 222, 179), (173, 216, 230), (135, 206, 235), (70, 130, 180),
            (65, 105, 225), (0, 0, 139),
        ],
        # Phase 4: Historical & specialized
        "impervious": [  # Urban impervious (gray gradient)
            (255, 255, 255), (240, 240, 240), (217, 217, 217), (189, 189, 189),
            (150, 150, 150), (115, 115, 115), (82, 82, 82), (54, 54, 54),
            (26, 26, 26), (0, 0, 0),
        ],
        "fire_historical": [  # Same as active_fire
            (255, 255, 204), (255, 237, 160), (254, 217, 118), (254, 178, 76),
            (253, 141, 60), (252, 78, 42), (227, 26, 28), (189, 0, 38),
            (128, 0, 38), (80, 0, 0),
        ],
        "canopy_height": [  # Forest height (green gradient)
            (247, 252, 245), (229, 245, 224), (199, 233, 192), (161, 217, 155),
            (116, 196, 118), (65, 171, 93), (35, 139, 69), (0, 109, 44),
            (0, 68, 27), (0, 40, 16),
        ],
    }

    # Value ranges for normalization
    VALUE_RANGES = {
        "ndvi": (-1.0, 1.0),
        "nightlights": (0.0, 100.0),
        "urban_density": (0.0, 1.0),
        "parking": (0.0, 1.0),
        # Phase 1: Core datasets
        "land_cover": (0.0, 1.0),  # Probability 0-1
        "surface_water": (0.0, 1.0),  # Binary mask
        "active_fire": (0.0, 500.0),  # FRP in MW
        # Phase 2: Air quality & weather
        "no2": (0.0, 0.0002),  # mol/m²
        "temperature": (-30.0, 45.0),  # Celsius
        "precipitation": (0.0, 500.0),  # mm/month
        "aerosol": (-2.0, 5.0),  # Aerosol index
        # Phase 3: Agriculture
        "cropland": (0.0, 255.0),  # Crop type codes
        "evapotranspiration": (0.0, 300.0),  # mm/month
        "soil_moisture": (0.0, 0.5),  # m³/m³ volumetric water content
        # Phase 4: Historical & specialized
        "impervious": (0.0, 1.0),  # Binary mask
        "fire_historical": (0.0, 500.0),  # FRP in MW
        "canopy_height": (0.0, 60.0),  # meters
    }

    def __init__(self, tiles_dir: str | Path | None = None):
        self.settings = get_settings()
        if tiles_dir:
            self.tiles_dir = Path(tiles_dir)
        else:
            self.tiles_dir = Path(self.settings.cache_dir) / "us_tiles"

    def get_tile_path(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
    ) -> Path:
        """
        Get the file path for a pre-generated tile.

        Args:
            metric: The metric type (nightlights, ndvi, etc.)
            date_str: Date string in YYYY-MM or YYYY-MM-DD format
            z, x, y: Tile coordinates
        """
        return self.tiles_dir / metric / date_str / str(z) / str(x) / f"{y}.png"

    def tile_exists(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
    ) -> bool:
        """Check if a tile has already been generated."""
        return self.get_tile_path(metric, date_str, z, x, y).exists()

    async def generate_month(
        self,
        year: int,
        month: int,
        metrics: list[str] | None = None,
        zoom_levels: list[int] | None = None,
        force: bool = False,
    ) -> dict:
        """
        Generate all tiles for a specific month.

        Args:
            year: Year (e.g., 2023)
            month: Month (1-12)
            metrics: List of metrics to generate (default: all)
            zoom_levels: Zoom levels to generate (default: 8-10)
            force: Regenerate even if tiles exist

        Returns:
            Statistics about generated tiles
        """
        from app.services.satellite.us_data_service import USDataService

        metrics = metrics or METRICS
        zoom_levels = zoom_levels or ZOOM_LEVELS
        year_month = f"{year}-{month:02d}"

        logger.info(f"Generating US tiles for {year_month}", metrics=metrics, zooms=zoom_levels)

        data_service = USDataService()
        await data_service.initialize()
        stats = {"generated": 0, "skipped": 0, "failed": 0}

        for metric in metrics:
            logger.info(f"Fetching {metric} data for US...")

            # Fetch data for entire US
            try:
                raster_data = await self._fetch_us_data(
                    data_service, metric, year, month
                )

                if raster_data is None:
                    logger.warning(f"No data available for {metric} {year_month}")
                    continue

            except Exception as e:
                logger.error(f"Failed to fetch {metric} data", error=str(e))
                continue

            # Generate tiles at each zoom level
            for zoom in zoom_levels:
                tiles = get_us_tiles(zoom)
                logger.info(f"Generating {len(tiles)} tiles for {metric} z{zoom}")

                for x, y in tiles:
                    tile_path = self.get_tile_path(metric, year_month, zoom, x, y)

                    if not force and tile_path.exists():
                        stats["skipped"] += 1
                        continue

                    try:
                        tile_data = self._extract_tile(raster_data, zoom, x, y, metric)

                        if tile_data is not None:
                            tile_image = self._apply_colormap(tile_data, metric)

                            tile_path.parent.mkdir(parents=True, exist_ok=True)
                            tile_image.save(tile_path, format="PNG", optimize=True)
                            stats["generated"] += 1
                        else:
                            # Create empty transparent tile for tiles outside data bounds
                            self._save_empty_tile(tile_path)
                            stats["generated"] += 1

                    except Exception as e:
                        logger.error(f"Failed to generate tile {zoom}/{x}/{y}", error=str(e))
                        stats["failed"] += 1

        logger.info(f"Completed {year_month}", **stats)
        return stats

    async def generate_day(
        self,
        year: int,
        month: int,
        day: int,
        metrics: list[str] | None = None,
        zoom_levels: list[int] | None = None,
        force: bool = False,
    ) -> dict:
        """
        Generate all tiles for a specific day.

        Currently only supports nightlights (VIIRS daily data).
        Other metrics fall back to monthly data.

        Args:
            year: Year (e.g., 2023)
            month: Month (1-12)
            day: Day (1-31)
            metrics: List of metrics to generate (default: nightlights only for daily)
            zoom_levels: Zoom levels to generate (default: 8-10)
            force: Regenerate even if tiles exist

        Returns:
            Statistics about generated tiles
        """
        from app.services.satellite.us_data_service import USDataService

        # Only nightlights supports daily granularity
        daily_metrics = ["nightlights"]
        metrics = metrics or daily_metrics
        metrics = [m for m in metrics if m in daily_metrics]

        if not metrics:
            logger.warning("No daily-capable metrics requested")
            return {"generated": 0, "skipped": 0, "failed": 0}

        zoom_levels = zoom_levels or ZOOM_LEVELS
        date_str = f"{year}-{month:02d}-{day:02d}"

        logger.info(f"Generating daily US tiles for {date_str}", metrics=metrics, zooms=zoom_levels)

        data_service = USDataService()
        await data_service.initialize()
        stats = {"generated": 0, "skipped": 0, "failed": 0}

        for metric in metrics:
            logger.info(f"Fetching daily {metric} data for US...")

            try:
                # Fetch daily data
                if metric == "nightlights":
                    raster_data = await data_service.get_nightlights(year, month, day)
                else:
                    logger.warning(f"Daily data not supported for {metric}")
                    continue

                if raster_data is None:
                    logger.warning(f"No data available for {metric} {date_str}")
                    continue

            except Exception as e:
                logger.error(f"Failed to fetch daily {metric} data", error=str(e))
                continue

            # Generate tiles at each zoom level
            for zoom in zoom_levels:
                tiles = get_us_tiles(zoom)
                logger.info(f"Generating {len(tiles)} daily tiles for {metric} z{zoom}")

                for x, y in tiles:
                    tile_path = self.get_tile_path(metric, date_str, zoom, x, y)

                    if not force and tile_path.exists():
                        stats["skipped"] += 1
                        continue

                    try:
                        tile_data = self._extract_tile(raster_data, zoom, x, y, metric)

                        if tile_data is not None:
                            tile_image = self._apply_colormap(tile_data, metric)

                            tile_path.parent.mkdir(parents=True, exist_ok=True)
                            tile_image.save(tile_path, format="PNG", optimize=True)
                            stats["generated"] += 1
                        else:
                            self._save_empty_tile(tile_path)
                            stats["generated"] += 1

                    except Exception as e:
                        logger.error(f"Failed to generate daily tile {zoom}/{x}/{y}", error=str(e))
                        stats["failed"] += 1

        logger.info(f"Completed daily tiles for {date_str}", **stats)
        return stats

    async def _fetch_us_data(
        self,
        data_service,
        metric: str,
        year: int,
        month: int,
    ) -> np.ndarray | None:
        """Fetch metric data for the entire US using chunked approach."""
        # US is fetched in a 6x3 grid of 512x512 chunks = 3072x1536 pixels
        # This provides good detail for zoom 8-10 tiles

        # Original metrics
        if metric == "ndvi":
            return await data_service.get_ndvi(year, month)
        elif metric == "nightlights":
            return await data_service.get_nightlights(year, month)
        elif metric == "urban_density":
            return await data_service.get_urban_density(year)
        elif metric == "parking":
            return await data_service.get_parking(year, month)
        # Phase 1: Core datasets
        elif metric == "land_cover":
            return await data_service.get_dynamic_world(year, month, "built")
        elif metric == "surface_water":
            return await data_service.get_surface_water(year, month)
        elif metric == "active_fire":
            return await data_service.get_active_fire(year, month)
        # Phase 2: Air quality & weather
        elif metric == "no2":
            return await data_service.get_no2(year, month)
        elif metric == "temperature":
            return await data_service.get_temperature(year, month)
        elif metric == "precipitation":
            return await data_service.get_precipitation(year, month)
        elif metric == "aerosol":
            return await data_service.get_aerosol(year, month)
        # Phase 3: Agriculture
        elif metric == "cropland":
            return await data_service.get_cropland(year)
        elif metric == "evapotranspiration":
            return await data_service.get_evapotranspiration(year, month)
        elif metric == "soil_moisture":
            return await data_service.get_soil_moisture(year, month)
        # Phase 4: Historical & specialized
        elif metric == "impervious":
            return await data_service.get_impervious(year)
        elif metric == "fire_historical":
            return await data_service.get_fire_historical(year, month)
        elif metric == "canopy_height":
            return await data_service.get_canopy_height()

        return None

    def _extract_tile(
        self,
        us_raster: np.ndarray,
        zoom: int,
        x: int,
        y: int,
        metric: str,
    ) -> np.ndarray | None:
        """
        Extract a single tile from the US-wide raster.

        Both the raster and tiles use Web Mercator projection (EPSG:3857).
        """
        # Get tile bounds in Web Mercator meters
        tile_west, tile_south, tile_east, tile_north = tile_bounds_mercator(zoom, x, y)

        # Check if tile is within US bounds (using Mercator bounds)
        if (tile_east < US_BOUNDS_MERCATOR["west"] or tile_west > US_BOUNDS_MERCATOR["east"] or
            tile_north < US_BOUNDS_MERCATOR["south"] or tile_south > US_BOUNDS_MERCATOR["north"]):
            return None

        # Calculate pixel coordinates in the US raster
        raster_height, raster_width = us_raster.shape

        # US raster covers US_BOUNDS_MERCATOR (in Web Mercator meters)
        us_x_res = (US_BOUNDS_MERCATOR["east"] - US_BOUNDS_MERCATOR["west"]) / raster_width
        us_y_res = (US_BOUNDS_MERCATOR["north"] - US_BOUNDS_MERCATOR["south"]) / raster_height

        # Calculate source pixel coordinates (in Mercator space)
        src_col_start = int((tile_west - US_BOUNDS_MERCATOR["west"]) / us_x_res)
        src_col_end = int((tile_east - US_BOUNDS_MERCATOR["west"]) / us_x_res)
        src_row_start = int((US_BOUNDS_MERCATOR["north"] - tile_north) / us_y_res)
        src_row_end = int((US_BOUNDS_MERCATOR["north"] - tile_south) / us_y_res)

        # Clamp to valid range
        src_col_start = max(0, src_col_start)
        src_col_end = min(raster_width, src_col_end)
        src_row_start = max(0, src_row_start)
        src_row_end = min(raster_height, src_row_end)

        if src_col_end <= src_col_start or src_row_end <= src_row_start:
            return None

        # Extract region
        region = us_raster[src_row_start:src_row_end, src_col_start:src_col_end]

        if region.size == 0:
            return None

        # Normalize values
        val_min, val_max = self.VALUE_RANGES.get(metric, (0.0, 1.0))
        region_clean = np.nan_to_num(region, nan=val_min)
        region_normalized = (region_clean - val_min) / (val_max - val_min)
        region_normalized = np.clip(region_normalized, 0, 1)

        # Resize to tile size
        region_uint8 = (region_normalized * 255).astype(np.uint8)
        region_img = Image.fromarray(region_uint8)
        tile_img = region_img.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)

        return np.array(tile_img) / 255.0

    def _apply_colormap(self, data: np.ndarray, metric: str) -> Image.Image:
        """Apply a colormap to tile data."""
        colors = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])

        height, width = data.shape
        rgb = np.zeros((height, width, 4), dtype=np.uint8)

        # Vectorized colormap application
        for i in range(len(colors)):
            lower = i / len(colors)
            upper = (i + 1) / len(colors)
            mask = (data >= lower) & (data < upper)

            if i < len(colors) - 1:
                t = (data[mask] - lower) / (upper - lower)
                c_low = np.array(colors[i])
                c_high = np.array(colors[min(i + 1, len(colors) - 1)])

                rgb[mask, 0] = (c_low[0] * (1 - t) + c_high[0] * t).astype(np.uint8)
                rgb[mask, 1] = (c_low[1] * (1 - t) + c_high[1] * t).astype(np.uint8)
                rgb[mask, 2] = (c_low[2] * (1 - t) + c_high[2] * t).astype(np.uint8)
                rgb[mask, 3] = 200  # Semi-transparent for overlay

        # Handle the last color bin
        mask = data >= (len(colors) - 1) / len(colors)
        rgb[mask, 0] = colors[-1][0]
        rgb[mask, 1] = colors[-1][1]
        rgb[mask, 2] = colors[-1][2]
        rgb[mask, 3] = 200

        # Make zero/nan transparent
        zero_mask = data <= 0.001
        rgb[zero_mask, 3] = 0

        return Image.fromarray(rgb, "RGBA")

    def _save_empty_tile(self, path: Path):
        """Save an empty transparent tile."""
        img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="PNG")


async def generate_all_us_tiles(
    start_year: int = 2023,
    end_year: int = 2024,
    metrics: list[str] | None = None,
):
    """Generate all US tiles for the specified date range."""
    generator = USTileGenerator()

    total_stats = {"generated": 0, "skipped": 0, "failed": 0}

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # Skip future months
            if year == 2024 and month > 12:
                continue

            stats = await generator.generate_month(year, month, metrics)

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

    return total_stats
