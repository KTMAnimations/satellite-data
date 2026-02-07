from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response

from app.gee import METRICS, get_tile_fetcher, get_tile_template
from app.schemas import MetricId, TileTemplateResponse
from app.settings import get_settings


router = APIRouter()

def _wrap_x(x: int, z: int) -> int:
    """
    Leaflet can request tiles outside the global x-range when world-wrapping.
    Earth Engine expects x within [0, 2^z - 1], so wrap it.
    """
    world = 1 << z
    return x % world


def _tile_cache_key(metric: str, granularity: str, date_bucket: str, z: int, x: int, y: int) -> str:
    """Deterministic filename-safe cache key for a tile."""
    raw = f"{metric}/{granularity}/{date_bucket}/{z}/{x}/{y}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_cached_tile(cache_dir: Path, key: str) -> bytes | None:
    path = cache_dir / f"{key}.png"
    if path.exists():
        # Touch to update atime for LRU eviction
        path.touch()
        return path.read_bytes()
    return None


def _put_cached_tile(cache_dir: Path, key: str, data: bytes, max_mb: int) -> None:
    if max_mb <= 0:
        return
    path = cache_dir / f"{key}.png"
    path.write_bytes(data)
    # Simple size-based eviction: if cache exceeds max, remove oldest files
    _evict_if_needed(cache_dir, max_mb)


def _evict_if_needed(cache_dir: Path, max_mb: int) -> None:
    max_bytes = max_mb * 1024 * 1024
    files = sorted(cache_dir.glob("*.png"), key=lambda p: p.stat().st_atime)
    total = sum(f.stat().st_size for f in files)
    while total > max_bytes and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink(missing_ok=True)


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

    # Check disk cache first
    settings = get_settings()
    cache_dir = settings.tile_cache_path
    cache_key = _tile_cache_key(metric, granularity, date_bucket, z, x, y)

    cached = await asyncio.to_thread(_get_cached_tile, cache_dir, cache_key)
    if cached is not None:
        return Response(
            content=cached,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    try:
        fetcher = await asyncio.to_thread(get_tile_fetcher, metric, date_bucket, granularity)  # type: ignore[arg-type]
        png_bytes: bytes = await asyncio.to_thread(fetcher.fetch_tile, x, y, z)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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

    # Write to disk cache (fire-and-forget)
    await asyncio.to_thread(_put_cached_tile, cache_dir, cache_key, png_bytes, settings.tile_cache_max_mb)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
