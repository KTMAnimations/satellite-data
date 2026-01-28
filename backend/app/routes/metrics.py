from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee import METRICS, compute_time_series
from app.models import Region
from app.schemas import MetricData, MetricDataPoint, MetricsResponse, MetricId, SeasonalAverage, SeasonalSummary


router = APIRouter()


def _parse_month_from_bucket(bucket: str) -> int | None:
    try:
        if len(bucket) == 7:
            return int(bucket.split("-")[1])
        return date.fromisoformat(bucket).month
    except Exception:
        return None


def _seasonal_summary(metrics: dict[str, MetricData]) -> SeasonalSummary | None:
    winter_months = {12, 1, 2}
    summer_months = {6, 7, 8}

    winter: dict[str, list[float]] = {}
    summer: dict[str, list[float]] = {}

    for metric, series in metrics.items():
        for point in series.data:
            month = _parse_month_from_bucket(point.date)
            if month is None:
                continue
            if month in winter_months:
                winter.setdefault(metric, []).append(point.value)
            if month in summer_months:
                summer.setdefault(metric, []).append(point.value)

    def avg(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    winter_avg = {k: avg(v) for k, v in winter.items()}
    summer_avg = {k: avg(v) for k, v in summer.items()}

    # Require at least one metric present in both seasons.
    common = set(winter_avg.keys()) & set(summer_avg.keys())
    if not common:
        return None

    change_pct: dict[str, float | None] = {}
    for m in common:
        w = winter_avg.get(m)
        s = summer_avg.get(m)
        if w is None or s is None or w == 0:
            change_pct[m] = None
        else:
            change_pct[m] = ((s - w) / w) * 100.0

    return SeasonalSummary(
        winter_avg=SeasonalAverage(**{k: winter_avg.get(k) for k in SeasonalAverage.model_fields.keys()}),
        summer_avg=SeasonalAverage(**{k: summer_avg.get(k) for k in SeasonalAverage.model_fields.keys()}),
        change_pct=SeasonalAverage(**{k: change_pct.get(k) for k in SeasonalAverage.model_fields.keys()}),
    )


@router.get("/{region_id}", response_model=MetricsResponse)
async def get_region_metrics(
    region_id: str,
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    metrics: list[MetricId] | None = Query(None),
    granularity: str = Query("monthly"),
) -> MetricsResponse:
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="start_date and end_date are required")
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    if granularity not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="granularity must be daily|weekly|monthly")

    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    try:
        geometry = json.loads(region.geometry)
    except Exception:
        raise HTTPException(status_code=500, detail="Region geometry is invalid JSON")

    requested = metrics or list(METRICS.keys())
    out: dict[str, MetricData] = {}

    semaphore = asyncio.Semaphore(4)

    async def compute_one(metric: MetricId) -> tuple[MetricId, list[tuple[str, float]]]:
        async with semaphore:
            try:
                series = await asyncio.to_thread(
                    compute_time_series,
                    geometry_geojson=geometry,
                    metric=metric,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity,  # type: ignore[arg-type]
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            return metric, series

    results = await asyncio.gather(*(compute_one(m) for m in requested))
    for metric, series in results:
        out[metric] = MetricData(
            unit=METRICS[metric].unit,
            data=[MetricDataPoint(date=d, value=v) for d, v in series],
        )

    seasonal = _seasonal_summary(out)

    return MetricsResponse(
        region_id=region.id,
        region_name=region.name,
        metrics=out,
        seasonal_summary=seasonal,
    )
