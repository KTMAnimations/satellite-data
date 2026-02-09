from __future__ import annotations

from app.routes.exports import _bounds_to_polygon, _normalize_bounds, _resolve_animation_bounds


def test_normalize_bounds_clamps_and_orders() -> None:
    bounds = _normalize_bounds((200.0, 95.0, -200.0, -95.0))
    assert bounds == (-160.0, -85.05112878, 160.0, 85.05112878)


def test_normalize_bounds_prevents_zero_sized_extent() -> None:
    min_lon, min_lat, max_lon, max_lat = _normalize_bounds((10.0, 20.0, 10.0, 20.0))
    assert max_lon > min_lon
    assert max_lat > min_lat


def test_resolve_animation_bounds_falls_back_on_invalid_input() -> None:
    fallback = (-5.0, -4.0, 5.0, 4.0)
    # Intentionally invalid shape/value to verify fallback behavior.
    resolved = _resolve_animation_bounds(("bad", 1.0, 2.0, 3.0), fallback)  # type: ignore[arg-type]
    assert resolved == fallback


def test_bounds_to_polygon_returns_closed_ring() -> None:
    polygon = _bounds_to_polygon((-2.0, -1.0, 3.0, 4.0))
    ring = polygon["coordinates"][0]
    assert polygon["type"] == "Polygon"
    assert ring[0] == [-2.0, -1.0]
    assert ring[-1] == ring[0]


def test_normalize_bounds_wraps_world_copy_longitudes() -> None:
    min_lon, _, max_lon, _ = _normalize_bounds((250.0, -5.0, 260.0, 5.0))
    assert min_lon == -110.0
    assert max_lon == -100.0
