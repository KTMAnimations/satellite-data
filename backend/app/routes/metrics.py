from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee import METRICS, bucket_starts, compute_time_series, format_bucket_date
from app.models import MetricObservation, Region
from app.schemas import MetricData, MetricDataPoint, MetricsResponse, MetricId, SeasonalAverage, SeasonalSummary


router = APIRouter()

# Used to invalidate cached metric observations in SQLite when computation logic changes.
# Bump this when making non-backwards-compatible changes to `compute_time_series` inputs
# or any metric implementation in `app/gee.py`.
METRICS_CACHE_SOURCE = "earth_engine:v4"


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
    metrics_brackets: list[MetricId] | None = Query(None, alias="metrics[]"),
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

    requested = metrics or metrics_brackets or list(METRICS.keys())
    out: dict[str, MetricData] = {}

    # Cache-aware: first check SQLite for already-collected observations. If any
    # buckets are missing, compute from Earth Engine and persist back to SQLite.
    semaphore = asyncio.Semaphore(4)

    per_metric: dict[MetricId, dict] = {}
    for metric in requested:
        metric_def = METRICS[metric]
        effective_granularity = (
            granularity if granularity in metric_def.supported_granularities else metric_def.default_granularity
        )

        starts = bucket_starts(start_date, end_date, effective_granularity)
        buckets = [format_bucket_date(d, effective_granularity) for d in starts]
        if not buckets:
            per_metric[metric] = {
                "metric_def": metric_def,
                "granularity": effective_granularity,
                "buckets": [],
                "existing": {},
                "needs_compute": False,
            }
            continue

        q = (
            select(MetricObservation)
            .where(MetricObservation.region_id == region.id)
            .where(MetricObservation.metric == metric)  # type: ignore[arg-type]
            .where(MetricObservation.granularity == effective_granularity)
            .where(MetricObservation.date_bucket >= buckets[0])
            .where(MetricObservation.date_bucket <= buckets[-1])
        )
        rows = (await db.execute(q)).scalars().all()
        existing = {r.date_bucket: r for r in rows}
        needs_compute = any((b not in existing) or (existing[b].source != METRICS_CACHE_SOURCE) for b in buckets)

        per_metric[metric] = {
            "metric_def": metric_def,
            "granularity": effective_granularity,
            "buckets": buckets,
            "existing": existing,
            "needs_compute": needs_compute,
        }

    async def compute_one(metric: MetricId) -> tuple[MetricId, list[tuple[str, float]]]:
        async with semaphore:
            try:
                series = await asyncio.to_thread(
                    compute_time_series,
                    geometry_geojson=geometry,
                    metric=metric,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=per_metric[metric]["granularity"],  # type: ignore[arg-type]
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Failed to fetch data from Earth Engine. "
                        "Verify credentials (run `earthengine authenticate` or configure GEE_* env vars) "
                        f"and try again. Error: {e}"
                    ),
                ) from e
            return metric, series

    to_compute = [m for m in requested if per_metric[m]["needs_compute"]]
    computed = await asyncio.gather(*(compute_one(m) for m in to_compute))
    computed_by_metric = {m: series for m, series in computed}

    # Persist computed series (and explicit "no data" buckets) to SQLite.
    computed_at = datetime.now(timezone.utc)
    for metric in to_compute:
        info = per_metric[metric]
        metric_def = info["metric_def"]
        buckets: list[str] = info["buckets"]
        existing: dict[str, MetricObservation] = info["existing"]
        series = computed_by_metric.get(metric, [])
        by_bucket = {d: v for d, v in series}

        for bucket in buckets:
            value = by_bucket.get(bucket)
            row = existing.get(bucket)
            if row is None:
                row = MetricObservation(
                    region_id=region.id,
                    metric=metric,
                    granularity=info["granularity"],
                    date_bucket=bucket,
                    value=value,
                    unit=metric_def.unit,
                    source=METRICS_CACHE_SOURCE,
                    computed_at=computed_at,
                )
                db.add(row)
                existing[bucket] = row
            else:
                row.value = value
                row.unit = metric_def.unit
                row.source = METRICS_CACHE_SOURCE
                row.computed_at = computed_at

        # Mark the dict back (mutated in place)
        info["existing"] = existing

    for metric in requested:
        info = per_metric[metric]
        metric_def = info["metric_def"]
        buckets: list[str] = info["buckets"]
        existing: dict[str, MetricObservation] = info["existing"]

        data_points: list[MetricDataPoint] = []
        for bucket in buckets:
            row = existing.get(bucket)
            if row is None or row.value is None:
                continue
            data_points.append(MetricDataPoint(date=bucket, value=float(row.value)))

        out[metric] = MetricData(unit=metric_def.unit, data=data_points)

    seasonal = _seasonal_summary(out)

    return MetricsResponse(
        region_id=region.id,
        region_name=region.name,
        metrics=out,
        seasonal_summary=seasonal,
    )
