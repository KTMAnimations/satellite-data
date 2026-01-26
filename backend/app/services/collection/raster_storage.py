"""
Raster Storage Utilities

Save metric raster data as properly georeferenced GeoTIFF files for tile serving.
"""

from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def save_raster(
    raster: np.ndarray,
    bounds: tuple[float, float, float, float],
    region_id: str,
    metric: str,
    obs_date: date,
) -> str | None:
    """
    Save a raster array as a GeoTIFF file.

    Args:
        raster: 2D numpy array with metric values
        bounds: Geographic bounds (lon_min, lat_min, lon_max, lat_max)
        region_id: UUID of the region
        metric: Name of the metric (ndvi, nightlights, etc.)
        obs_date: Date of the observation

    Returns:
        Relative path to the saved raster file, or None if save failed
    """
    if raster is None or bounds is None:
        logger.warning("Cannot save raster: missing data or bounds")
        return None

    settings = get_settings()

    # Ensure raster is 2D
    if raster.ndim == 1:
        # Try to reshape if it's a flattened square
        side = int(np.sqrt(raster.shape[0]))
        if side * side == raster.shape[0]:
            raster = raster.reshape((side, side))
        else:
            logger.warning(f"Cannot reshape 1D raster of size {raster.shape[0]}")
            return None

    if raster.ndim != 2:
        logger.warning(f"Invalid raster dimensions: {raster.ndim}")
        return None

    # Create directory structure: rasters/<region_id>/<metric>/<year>/
    base_dir = Path(settings.rasters_dir)
    raster_dir = base_dir / region_id / metric / str(obs_date.year)
    raster_dir.mkdir(parents=True, exist_ok=True)

    # File name: YYYY-MM-DD.tif
    filename = f"{obs_date.isoformat()}.tif"
    file_path = raster_dir / filename

    # Calculate transform from bounds
    lon_min, lat_min, lon_max, lat_max = bounds
    height, width = raster.shape
    transform = from_bounds(lon_min, lat_min, lon_max, lat_max, width, height)

    # Ensure data type is appropriate
    if raster.dtype == np.float64:
        raster = raster.astype(np.float32)

    # Replace NaN with nodata value
    nodata = -9999.0
    raster_clean = np.where(np.isnan(raster), nodata, raster)

    try:
        # Write GeoTIFF with proper georeferencing
        with rasterio.open(
            file_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=raster_clean.dtype,
            crs='EPSG:4326',
            transform=transform,
            nodata=nodata,
            compress='lzw',  # Lossless compression
        ) as dst:
            dst.write(raster_clean, 1)

        # Return relative path from rasters_dir
        relative_path = str(file_path.relative_to(base_dir))
        logger.debug(f"Saved raster to {relative_path}", size=f"{height}x{width}")
        return relative_path

    except Exception as e:
        logger.error(f"Failed to save raster: {e}", exc_info=True)
        return None


def load_raster(raster_path: str) -> tuple[np.ndarray, tuple[float, float, float, float]] | tuple[None, None]:
    """
    Load a raster from file.

    Args:
        raster_path: Relative path from rasters_dir

    Returns:
        Tuple of (raster array, bounds) or (None, None) if load failed
    """
    settings = get_settings()
    full_path = Path(settings.rasters_dir) / raster_path

    if not full_path.exists():
        logger.warning(f"Raster file not found: {full_path}")
        return None, None

    try:
        with rasterio.open(full_path) as src:
            raster = src.read(1)
            bounds = src.bounds

            # Replace nodata with NaN
            nodata = src.nodata
            if nodata is not None:
                raster = np.where(raster == nodata, np.nan, raster)

            return raster, (bounds.left, bounds.bottom, bounds.right, bounds.top)

    except Exception as e:
        logger.error(f"Failed to load raster: {e}", exc_info=True)
        return None, None


def get_raster_full_path(raster_path: str) -> Path:
    """Get full filesystem path for a raster."""
    settings = get_settings()
    return Path(settings.rasters_dir) / raster_path
