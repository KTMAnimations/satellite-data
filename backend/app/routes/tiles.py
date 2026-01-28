from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.gee import METRICS, get_tile_template
from app.schemas import MetricId, TileTemplateResponse


router = APIRouter()


@router.get("/template", response_model=TileTemplateResponse)
async def tile_template(
    metric: MetricId = Query(...),
    date_bucket: str = Query(..., description="YYYY-MM (monthly) or YYYY-MM-DD (daily/weekly)"),
    granularity: str = Query("monthly", description="daily|weekly|monthly"),
    opacity: float | None = Query(None, ge=0.0, le=1.0),
) -> TileTemplateResponse:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail="Invalid metric")
    if granularity not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="Invalid granularity")

    try:
        payload = await asyncio.to_thread(
            get_tile_template,
            metric,
            date_bucket,
            granularity,  # type: ignore[arg-type]
            opacity=opacity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Failed to fetch tile template from Earth Engine. "
                "Verify credentials (run `earthengine authenticate` or configure GEE_* env vars) "
                f"and try again. Error: {e}"
            ),
        ) from e
    return TileTemplateResponse(**payload)
