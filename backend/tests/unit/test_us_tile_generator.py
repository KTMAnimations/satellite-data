"""
Unit tests for US tile generation utilities.

These tests focus on tile extraction from the US-wide raster, ensuring that
resampling does not introduce obvious seams at tile boundaries.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.services.tiles.us_tile_generator import (
    TILE_SIZE,
    US_BOUNDS_MERCATOR,
    USTileGenerator,
    tile_bounds_mercator,
)


def _extract_tile_naive(
    generator: USTileGenerator,
    us_raster: np.ndarray,
    zoom: int,
    x: int,
    y: int,
    metric: str,
) -> np.ndarray | None:
    """
    Replicates the pre-padding resampling approach for comparison.

    Extracts the tile-aligned region and resizes it directly to TILE_SIZE.
    """
    tile_west, tile_south, tile_east, tile_north = tile_bounds_mercator(zoom, x, y)

    raster_height, raster_width = us_raster.shape
    us_x_res = (US_BOUNDS_MERCATOR["east"] - US_BOUNDS_MERCATOR["west"]) / raster_width
    us_y_res = (US_BOUNDS_MERCATOR["north"] - US_BOUNDS_MERCATOR["south"]) / raster_height

    src_col_start = int((tile_west - US_BOUNDS_MERCATOR["west"]) / us_x_res)
    src_col_end = int((tile_east - US_BOUNDS_MERCATOR["west"]) / us_x_res)
    src_row_start = int((US_BOUNDS_MERCATOR["north"] - tile_north) / us_y_res)
    src_row_end = int((US_BOUNDS_MERCATOR["north"] - tile_south) / us_y_res)

    src_col_start = max(0, src_col_start)
    src_col_end = min(raster_width, src_col_end)
    src_row_start = max(0, src_row_start)
    src_row_end = min(raster_height, src_row_end)

    if src_col_end <= src_col_start or src_row_end <= src_row_start:
        return None

    region = us_raster[src_row_start:src_row_end, src_col_start:src_col_end]
    if region.size == 0:
        return None

    val_min, val_max = generator.VALUE_RANGES.get(metric, (0.0, 1.0))
    region_clean = np.nan_to_num(region, nan=val_min)
    region_normalized = (region_clean - val_min) / (val_max - val_min)
    region_normalized = np.clip(region_normalized, 0, 1)

    region_uint8 = (region_normalized * 255).astype(np.uint8)
    region_img = Image.fromarray(region_uint8)
    tile_img = region_img.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)

    return np.array(tile_img) / 255.0


def test_extract_tile_reduces_seams_at_boundaries():
    """
    Adjacent tiles extracted from a smooth raster should not show strong seams
    caused purely by resampling edge effects.

    The padded extraction approach should produce a lower seam error than the
    naive approach.
    """
    generator = USTileGenerator()

    # Synthetic US raster (3072x1536) with high-frequency variation to make
    # edge artifacts easier to detect.
    height, width = 1536, 3072
    x = np.linspace(0, 2 * np.pi, width, endpoint=False, dtype=np.float32)
    y = np.linspace(0, 2 * np.pi, height, endpoint=False, dtype=np.float32)

    # Broadcasting keeps memory use reasonable while still producing a full
    # raster.
    us_raster = (np.sin(x * 40)[None, :] + np.cos(y * 30)[:, None]) * 0.5 + 0.5
    us_raster = np.clip(us_raster, 0, 1).astype(np.float32)

    zoom = 11
    y_tile = 770
    x_left = 602
    x_right = 603
    metric = "land_cover"  # value range 0-1 keeps normalization simple

    left_naive = _extract_tile_naive(generator, us_raster, zoom, x_left, y_tile, metric)
    right_naive = _extract_tile_naive(generator, us_raster, zoom, x_right, y_tile, metric)
    left = generator._extract_tile(us_raster, zoom, x_left, y_tile, metric)
    right = generator._extract_tile(us_raster, zoom, x_right, y_tile, metric)

    assert left_naive is not None and right_naive is not None
    assert left is not None and right is not None
    assert left.shape == (TILE_SIZE, TILE_SIZE)
    assert right.shape == (TILE_SIZE, TILE_SIZE)

    seam_naive = float(np.abs(left_naive[:, -1] - right_naive[:, 0]).mean())
    seam_padded = float(np.abs(left[:, -1] - right[:, 0]).mean())

    # Padded extraction should materially reduce the seam magnitude.
    assert seam_padded < seam_naive
    assert seam_padded <= seam_naive * 0.75

