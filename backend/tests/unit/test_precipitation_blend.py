from __future__ import annotations

import pytest

from app.gee import _precipitation_blend_lat_bounds, _precipitation_era5_weight_for_abs_lat


def test_precipitation_blend_bounds_are_centered_on_chirps_limit():
    start, end = _precipitation_blend_lat_bounds()
    assert start < 50.0 < end
    assert ((start + end) / 2) == 50.0


def test_precipitation_era5_weight_is_clamped_linear():
    start, end = _precipitation_blend_lat_bounds()
    mid = (start + end) / 2

    assert _precipitation_era5_weight_for_abs_lat(start - 10) == 0.0
    assert _precipitation_era5_weight_for_abs_lat(start) == 0.0
    assert _precipitation_era5_weight_for_abs_lat(mid) == pytest.approx(0.5)
    assert _precipitation_era5_weight_for_abs_lat(end) == 1.0
    assert _precipitation_era5_weight_for_abs_lat(end + 10) == 1.0
