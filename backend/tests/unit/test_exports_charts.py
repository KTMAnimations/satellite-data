from __future__ import annotations

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Rect

from app.routes.exports import _build_pdf_time_series_chart


def _extract_line_chart(drawing):  # type: ignore[no-untyped-def]
    for item in drawing.contents:
        if isinstance(item, HorizontalLineChart):
            return item
    raise AssertionError("HorizontalLineChart not found in drawing")


def test_pdf_time_series_chart_normalizes_each_metric_independently():
    series_by_metric = {
        "nightlights": [
            ("2024-01", 10.0),
            ("2024-02", 20.0),
            ("2024-03", 30.0),
        ],
        "temperature": [
            ("2024-01", -5.0),
            ("2024-03", 15.0),
        ],
    }

    drawing = _build_pdf_time_series_chart(series_by_metric, ["nightlights", "temperature"], available_width=500.0)
    assert drawing is not None

    chart = _extract_line_chart(drawing)
    assert chart.valueAxis.valueMin == 0
    assert chart.valueAxis.valueMax == 100
    assert chart.valueAxis.valueStep == 20
    assert chart.categoryAxis.categoryNames == ["2024-01", "2024-02", "2024-03"]
    assert chart.data == [
        [0.0, 50.0, 100.0],
        [0.0, None, 100.0],
    ]


def test_pdf_time_series_chart_constant_series_uses_midline():
    series_by_metric = {
        "aerosol": [
            ("2024-01", 1.23),
            ("2024-02", 1.23),
            ("2024-03", 1.23),
        ],
    }

    drawing = _build_pdf_time_series_chart(series_by_metric, ["aerosol"], available_width=500.0)
    assert drawing is not None

    chart = _extract_line_chart(drawing)
    assert chart.data == [[50.0, 50.0, 50.0]]


def test_pdf_time_series_chart_legend_stays_above_plot_area():
    metrics = [
        "ndvi",
        "nightlights",
        "surface_water",
        "no2",
        "temperature",
        "precipitation",
        "aerosol",
        "cropland",
        "evapotranspiration",
        "soil_moisture",
    ]
    series_by_metric = {
        metric: [
            ("2024-01", float(i)),
            ("2024-02", float(i + 1)),
            ("2024-03", float(i + 2)),
        ]
        for i, metric in enumerate(metrics, start=1)
    }

    drawing = _build_pdf_time_series_chart(series_by_metric, metrics, available_width=500.0)
    assert drawing is not None

    chart = _extract_line_chart(drawing)
    chart_top = chart.y + chart.height
    legend_rects = [item for item in drawing.contents if isinstance(item, Rect)]
    assert legend_rects
    assert min(rect.y for rect in legend_rects) > chart_top
