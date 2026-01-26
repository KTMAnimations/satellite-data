"""
US-Wide Tile Generator

Pre-generates map tiles for the entire continental US at zoom levels 8-10.
Tiles are stored in standard XYZ format: /{metric}/{YYYY-MM}/{z}/{x}/{y}.png
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

# Continental US bounding box
US_BOUNDS = {
    "west": -125.0,
    "east": -66.0,
    "south": 24.0,
    "north": 50.0,
}

# Metrics to generate
METRICS = ["ndvi", "nightlights", "urban_density", "parking"]

# Zoom levels to generate
ZOOM_LEVELS = [8, 9, 10]


def lon_to_tile_x(lon: float, zoom: int) -> int:
    """Convert longitude to tile X coordinate."""
    return int((lon + 180) / 360 * (2 ** zoom))


def lat_to_tile_y(lat: float, zoom: int) -> int:
    """Convert latitude to tile Y coordinate."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    return int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Get geographic bounds for a tile (west, south, east, north)."""
    n = 2 ** z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180

    north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))

    south = math.degrees(south_rad)
    north = math.degrees(north_rad)

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
    }

    # Value ranges for normalization
    VALUE_RANGES = {
        "ndvi": (-1.0, 1.0),
        "nightlights": (0.0, 100.0),
        "urban_density": (0.0, 1.0),
        "parking": (0.0, 1.0),
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
        year_month: str,
        z: int,
        x: int,
        y: int,
    ) -> Path:
        """Get the file path for a pre-generated tile."""
        return self.tiles_dir / metric / year_month / str(z) / str(x) / f"{y}.png"

    def tile_exists(
        self,
        metric: str,
        year_month: str,
        z: int,
        x: int,
        y: int,
    ) -> bool:
        """Check if a tile has already been generated."""
        return self.get_tile_path(metric, year_month, z, x, y).exists()

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

        if metric == "ndvi":
            return await data_service.get_ndvi(year, month)
        elif metric == "nightlights":
            return await data_service.get_nightlights(year, month)
        elif metric == "urban_density":
            return await data_service.get_urban_density(year)
        elif metric == "parking":
            return await data_service.get_parking(year, month)

        return None

    def _extract_tile(
        self,
        us_raster: np.ndarray,
        zoom: int,
        x: int,
        y: int,
        metric: str,
    ) -> np.ndarray | None:
        """Extract a single tile from the US-wide raster."""
        # Get tile bounds
        tile_west, tile_south, tile_east, tile_north = tile_bounds(zoom, x, y)

        # Check if tile is within US bounds
        if (tile_east < US_BOUNDS["west"] or tile_west > US_BOUNDS["east"] or
            tile_north < US_BOUNDS["south"] or tile_south > US_BOUNDS["north"]):
            return None

        # Calculate pixel coordinates in the US raster
        raster_height, raster_width = us_raster.shape

        # US raster covers US_BOUNDS
        us_lon_res = (US_BOUNDS["east"] - US_BOUNDS["west"]) / raster_width
        us_lat_res = (US_BOUNDS["north"] - US_BOUNDS["south"]) / raster_height

        # Calculate source pixel coordinates
        src_col_start = int((tile_west - US_BOUNDS["west"]) / us_lon_res)
        src_col_end = int((tile_east - US_BOUNDS["west"]) / us_lon_res)
        src_row_start = int((US_BOUNDS["north"] - tile_north) / us_lat_res)
        src_row_end = int((US_BOUNDS["north"] - tile_south) / us_lat_res)

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
