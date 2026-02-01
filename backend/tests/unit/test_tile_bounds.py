from __future__ import annotations

import math

from app.gee import GLOBAL_TILE_BOUNDS_WGS84, WEB_MERCATOR_MAX_LAT


def _tiley_to_lat(y: int, z: int) -> float:
    """
    Convert a Web Mercator tile y index to the latitude of the tile's top edge.

    This mirrors the XYZ tiling scheme used by Leaflet/Google Maps (EPSG:3857).
    """
    n = 2 ** z
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    return lat_rad * 180 / math.pi


def test_global_tile_bounds_cover_full_web_mercator_lat_extent():
    _, min_lat, _, max_lat = GLOBAL_TILE_BOUNDS_WGS84
    assert max_lat >= WEB_MERCATOR_MAX_LAT - 1e-6
    assert min_lat <= -WEB_MERCATOR_MAX_LAT + 1e-6


def test_global_tile_bounds_do_not_clip_extreme_tile_rows():
    # Regression: using ±85° clips the outermost tile rows at higher zooms.
    _, min_lat, _, max_lat = GLOBAL_TILE_BOUNDS_WGS84
    z = 10

    bottom_edge_of_top_row = _tiley_to_lat(1, z)
    top_edge_of_bottom_row = _tiley_to_lat((2 ** z) - 1, z)

    assert max_lat >= bottom_edge_of_top_row
    assert min_lat <= top_edge_of_bottom_row

