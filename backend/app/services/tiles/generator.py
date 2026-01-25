from datetime import date
from io import BytesIO
from pathlib import Path

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
            (165, 0, 38),  # -1: Dark red
            (215, 48, 39),  # -0.5: Red
            (244, 109, 67),  # 0: Orange
            (253, 174, 97),  # 0.25: Light orange
            (254, 224, 139),  # 0.5: Yellow
            (217, 239, 139),  # 0.6: Light green
            (166, 217, 106),  # 0.7: Green
            (102, 189, 99),  # 0.8: Darker green
            (26, 152, 80),  # 0.9: Dark green
            (0, 104, 55),  # 1: Very dark green
        ],
        "nightlights": [
            (0, 0, 0),  # 0: Black
            (30, 0, 50),  # Low: Dark purple
            (60, 0, 100),  #
            (100, 0, 150),  #
            (150, 50, 150),  #
            (200, 100, 100),  #
            (255, 150, 50),  # Medium: Orange
            (255, 200, 100),  #
            (255, 255, 150),  #
            (255, 255, 255),  # High: White
        ],
        "urban_density": [
            (255, 255, 229),  # 0: Light yellow
            (255, 247, 188),
            (254, 227, 145),
            (254, 196, 79),
            (254, 153, 41),
            (236, 112, 20),
            (204, 76, 2),
            (153, 52, 4),
            (102, 37, 6),
            (51, 18, 3),  # 1: Dark brown
        ],
        "parking": [
            (247, 251, 255),  # 0: Very light blue
            (222, 235, 247),
            (198, 219, 239),
            (158, 202, 225),
            (107, 174, 214),
            (66, 146, 198),
            (33, 113, 181),
            (8, 81, 156),
            (8, 48, 107),
            (3, 19, 43),  # 1: Very dark blue
        ],
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
        date: date | None = None,
    ) -> bytes:
        """
        Generate a map tile for a specific location and metric.

        Args:
            region_id: Region ID
            metric: Metric name
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            date: Optional date for temporal data

        Returns:
            PNG image data as bytes
        """
        # Calculate tile bounds
        bounds = self._tile_bounds(z, x, y)

        # Try to load cached tile
        cache_path = self._get_cache_path(region_id, metric, z, x, y, date)
        if cache_path.exists():
            return cache_path.read_bytes()

        # Load raster data for this region/metric/date
        raster_data = await self._load_raster_data(region_id, metric, date)

        if raster_data is None:
            # Return empty tile if no data
            return create_empty_tile()

        # Extract tile from raster
        tile_data = self._extract_tile(raster_data, bounds, z)

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
        """Calculate geographic bounds for a tile."""
        import math

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
        date: date | None,
    ) -> Path:
        """Get cache file path for a tile."""
        date_str = date.isoformat() if date else "latest"
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

    async def _load_raster_data(
        self,
        region_id: str,
        metric: str,
        date: date | None,
    ) -> np.ndarray | None:
        """Load raster data from storage."""
        from sqlalchemy import select

        from app.core.database import get_db_context
        from app.models.observation import Observation

        async with get_db_context() as db:
            query = select(Observation).where(
                Observation.region_id == region_id,
                Observation.metric == metric,
                Observation.raster_path.isnot(None),
            )

            if date:
                query = query.where(Observation.date == date)
            else:
                query = query.order_by(Observation.date.desc())

            result = await db.execute(query.limit(1))
            obs = result.scalar_one_or_none()

            if obs is None or obs.raster_path is None:
                return None

            # Load raster
            try:
                import rasterio

                with rasterio.open(obs.raster_path) as src:
                    return src.read(1)
            except Exception as e:
                logger.error("Failed to load raster", path=obs.raster_path, error=str(e))
                return None

    def _extract_tile(
        self,
        raster: np.ndarray,
        bounds: tuple[float, float, float, float],
        zoom: int,
    ) -> np.ndarray:
        """Extract a tile region from a raster."""
        # This is a simplified implementation
        # In production, use rasterio for proper georeferencing

        # For now, just resize to tile size
        from PIL import Image

        # Normalize and convert to image
        vmin, vmax = np.nanmin(raster), np.nanmax(raster)
        if vmax > vmin:
            normalized = (raster - vmin) / (vmax - vmin)
        else:
            normalized = np.zeros_like(raster)

        normalized = np.nan_to_num(normalized, nan=0)
        normalized = (normalized * 255).astype(np.uint8)

        img = Image.fromarray(normalized)
        img = img.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.BILINEAR)

        return np.array(img) / 255.0

    def _apply_colormap(self, data: np.ndarray, metric: str) -> Image.Image:
        """Apply a colormap to tile data."""
        colors = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])

        # Create RGB image
        height, width = data.shape
        rgb = np.zeros((height, width, 4), dtype=np.uint8)

        # Apply colormap
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
