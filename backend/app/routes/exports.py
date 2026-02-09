from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import math
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import imageio
import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from PIL import Image
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee_concurrency import gee_to_thread
from app.gee import METRICS, build_metric_image, bucket_end, bucket_starts, geojson_to_ee_geometry, initialize_ee
from app.models import ExportJob, Region
from app.schemas import AnimationRequest, CSVExportRequest, ExportRequest, ExportResponse
from app.settings import get_settings


router = APIRouter()
logger = logging.getLogger(__name__)

WEB_MERCATOR_MAX_LAT = 85.05112878
BASEMAP_TILE_URL = "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
TILE_SIZE = 256

PDF_METRIC_COLORS: dict[str, str] = {
    "ndvi": "#059669",
    "nightlights": "#D97706",
    "surface_water": "#2563EB",
    "no2": "#6366F1",
    "temperature": "#EF4444",
    "precipitation": "#3B82F6",
    "aerosol": "#92400E",
    "cropland": "#16A34A",
    "evapotranspiration": "#0D9488",
    "soil_moisture": "#7C3AED",
    "impervious": "#6B7280",
    "canopy_height": "#15803D",
    "forest_loss_year": "#92400E",
    "snow_cover": "#60A5FA",
    "travel_time_to_cities": "#9333EA",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_to_response(job: ExportJob) -> ExportResponse:
    return ExportResponse(
        id=job.id,
        status=job.status,  # type: ignore[arg-type]
        format=job.format,
        progress=job.progress,
        message=job.message,
        download_url=f"/api/v1/exports/download/{job.id}" if job.status == "completed" else None,
        file_size=job.file_size,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
    )


async def _update_job(db: AsyncSession, job_id: str, **updates) -> None:
    result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        logger.warning("Export job %s not found while attempting update: %s", job_id, sorted(updates.keys()))
        return
    for k, v in updates.items():
        setattr(job, k, v)


def _truncate_error(error: str, max_chars: int = 4000) -> str:
    if len(error) <= max_chars:
        return error
    return f"{error[: max_chars - 3]}..."


async def _mark_job_failed(job_id: str, db_url: str, error_message: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            await _update_job(
                db,
                job_id,
                status="failed",
                message="Failed",
                error=_truncate_error(error_message),
                completed_at=_now(),
            )
            await db.commit()
    finally:
        await engine.dispose()


async def _run_export_task(
    job_id: str,
    db_url: str,
    task_fn: Callable[..., Awaitable[None]],
    *task_args: object,
) -> None:
    try:
        await task_fn(job_id, *task_args, db_url)  # type: ignore[misc]
    except Exception as exc:
        logger.exception("Export job %s failed", job_id)
        await _mark_job_failed(job_id, db_url, str(exc))


def _clamp_lat(lat: float) -> float:
    return max(-WEB_MERCATOR_MAX_LAT, min(WEB_MERCATOR_MAX_LAT, lat))


def _iter_lon_lat_pairs(geometry: dict) -> list[tuple[float, float]]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    points: list[tuple[float, float]] = []

    if geom_type == "Polygon":
        for ring in coords or []:
            for pair in ring:
                if len(pair) >= 2:
                    points.append((float(pair[0]), float(pair[1])))
        return points

    if geom_type == "MultiPolygon":
        for polygon in coords or []:
            for ring in polygon:
                for pair in ring:
                    if len(pair) >= 2:
                        points.append((float(pair[0]), float(pair[1])))
        return points

    raise ValueError(f"Unsupported geometry type for animation export: {geom_type}")


def _extract_bounds(geometry: dict) -> tuple[float, float, float, float]:
    points = _iter_lon_lat_pairs(geometry)
    if not points:
        raise ValueError("Region geometry has no coordinates")

    lons = [max(-179.999, min(179.999, lon)) for lon, _ in points]
    lats = [_clamp_lat(lat) for _, lat in points]

    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    # Avoid zero-sized bounds.
    if abs(max_lon - min_lon) < 1e-6:
        min_lon = max(-179.999, min_lon - 0.01)
        max_lon = min(179.999, max_lon + 0.01)
    if abs(max_lat - min_lat) < 1e-6:
        min_lat = _clamp_lat(min_lat - 0.01)
        max_lat = _clamp_lat(max_lat + 0.01)

    return (min_lon, min_lat, max_lon, max_lat)


def _lon_to_tile_x(lon: float, zoom: int) -> float:
    n = 2**zoom
    return (lon + 180.0) / 360.0 * n


def _lat_to_tile_y(lat: float, zoom: int) -> float:
    lat = _clamp_lat(lat)
    rad = math.radians(lat)
    n = 2**zoom
    return (1.0 - (math.log(math.tan(rad) + (1.0 / math.cos(rad))) / math.pi)) / 2.0 * n


def _choose_basemap_zoom(
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
    max_tiles: int = 64,
) -> int:
    min_lon, min_lat, max_lon, max_lat = bounds
    best = 3

    for zoom in range(18, 0, -1):
        x0 = _lon_to_tile_x(min_lon, zoom)
        x1 = _lon_to_tile_x(max_lon, zoom)
        y0 = _lat_to_tile_y(max_lat, zoom)
        y1 = _lat_to_tile_y(min_lat, zoom)

        x_min = int(math.floor(x0))
        x_max = int(math.floor(x1))
        y_min = int(math.floor(y0))
        y_max = int(math.floor(y1))

        tile_count = max(1, (x_max - x_min + 1) * (y_max - y_min + 1))
        span_x = max(1.0, (x1 - x0) * TILE_SIZE)
        span_y = max(1.0, (y1 - y0) * TILE_SIZE)

        if tile_count <= max_tiles:
            best = zoom
        if tile_count <= max_tiles and span_x >= width and span_y >= height:
            return zoom

    return best


async def _render_basemap_rgb(
    client: httpx.AsyncClient,
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
) -> np.ndarray:
    min_lon, min_lat, max_lon, max_lat = bounds
    zoom = _choose_basemap_zoom(bounds, width, height)

    x0 = _lon_to_tile_x(min_lon, zoom)
    x1 = _lon_to_tile_x(max_lon, zoom)
    y0 = _lat_to_tile_y(max_lat, zoom)
    y1 = _lat_to_tile_y(min_lat, zoom)

    x_min = int(math.floor(x0))
    x_max = int(math.floor(x1))
    y_min = int(math.floor(y0))
    y_max = int(math.floor(y1))

    canvas_w = max(1, (x_max - x_min + 1) * TILE_SIZE)
    canvas_h = max(1, (y_max - y_min + 1) * TILE_SIZE)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (233, 237, 241))

    semaphore = asyncio.Semaphore(12)

    async def fetch_tile(x: int, y: int) -> tuple[int, int, bytes | None]:
        url = BASEMAP_TILE_URL.format(z=zoom, x=x, y=y)
        async with semaphore:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return x, y, response.content
            except Exception:
                logger.warning("Basemap tile download failed for z=%s x=%s y=%s", zoom, x, y)
                return x, y, None

    tasks = [fetch_tile(x, y) for y in range(y_min, y_max + 1) for x in range(x_min, x_max + 1)]
    for x, y, content in await asyncio.gather(*tasks):
        if not content:
            continue
        try:
            tile = Image.open(io.BytesIO(content)).convert("RGB")
            canvas.paste(tile, ((x - x_min) * TILE_SIZE, (y - y_min) * TILE_SIZE))
        except Exception:
            logger.warning("Basemap tile decode failed for z=%s x=%s y=%s", zoom, x, y)

    left = int(max(0, min(canvas_w - 1, math.floor((x0 - x_min) * TILE_SIZE))))
    upper = int(max(0, min(canvas_h - 1, math.floor((y0 - y_min) * TILE_SIZE))))
    right = int(max(left + 1, min(canvas_w, math.ceil((x1 - x_min) * TILE_SIZE))))
    lower = int(max(upper + 1, min(canvas_h, math.ceil((y1 - y_min) * TILE_SIZE))))

    cropped = canvas.crop((left, upper, right, lower))
    if cropped.size != (width, height):
        cropped = cropped.resize((width, height), Image.Resampling.LANCZOS)

    return np.asarray(cropped, dtype=np.uint8)


def _composite_overlay_on_basemap(
    basemap_rgba: Image.Image,
    overlay_png_bytes: bytes,
    overlay_opacity: float,
) -> np.ndarray:
    overlay = Image.open(io.BytesIO(overlay_png_bytes)).convert("RGBA")
    if overlay.size != basemap_rgba.size:
        overlay = overlay.resize(basemap_rgba.size, Image.Resampling.BILINEAR)

    overlay_arr = np.asarray(overlay, dtype=np.uint8).copy()
    alpha = overlay_arr[:, :, 3].astype(np.float32)
    overlay_arr[:, :, 3] = np.clip(alpha * overlay_opacity, 0, 255).astype(np.uint8)

    composed = Image.alpha_composite(basemap_rgba.copy(), Image.fromarray(overlay_arr, mode="RGBA")).convert("RGB")
    return np.asarray(composed, dtype=np.uint8)


def _short_label(text: str, max_len: int = 14) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return f"{text[: max_len - 3]}..."


def _bucket_month(bucket: str) -> int | None:
    # Expected forms: YYYY-MM or YYYY-MM-DD
    try:
        return int(bucket[5:7])
    except Exception:
        return None


def _normalize_percent(value: float, vmin: float, vmax: float) -> float:
    span = vmax - vmin
    if span <= 0:
        return 0.0
    return max(0.0, min(100.0, ((value - vmin) / span) * 100.0))


def _build_pdf_time_series_chart(
    series_by_metric: dict[str, list[tuple[str, float]]],
    metric_order: list[str],
    available_width: float,
) -> Drawing | None:
    all_buckets = sorted({bucket for series in series_by_metric.values() for bucket, _ in series})
    if not all_buckets:
        return None

    # Keep chart readable for long windows.
    if len(all_buckets) > 36:
        all_buckets = all_buckets[-36:]

    rows: list[list[float | None]] = []
    row_metrics: list[str] = []

    for metric in metric_order:
        points = series_by_metric.get(metric) or []
        if not points:
            continue
        by_bucket = {bucket: value for bucket, value in points}
        row_raw = [by_bucket.get(bucket) for bucket in all_buckets]
        non_null = [v for v in row_raw if v is not None]
        if not non_null:
            continue

        row_min = min(non_null)
        row_max = max(non_null)
        if abs(row_max - row_min) < 1e-9:
            # Keep constant series visible as a flat midline.
            row_normalized = [50.0 if v is not None else None for v in row_raw]
        else:
            row_normalized = [
                _normalize_percent(float(v), row_min, row_max) if v is not None else None for v in row_raw
            ]

        rows.append(row_normalized)
        row_metrics.append(metric)

    if not rows:
        return None

    chart_width = max(340.0, min(available_width, 500.0))
    legend_col_width = (chart_width - 88) / 2
    legend_row_h = 12
    legend_items = min(len(row_metrics), 10)
    legend_rows = max(1, math.ceil(legend_items / 2))

    line = HorizontalLineChart()
    line.x = 38
    line.y = 64
    line.width = chart_width - 72
    line.height = 140

    chart_top = line.y + line.height
    legend_bottom_y = chart_top + 8
    legend_start_y = legend_bottom_y + (legend_rows - 1) * legend_row_h
    subtitle_y = legend_start_y + 18
    title_y = subtitle_y + 13
    drawing_height = title_y + 14
    drawing = Drawing(chart_width, drawing_height)
    drawing.add(
        String(
            chart_width / 2,
            title_y,
            "Time Series by Metric",
            fontName="Helvetica-Bold",
            fontSize=11,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            chart_width / 2,
            subtitle_y,
            "Each metric scaled to its own observed range (0-100%)",
            fontName="Helvetica",
            fontSize=7,
            textAnchor="middle",
            fillColor=colors.HexColor("#6b7280"),
        )
    )

    line.data = rows
    line.categoryAxis.categoryNames = all_buckets
    line.categoryAxis.labels.angle = 35
    line.categoryAxis.labels.dy = -16
    line.categoryAxis.labels.fontName = "Helvetica"
    line.categoryAxis.labels.fontSize = 6 if len(all_buckets) > 24 else 7
    line.categoryAxis.strokeColor = colors.HexColor("#9ca3af")
    line.valueAxis.strokeColor = colors.HexColor("#9ca3af")
    line.valueAxis.labels.fontName = "Helvetica"
    line.valueAxis.labels.fontSize = 7
    line.valueAxis.gridStrokeColor = colors.HexColor("#e5e7eb")
    line.valueAxis.gridStrokeWidth = 0.3
    line.valueAxis.valueMin = 0
    line.valueAxis.valueMax = 100
    line.valueAxis.valueStep = 20

    for idx, metric in enumerate(row_metrics):
        metric_color = colors.HexColor(PDF_METRIC_COLORS.get(metric, "#2563eb"))
        line.lines[idx].strokeColor = metric_color
        line.lines[idx].strokeWidth = 1.5
        line.lines[idx].symbol = None

    drawing.add(line)

    legend_start_x = 44
    for idx, metric in enumerate(row_metrics[:10]):
        col = idx % 2
        row = idx // 2
        x = legend_start_x + col * legend_col_width
        y = legend_start_y - row * legend_row_h
        metric_color = colors.HexColor(PDF_METRIC_COLORS.get(metric, "#2563eb"))
        drawing.add(Rect(x, y, 9, 4, fillColor=metric_color, strokeColor=metric_color))
        drawing.add(
            String(
                x + 13,
                y - 1,
                _short_label(METRICS[metric].label, 24),
                fontName="Helvetica",
                fontSize=7,
                fillColor=colors.HexColor("#374151"),
            )
        )

    if len(row_metrics) > 10:
        drawing.add(
            String(
                chart_width - 42,
                legend_start_y + 8,
                f"+{len(row_metrics) - 10} more",
                fontName="Helvetica",
                fontSize=7,
                textAnchor="end",
                fillColor=colors.HexColor("#6b7280"),
            )
        )

    return drawing


def _build_pdf_seasonal_chart(
    series_by_metric: dict[str, list[tuple[str, float]]],
    metric_order: list[str],
    available_width: float,
) -> Drawing | None:
    winter_months = {12, 1, 2}
    summer_months = {6, 7, 8}
    seasonal_rows: list[tuple[str, float, float]] = []

    for metric in metric_order:
        series = series_by_metric.get(metric) or []
        if not series:
            continue

        winter_values: list[float] = []
        summer_values: list[float] = []
        for bucket, value in series:
            month = _bucket_month(bucket)
            if month is None:
                continue
            if month in winter_months:
                winter_values.append(value)
            elif month in summer_months:
                summer_values.append(value)

        if not winter_values or not summer_values:
            continue

        winter_avg = sum(winter_values) / len(winter_values)
        summer_avg = sum(summer_values) / len(summer_values)
        vmin, vmax = METRICS[metric].value_range
        winter_pct = _normalize_percent(winter_avg, vmin, vmax)
        summer_pct = _normalize_percent(summer_avg, vmin, vmax)
        seasonal_rows.append((metric, winter_pct, summer_pct))

    if not seasonal_rows:
        return None

    # Keep labels readable.
    if len(seasonal_rows) > 8:
        seasonal_rows = seasonal_rows[:8]

    chart_width = max(340.0, min(available_width, 500.0))
    drawing = Drawing(chart_width, 255)
    drawing.add(
        String(
            chart_width / 2,
            238,
            "Seasonal Comparison (Winter vs Summer)",
            fontName="Helvetica-Bold",
            fontSize=11,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            chart_width / 2,
            225,
            "Values normalized to each metric's configured range (0-100%)",
            fontName="Helvetica",
            fontSize=7,
            textAnchor="middle",
            fillColor=colors.HexColor("#6b7280"),
        )
    )

    bar = VerticalBarChart()
    bar.x = 38
    bar.y = 60
    bar.width = chart_width - 72
    bar.height = 145
    bar.data = [
        [row[1] for row in seasonal_rows],  # winter
        [row[2] for row in seasonal_rows],  # summer
    ]
    bar.categoryAxis.categoryNames = [_short_label(METRICS[row[0]].label, 16) for row in seasonal_rows]
    bar.categoryAxis.labels.angle = 30
    bar.categoryAxis.labels.dy = -14
    bar.categoryAxis.labels.fontName = "Helvetica"
    bar.categoryAxis.labels.fontSize = 7
    bar.categoryAxis.strokeColor = colors.HexColor("#9ca3af")
    bar.valueAxis.strokeColor = colors.HexColor("#9ca3af")
    bar.valueAxis.labels.fontName = "Helvetica"
    bar.valueAxis.labels.fontSize = 7
    bar.valueAxis.gridStrokeColor = colors.HexColor("#e5e7eb")
    bar.valueAxis.gridStrokeWidth = 0.3
    bar.valueAxis.valueMin = 0
    bar.valueAxis.valueMax = 100
    bar.valueAxis.valueStep = 20
    bar.groupSpacing = 8
    bar.barSpacing = 1.5
    bar.bars[0].fillColor = colors.HexColor("#0D9488")  # Winter
    bar.bars[1].fillColor = colors.HexColor("#D97706")  # Summer

    drawing.add(bar)

    legend_y = 210
    drawing.add(Rect(46, legend_y, 10, 5, fillColor=colors.HexColor("#0D9488"), strokeColor=colors.HexColor("#0D9488")))
    drawing.add(String(60, legend_y - 1, "Winter (Dec-Feb)", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#374151")))
    drawing.add(Rect(154, legend_y, 10, 5, fillColor=colors.HexColor("#D97706"), strokeColor=colors.HexColor("#D97706")))
    drawing.add(String(168, legend_y - 1, "Summer (Jun-Aug)", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#374151")))

    return drawing


async def _generate_csv(job_id: str, request: CSVExportRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            await _update_job(db, job_id, status="processing", progress=5.0, message="Generating CSV")
            await db.commit()

            region_ids = request.region_ids or []
            if not region_ids:
                # Default: all regions.
                regions = (await db.execute(select(Region.id))).scalars().all()
                region_ids = list(regions)

            metrics = request.metrics or list(METRICS.keys())
            start_date = request.start_date
            end_date = request.end_date
            if start_date is None or end_date is None:
                raise ValueError("start_date and end_date are required")

            rows: list[list[str]] = []
            header = ["date", "region", "metric", "value"]
            if request.include_metadata:
                header.append("unit")
            rows.append(header)

            for region_id in region_ids:
                region = (await db.execute(select(Region).where(Region.id == region_id))).scalar_one_or_none()
                if region is None:
                    continue
                geometry = json.loads(region.geometry)
                for metric in metrics:
                    # Monthly CSV for exports (keeps file size manageable)
                    from app.gee import compute_time_series

                    series = await gee_to_thread(
                        compute_time_series,
                        geometry_geojson=geometry,
                        metric=metric,
                        start_date=start_date,
                        end_date=end_date,
                        granularity="monthly",
                    )
                    unit = METRICS[metric].unit
                    for d, v in series:
                        row = [d, region.name, metric, f"{v:.6f}"]
                        if request.include_metadata:
                            row.append(unit)
                        rows.append(row)

            output = Path(settings.exports_path) / f"{job_id}.csv"
            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

            await _update_job(
                db,
                job_id,
                status="completed",
                progress=100.0,
                message="Completed",
                output_path=str(output),
                file_size=output.stat().st_size,
                completed_at=_now(),
            )
            await db.commit()
    finally:
        await engine.dispose()


async def _generate_pdf(job_id: str, request: ExportRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            await _update_job(db, job_id, status="processing", progress=5.0, message="Generating PDF")
            await db.commit()

            region = (await db.execute(select(Region).where(Region.id == request.region_id))).scalar_one_or_none()
            if region is None:
                raise ValueError("Region not found")

            start_date = request.start_date
            end_date = request.end_date
            if start_date is None or end_date is None:
                raise ValueError("start_date and end_date are required")

            metrics = request.metrics or list(METRICS.keys())
            geometry = json.loads(region.geometry)

            # Compute monthly time series per metric and summarize with mean/min/max.
            from app.gee import compute_time_series

            summary_rows: list[list[str]] = [["Metric", "Unit", "Mean", "Min", "Max", "Points"]]
            series_by_metric: dict[str, list[tuple[str, float]]] = {}
            total_metrics = max(1, len(metrics))
            for index, metric in enumerate(metrics, start=1):
                await _update_job(
                    db,
                    job_id,
                    progress=5.0 + ((index - 1) / total_metrics) * 80.0,
                    message=f"Computing {index}/{total_metrics}: {METRICS[metric].label}",
                )
                await db.commit()

                series = await gee_to_thread(
                    compute_time_series,
                    geometry_geojson=geometry,
                    metric=metric,
                    start_date=start_date,
                    end_date=end_date,
                    granularity="monthly",
                )
                series_by_metric[metric] = series
                values = [v for _, v in series]
                if not values:
                    continue
                mean_v = sum(values) / len(values)
                summary_rows.append(
                    [
                        METRICS[metric].label,
                        METRICS[metric].unit,
                        f"{mean_v:.4f}",
                        f"{min(values):.4f}",
                        f"{max(values):.4f}",
                        str(len(values)),
                    ]
                )

                await _update_job(
                    db,
                    job_id,
                    progress=5.0 + (index / total_metrics) * 80.0,
                    message=f"Computed {index}/{total_metrics}: {METRICS[metric].label}",
                )
                await db.commit()

            await _update_job(db, job_id, progress=90.0, message="Building PDF file")
            await db.commit()

            output = Path(settings.exports_path) / f"{job_id}.pdf"
            doc = SimpleDocTemplate(str(output), pagesize=letter)
            styles = getSampleStyleSheet()

            story = []
            story.append(Paragraph(request.title or f"Report: {region.name}", styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Period: {start_date} to {end_date}", styles["Normal"]))
            story.append(Spacer(1, 12))
            if request.description:
                story.append(Paragraph(request.description, styles["BodyText"]))
                story.append(Spacer(1, 12))

            story.append(Paragraph("Metric Summary", styles["Heading2"]))
            story.append(Spacer(1, 6))
            table = Table(summary_rows, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ]
                )
            )
            story.append(table)

            if request.include_charts:
                line_chart = _build_pdf_time_series_chart(series_by_metric, metrics, doc.width)
                if line_chart is not None:
                    story.append(Spacer(1, 16))
                    story.append(line_chart)

                seasonal_chart = _build_pdf_seasonal_chart(series_by_metric, metrics, doc.width)
                if seasonal_chart is not None:
                    story.append(Spacer(1, 12))
                    story.append(seasonal_chart)

            doc.build(story)

            await _update_job(
                db,
                job_id,
                status="completed",
                progress=100.0,
                message="Completed",
                output_path=str(output),
                file_size=output.stat().st_size,
                completed_at=_now(),
            )
            await db.commit()
    finally:
        await engine.dispose()


async def _generate_animation(job_id: str, request: AnimationRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            await _update_job(db, job_id, status="processing", progress=0.0, message="Rendering frames")
            await db.commit()

            region = (await db.execute(select(Region).where(Region.id == request.region_id))).scalar_one_or_none()
            if region is None:
                raise ValueError("Region not found")

            geometry = json.loads(region.geometry)
            metric_def = METRICS[request.metric]

            initialize_ee()
            import ee

            geom = geojson_to_ee_geometry(geometry)

            # Choose monthly frames by default; daily if <= 90 days and supported.
            days = (request.end_date - request.start_date).days
            frame_granularity: str = "monthly"
            if days <= 90 and "daily" in metric_def.supported_granularities:
                frame_granularity = "daily"

            starts = bucket_starts(request.start_date, request.end_date, frame_granularity)  # type: ignore[arg-type]
            total = max(1, len(starts))

            bounds = _extract_bounds(geometry)
            overlay_opacity = float(request.overlay_opacity)

            frames = []
            async with httpx.AsyncClient(
                timeout=60.0,
                headers={"User-Agent": "satellite-data-exporter/1.0"},
            ) as client:
                await _update_job(db, job_id, progress=2.0, message="Loading basemap")
                await db.commit()
                basemap_rgb = await _render_basemap_rgb(client, bounds, request.width, request.height)
                basemap_rgba = Image.fromarray(basemap_rgb, mode="RGB").convert("RGBA")

                for i, d0 in enumerate(starts):
                    d1 = bucket_end(d0, frame_granularity)  # type: ignore[arg-type]
                    ee_start = ee.Date(d0.isoformat())
                    ee_end = ee.Date(d1.isoformat())

                    img = build_metric_image(request.metric, ee_start, ee_end, geom)
                    vmin, vmax = metric_def.value_range
                    overlay_img = img.visualize(min=vmin, max=vmax, palette=metric_def.palette).updateMask(img.mask())
                    thumb = await gee_to_thread(
                        overlay_img.getThumbURL,
                        {
                            "region": geom,
                            "dimensions": [request.width, request.height],
                            "format": "png",
                        },
                    )
                    resp = await client.get(thumb)
                    resp.raise_for_status()
                    if request.include_basemap:
                        frames.append(_composite_overlay_on_basemap(basemap_rgba, resp.content, overlay_opacity))
                    else:
                        overlay_frame = imageio.imread(resp.content)
                        if overlay_frame.ndim == 3 and overlay_frame.shape[-1] == 4:
                            overlay_frame = overlay_frame[:, :, :3]
                        frames.append(overlay_frame)

                    progress = ((i + 1) / total) * 95.0
                    await _update_job(db, job_id, progress=progress, message=f"Rendered {i + 1}/{total} frames")
                    await db.commit()

            output = Path(settings.exports_path) / f"{job_id}.gif"
            imageio.mimsave(output, frames, duration=request.frame_duration_ms / 1000.0)

            await _update_job(
                db,
                job_id,
                status="completed",
                progress=100.0,
                message="Completed",
                output_path=str(output),
                file_size=output.stat().st_size,
                completed_at=_now(),
            )
            await db.commit()
    finally:
        await engine.dispose()


@router.post("/pdf", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_pdf(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="pdf",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()
    await db.commit()

    from app.settings import get_settings

    settings = get_settings()
    background_tasks.add_task(_run_export_task, job.id, settings.database_url, _generate_pdf, request)
    return _job_to_response(job)


@router.post("/csv", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_csv(
    request: CSVExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="csv",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()
    await db.commit()

    settings = get_settings()
    background_tasks.add_task(_run_export_task, job.id, settings.database_url, _generate_csv, request)
    return _job_to_response(job)


@router.post("/animation", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_animation(
    request: AnimationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="gif",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()
    await db.commit()

    settings = get_settings()
    background_tasks.add_task(_run_export_task, job.id, settings.database_url, _generate_animation, request)
    return _job_to_response(job)


@router.get("/{export_id}/status", response_model=ExportResponse)
async def get_export_status(export_id: str, db: AsyncSession = Depends(get_db)) -> ExportResponse:
    job = (await db.execute(select(ExportJob).where(ExportJob.id == export_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return _job_to_response(job)


@router.get("/download/{export_id}")
async def download_export(export_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    job = (await db.execute(select(ExportJob).where(ExportJob.id == export_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    if job.status != "completed" or not job.output_path:
        raise HTTPException(status_code=400, detail="Export not ready")

    output_path = Path(job.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Export file missing")

    media = "application/octet-stream"
    if output_path.suffix == ".pdf":
        media = "application/pdf"
    elif output_path.suffix == ".csv":
        media = "text/csv"
    elif output_path.suffix == ".gif":
        media = "image/gif"

    return FileResponse(path=str(output_path), filename=output_path.name, media_type=media)
