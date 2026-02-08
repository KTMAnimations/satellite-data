from __future__ import annotations

from app.gee import _tile_render_variant


def test_tile_render_variant_uses_low_zoom_proxy_for_selected_metrics():
    assert _tile_render_variant("ndvi", z=6) == "ndvi_low_zoom_proxy"
    assert _tile_render_variant("cropland", z=6) == "cropland_low_zoom_proxy"
    assert _tile_render_variant("surface_water", z=6) == "surface_water_low_zoom_proxy"


def test_tile_render_variant_defaults_outside_low_zoom_proxy_mode():
    assert _tile_render_variant("ndvi", z=7) == "default"
    assert _tile_render_variant("surface_water", z=None) == "default"
    assert _tile_render_variant("cropland", z=None) == "default"
    assert _tile_render_variant("nightlights", z=4) == "default"
