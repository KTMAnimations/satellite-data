"""
Tile Generator

Generate map tiles from raster data with proper georeferencing.
"""

from datetime import date
from io import BytesIO
from pathlib import Path

import math
import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Tile size in pixels
TILE_SIZE = 256


def create_empty_tile() -> bytes:
    """Create a transparent empty tile."""
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TileGenerator:
    """Generate map tiles from raster data."""

    # Color maps for metrics
    COLORMAPS = {
        "ndvi": [
            (165, 0, 38),    # -1: Dark red
            (215, 48, 39),   # -0.5: Red
            (244, 109, 67),  # 0: Orange
            (253, 174, 97),  # 0.25: Light orange
            (254, 224, 139), # 0.5: Yellow
            (217, 239, 139), # 0.6: Light green
            (166, 217, 106), # 0.7: Green
            (102, 189, 99),  # 0.8: Darker green
            (26, 152, 80),   # 0.9: Dark green
            (0, 104, 55),    # 1: Very dark green
        ],
        "nightlights": [
            (0, 0, 0),       # 0: Black
            (30, 0, 50),     # Low: Dark purple
            (60, 0, 100),
            (100, 0, 150),
            (150, 50, 150),
            (200, 100, 100),
            (255, 150, 50),  # Medium: Orange
            (255, 200, 100),
            (255, 255, 150),
            (255, 255, 255), # High: White
        ],
        "urban_density": [
            (255, 255, 229), # 0: Light yellow
            (255, 247, 188),
            (254, 227, 145),
            (254, 196, 79),
            (254, 153, 41),
            (236, 112, 20),
            (204, 76, 2),
            (153, 52, 4),
            (102, 37, 6),
            (51, 18, 3),     # 1: Dark brown
        ],
        "parking": [
            (247, 251, 255), # 0: Very light blue
            (222, 235, 247),
            (198, 219, 239),
            (158, 202, 225),
            (107, 174, 214),
            (66, 146, 198),
            (33, 113, 181),
            (8, 81, 156),
            (8, 48, 107),
            (3, 19, 43),     # 1: Very dark blue
        ],
    }

    # Value ranges for normalization
    VALUE_RANGES = {
        "ndvi": (-1.0, 1.0),
        "nightlights": (0.0, 100.0),
        "urban_density": (0.0, 1.0),
        "parking": (0.0, 1.0),
    }

    def __init__(self):
        self.settings = get_settings()

    async def generate_tile(
        self,
        region_id: str,
        metric: str,
        z: int,
        x: int,
        y: int,
        tile_date: date | None = None,
    ) -> bytes:
        """
        Generate a map tile for a specific location and metric.

        Args:
            region_id: Region ID
            metric: Metric name
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            tile_date: Optional date for temporal data

        Returns:
            PNG image data as bytes
        """
        # Calculate tile bounds
        tile_bounds = self._tile_bounds(z, x, y)

        # Try to load cached tile
        cache_path = self._get_cache_path(region_id, metric, z, x, y, tile_date)
        if cache_path.exists():
            return cache_path.read_bytes()

        # Load raster data with bounds for this region/metric/date
        raster_data, raster_bounds = await self._load_raster_with_bounds(
            region_id, metric, tile_date
        )

        if raster_data is None:
            # Return empty tile if no data
            return create_empty_tile()

        # Extract tile from raster using proper georeferencing
        tile_data = self._extract_tile_georeferenced(
            raster_data, raster_bounds, tile_bounds, metric
        )

        if tile_data is None:
            # Tile doesn't overlap with raster
            return create_empty_tile()

        # Apply colormap
        tile_image = self._apply_colormap(tile_data, metric)

        # Convert to PNG
        buffer = BytesIO()
        tile_image.save(buffer, format="PNG")
        tile_bytes = buffer.getvalue()

        # Cache the tile
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(tile_bytes)

        return tile_bytes

    def _tile_bounds(
        self, z: int, x: int, y: int
    ) -> tuple[float, float, float, float]:
        """Calculate geographic bounds for a tile (lon_min, lat_min, lon_max, lat_max)."""
        n = 2**z
        lon_min = x / n * 360 - 180
        lon_max = (x + 1) / n * 360 - 180

        lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))

        lat_min = math.degrees(lat_min_rad)
        lat_max = math.degrees(lat_max_rad)

        return (lon_min, lat_min, lon_max, lat_max)

    def _get_cache_path(
        self,
        region_id: str,
        metric: str,
        z: int,
        x: int,
        y: int,
        tile_date: date | None,
    ) -> Path:
        """Get cache file path for a tile."""
        date_str = tile_date.isoformat() if tile_date else "latest"
        return (
            Path(self.settings.cache_dir)
            / "tiles"
            / region_id
            / metric
            / date_str
            / str(z)
            / str(x)
            / f"{y}.png"
        )

    async def _load_raster_with_bounds(
        self,
        region_id: str,
        metric: str,
        tile_date: date | None,
    ) -> tuple[np.ndarray | None, tuple[float, float, float, float] | None]:
        """
        Load raster data with geographic bounds from storage.

        Returns:
            Tuple of (raster array, bounds) or (None, None) if not found
        """
        import rasterio
        from sqlalchemy import select

        from app.core.database import get_db_context
        from app.models.observation import Observation

        async with get_db_context() as db:
            # Find observation
            query = select(Observation).where(
                Observation.region_id == region_id,
                Observation.metric == metric,
            )

            if tile_date:
                query = query.where(Observation.date == tile_date)
            else:
                query = query.order_by(Observation.date.desc())

            result = await db.execute(query.limit(1))
            obs = result.scalar_one_or_none()

            if obs is None:
                return None, None

            # Try to load actual raster file
            if obs.raster_path:
                try:
                    full_path = Path(self.settings.rasters_dir) / obs.raster_path
                    if full_path.exists():
                        with rasterio.open(full_path) as src:
                            raster = src.read(1)
                            bounds = src.bounds

                            # Replace nodata with NaN
                            nodata = src.nodata
                            if nodata is not None:
                                raster = np.where(raster == nodata, np.nan, raster)

                            return raster, (bounds.left, bounds.bottom, bounds.right, bounds.top)
                except Exception as e:
                    logger.error("Failed to load raster", path=obs.raster_path, error=str(e))

            # No raster file available - return None (no synthetic data)
            # Real raster data must be collected via data collection pipeline
            logger.debug(
                "No raster file available for observation",
                region_id=region_id,
                metric=metric,
                date=str(tile_date),
                has_value=obs.value is not None,
            )
            return None, None

    def _extract_tile_georeferenced(
        self,
        raster: np.ndarray,
        raster_bounds: tuple[float, float, float, float],
        tile_bounds: tuple[float, float, float, float],
        metric: str,
    ) -> np.ndarray | None:
        """
        Extract a tile from a raster using proper georeferencing.

        Args:
            raster: Source raster data
            raster_bounds: (lon_min, lat_min, lon_max, lat_max) of raster
            tile_bounds: (lon_min, lat_min, lon_max, lat_max) of requested tile
            metric: Metric name for normalization

        Returns:
            256x256 tile array with normalized values, or None if no overlap
        """
        rast_lon_min, rast_lat_min, rast_lon_max, rast_lat_max = raster_bounds
        tile_lon_min, tile_lat_min, tile_lon_max, tile_lat_max = tile_bounds

        # Check for overlap
        if (tile_lon_max < rast_lon_min or tile_lon_min > rast_lon_max or
            tile_lat_max < rast_lat_min or tile_lat_min > rast_lat_max):
            return None

        # Calculate intersection bounds
        int_lon_min = max(tile_lon_min, rast_lon_min)
        int_lon_max = min(tile_lon_max, rast_lon_max)
        int_lat_min = max(tile_lat_min, rast_lat_min)
        int_lat_max = min(tile_lat_max, rast_lat_max)

        # Calculate pixel coordinates in the source raster
        raster_height, raster_width = raster.shape
        rast_lon_res = (rast_lon_max - rast_lon_min) / raster_width
        rast_lat_res = (rast_lat_max - rast_lat_min) / raster_height

        # Raster row 0 is typically at lat_max (north), increasing row = decreasing lat
        col_start = int((int_lon_min - rast_lon_min) / rast_lon_res)
        col_end = int((int_lon_max - rast_lon_min) / rast_lon_res)
        row_start = int((rast_lat_max - int_lat_max) / rast_lat_res)
        row_end = int((rast_lat_max - int_lat_min) / rast_lat_res)

        # Clamp to valid range
        col_start = max(0, min(col_start, raster_width - 1))
        col_end = max(1, min(col_end, raster_width))
        row_start = max(0, min(row_start, raster_height - 1))
        row_end = max(1, min(row_end, raster_height))

        # Extract the region
        region = raster[row_start:row_end, col_start:col_end]

        if region.size == 0:
            return None

        # Calculate where this region fits in the output tile
        tile_lon_res = (tile_lon_max - tile_lon_min) / TILE_SIZE
        tile_lat_res = (tile_lat_max - tile_lat_min) / TILE_SIZE

        out_col_start = int((int_lon_min - tile_lon_min) / tile_lon_res)
        out_col_end = int((int_lon_max - tile_lon_min) / tile_lon_res)
        out_row_start = int((tile_lat_max - int_lat_max) / tile_lat_res)
        out_row_end = int((tile_lat_max - int_lat_min) / tile_lat_res)

        # Clamp to tile dimensions
        out_col_start = max(0, min(out_col_start, TILE_SIZE - 1))
        out_col_end = max(1, min(out_col_end, TILE_SIZE))
        out_row_start = max(0, min(out_row_start, TILE_SIZE - 1))
        out_row_end = max(1, min(out_row_end, TILE_SIZE))

        out_width = out_col_end - out_col_start
        out_height = out_row_end - out_row_start

        if out_width <= 0 or out_height <= 0:
            return None

        # Resize the extracted region to fit the output area
        from PIL import Image

        # Normalize data based on metric's value range
        val_min, val_max = self.VALUE_RANGES.get(metric, (0.0, 1.0))
        region_clean = np.nan_to_num(region, nan=val_min)
        # Normalize to 0-1 range
        region_normalized = (region_clean - val_min) / (val_max - val_min)
        region_uint8 = (np.clip(region_normalized, 0, 1) * 255).astype(np.uint8)
        region_img = Image.fromarray(region_uint8)
        region_resized = region_img.resize((out_width, out_height), Image.Resampling.BILINEAR)
        region_resized_arr = np.array(region_resized) / 255.0

        # Create output tile (transparent background)
        tile = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)

        # Place the resized region into the tile
        tile[out_row_start:out_row_start + out_height,
             out_col_start:out_col_start + out_width] = region_resized_arr

        return tile

    def _apply_colormap(self, data: np.ndarray, metric: str) -> Image.Image:
        """Apply a colormap to tile data."""
        colors = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])

        # Create RGBA image
        height, width = data.shape
        rgb = np.zeros((height, width, 4), dtype=np.uint8)

        # Vectorized colormap application
        for i in range(height):
            for j in range(width):
                val = data[i, j]
                if np.isnan(val) or val == 0:
                    rgb[i, j] = [0, 0, 0, 0]  # Transparent
                else:
                    # Linear interpolation between colors
                    idx = val * (len(colors) - 1)
                    idx_low = int(idx)
                    idx_high = min(idx_low + 1, len(colors) - 1)
                    t = idx - idx_low

                    c_low = colors[idx_low]
                    c_high = colors[idx_high]

                    r = int(c_low[0] * (1 - t) + c_high[0] * t)
                    g = int(c_low[1] * (1 - t) + c_high[1] * t)
                    b = int(c_low[2] * (1 - t) + c_high[2] * t)

                    rgb[i, j] = [r, g, b, 255]

        return Image.fromarray(rgb, "RGBA")
