from __future__ import annotations

from app.gee import METRICS, _tile_visualization_range


def test_tile_visualization_range_defaults_to_metric_value_range():
    metric = METRICS["ndvi"]
    assert _tile_visualization_range(metric) == metric.value_range


def test_tile_visualization_range_uses_metric_specific_overrides():
    assert _tile_visualization_range(METRICS["precipitation"]) == (0.0, 180.0)
    assert _tile_visualization_range(METRICS["no2"]) == (0.0, 0.00008)
    assert _tile_visualization_range(METRICS["aerosol"]) == (-0.5, 1.5)
    assert _tile_visualization_range(METRICS["parking"]) == (0.2, 0.6)
