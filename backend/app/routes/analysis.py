from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee import METRICS, build_metric_image, geojson_to_ee_geometry, initialize_ee
from app.models import Region
from app.schemas import CompareRequest, CompareResponse, PeriodSummary


router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
async def compare_periods(request: CompareRequest, db: AsyncSession = Depends(get_db)) -> CompareResponse:
    result = await db.execute(select(Region).where(Region.id == request.region_id))
    region = result.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    try:
        geometry = json.loads(region.geometry)
    except Exception:
        raise HTTPException(status_code=500, detail="Region geometry invalid")

    metrics = request.metrics or list(METRICS.keys())

    initialize_ee()
    import ee

    geom = geojson_to_ee_geometry(geometry)
    reducer = ee.Reducer.mean()

    semaphore = asyncio.Semaphore(4)

    def _metric_average(metric: str, start_date, end_date) -> tuple[str, float] | None:
        start = ee.Date(start_date.isoformat())
        end = ee.Date((end_date + timedelta(days=1)).isoformat())
        metric_def = METRICS[metric]  # type: ignore[index]
        img = build_metric_image(metric, start, end, geom)
        reduced = img.reduceRegion(
            reducer=reducer,
            geometry=geom,
            scale=metric_def.scale_m,
            maxPixels=1e13,
            bestEffort=True,
        )
        v = reduced.get(metric).getInfo()
        if v is None:
            return None
        try:
            return metric, float(v)
        except Exception:
            return None

    async def period_averages(start_date, end_date) -> dict[str, float]:
        async def compute_one(metric: str) -> tuple[str, float] | None:
            async with semaphore:
                return await asyncio.to_thread(_metric_average, metric, start_date, end_date)

        results = await asyncio.gather(*(compute_one(m) for m in metrics))
        return {k: v for item in results if item is not None for k, v in [item]}

    period_a_avgs = await period_averages(request.period_a_start, request.period_a_end)
    period_b_avgs = await period_averages(request.period_b_start, request.period_b_end)

    change: dict[str, float] = {}
    change_abs: dict[str, float] = {}
    for metric in metrics:
        a = period_a_avgs.get(metric)
        b = period_b_avgs.get(metric)
        if a is None or b is None:
            continue
        change_abs[metric] = b - a
        change[metric] = ((b - a) / a * 100.0) if a != 0 else 0.0

    return CompareResponse(
        region_id=region.id,
        region_name=region.name,
        period_a=PeriodSummary(
            start_date=request.period_a_start,
            end_date=request.period_a_end,
            averages=period_a_avgs,
            observation_count=sum(1 for _ in period_a_avgs),
        ),
        period_b=PeriodSummary(
            start_date=request.period_b_start,
            end_date=request.period_b_end,
            averages=period_b_avgs,
            observation_count=sum(1 for _ in period_b_avgs),
        ),
        change=change,
        change_absolute=change_abs,
    )
