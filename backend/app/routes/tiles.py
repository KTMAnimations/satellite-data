from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Response

from app.gee import METRICS, get_tile_fetcher, get_tile_template
from app.schemas import MetricId, TileTemplateResponse


router = APIRouter()

def _wrap_x(x: int, z: int) -> int:
    """
    Leaflet can request tiles outside the global x-range when world-wrapping.
    Earth Engine expects x within [0, 2^z - 1], so wrap it.
    """
    world = 1 << z
    return x % world


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


@router.get("/{metric}/{granularity}/{date_bucket}/{z}/{x}/{y}.png")
async def tile_png(
    metric: MetricId,
    granularity: str,
    date_bucket: str,
    z: int,
    x: int,
    y: int,
) -> Response:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail="Invalid metric")
    if granularity not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="Invalid granularity")
    if z < 0:
        raise HTTPException(status_code=400, detail="Invalid zoom")

    world = 1 << z
    if y < 0 or y >= world:
        # Leaflet doesn't wrap y; out-of-range tiles are empty.
        raise HTTPException(status_code=404, detail="Tile out of range")

    x = _wrap_x(x, z)

    try:
        fetcher = await asyncio.to_thread(get_tile_fetcher, metric, date_bucket, granularity)  # type: ignore[arg-type]
        png_bytes: bytes = await asyncio.to_thread(fetcher.fetch_tile, x, y, z)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Failed to fetch tile from Earth Engine. "
                "Verify credentials (run `earthengine authenticate` or configure GEE_* env vars) "
                f"and try again. Error: {e}"
            ),
        ) from e

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
