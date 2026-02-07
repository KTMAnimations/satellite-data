from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from app.gee import METRICS, get_tile_fetcher, get_tile_template
from app.gee_concurrency import get_gee_semaphore
from app.schemas import MetricId, TileTemplateResponse
from app.settings import get_settings


router = APIRouter()


_gee_semaphore = get_gee_semaphore()


@dataclass(frozen=True, slots=True)
class _TileCacheStats:
    total_bytes: int


_tile_cache_lock = threading.Lock()
_tile_cache_stats: _TileCacheStats | None = None


def _tile_cache_path(cache_dir: Path, metric: str, key: str) -> Path:
    return cache_dir / f"{metric}--{key}.png"


def _legacy_tile_cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.png"


def _wrap_x(x: int, z: int) -> int:
    """
    Leaflet can request tiles outside the global x-range when world-wrapping.
    Earth Engine expects x within [0, 2^z - 1], so wrap it.
    """
    world = 1 << z
    return x % world


def _tile_cache_key(metric: str, granularity: str, date_bucket: str, z: int, x: int, y: int, *, version: str) -> str:
    """Deterministic filename-safe cache key for a tile."""
    raw = f"{metric}/{granularity}/{date_bucket}/{z}/{x}/{y}?v={version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_cached_tile(cache_dir: Path, metric: str, key: str) -> bytes | None:
    path = _tile_cache_path(cache_dir, metric, key)
    legacy_path = _legacy_tile_cache_path(cache_dir, key)
    using_legacy = False

    if not path.exists():
        if legacy_path.exists():
            path = legacy_path
            using_legacy = True
        else:
            return None

    try:
        data = path.read_bytes()
    except Exception:
        return None

    # Opportunistically migrate legacy cache files so metric-specific clears work.
    if using_legacy:
        metric_path = _tile_cache_path(cache_dir, metric, key)
        try:
            if not metric_path.exists():
                os.replace(path, metric_path)
                path = metric_path
            else:
                path.unlink(missing_ok=True)
                path = metric_path
        except Exception:
            pass

    try:
        # Touch to update atime for LRU eviction.
        path.touch()
    except Exception:
        pass
    return data


def _init_tile_cache_stats(cache_dir: Path) -> _TileCacheStats:
    total = 0
    for p in cache_dir.glob("*.png"):
        try:
            total += p.stat().st_size
        except FileNotFoundError:
            continue
    return _TileCacheStats(total_bytes=total)


def _put_cached_tile(cache_dir: Path, metric: str, key: str, data: bytes, max_mb: int) -> None:
    """
    Persist a tile to disk and enforce a best-effort size cap.

    Uses atomic replace to avoid serving partial/corrupted PNGs under concurrency.
    """
    if max_mb <= 0:
        return

    max_bytes = max_mb * 1024 * 1024
    path = _tile_cache_path(cache_dir, metric, key)
    legacy_path = _legacy_tile_cache_path(cache_dir, key)
    tmp = cache_dir / f"{metric}--{key}.{uuid4().hex}.tmp"

    with _tile_cache_lock:
        global _tile_cache_stats
        stats = _tile_cache_stats
        if stats is None:
            stats = _tile_cache_stats = _init_tile_cache_stats(cache_dir)

        try:
            old_size = path.stat().st_size
        except FileNotFoundError:
            old_size = 0

        try:
            tmp.write_bytes(data)
            new_size = tmp.stat().st_size
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

        removed_legacy_size = 0
        if legacy_path != path and legacy_path.exists():
            try:
                removed_legacy_size = legacy_path.stat().st_size
            except FileNotFoundError:
                removed_legacy_size = 0
            try:
                legacy_path.unlink()
            except FileNotFoundError:
                removed_legacy_size = 0

        _tile_cache_stats = _TileCacheStats(
            total_bytes=stats.total_bytes + (new_size - old_size - removed_legacy_size)
        )
        _evict_if_needed(cache_dir, max_bytes)


def _evict_if_needed(cache_dir: Path, max_bytes: int) -> None:
    global _tile_cache_stats
    stats = _tile_cache_stats
    if stats is None:
        stats = _tile_cache_stats = _init_tile_cache_stats(cache_dir)

    if stats.total_bytes <= max_bytes:
        return

    files: list[tuple[float, int, Path]] = []
    for p in cache_dir.glob("*.png"):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        files.append((st.st_atime, st.st_size, p))
    files.sort(key=lambda t: t[0])

    total = stats.total_bytes
    for _, size, p in files:
        if total <= max_bytes:
            break
        try:
            p.unlink()
        except FileNotFoundError:
            continue
        total -= size

    _tile_cache_stats = _TileCacheStats(total_bytes=max(0, total))


def _clear_metric_cached_tiles(cache_dir: Path, metric: str) -> tuple[int, int]:
    deleted_files = 0
    deleted_bytes = 0

    with _tile_cache_lock:
        for p in cache_dir.glob(f"{metric}--*.png"):
            try:
                size = p.stat().st_size
            except FileNotFoundError:
                continue
            try:
                p.unlink()
            except FileNotFoundError:
                continue
            deleted_files += 1
            deleted_bytes += size

        global _tile_cache_stats
        stats = _tile_cache_stats
        if stats is None:
            _tile_cache_stats = _init_tile_cache_stats(cache_dir)
        else:
            _tile_cache_stats = _TileCacheStats(total_bytes=max(0, stats.total_bytes - deleted_bytes))

    return deleted_files, deleted_bytes


def _fetch_tile_png(metric: MetricId, date_bucket: str, granularity: str, x: int, y: int, z: int) -> bytes:
    fetcher = get_tile_fetcher(metric, date_bucket, granularity, z=z)  # type: ignore[arg-type]
    return fetcher.fetch_tile(x, y, z)


async def _acquire_gee_slot_or_499(request: Request) -> None:
    """
    Acquire a global EE slot, but bail out quickly if the client disconnects.

    The frontend aborts in-flight tile fetches during fast pans/zooms. If we just
    queue on a semaphore, we can end up doing expensive EE work for tiles the
    client no longer needs.
    """
    poll_seconds = 0.25
    while True:
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client disconnected")
        try:
            await asyncio.wait_for(_gee_semaphore.acquire(), timeout=poll_seconds)
            return
        except asyncio.TimeoutError:
            continue


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

    # Validate date formats up front so the frontend gets a fast 400 for bad input,
    # without needing to hit Earth Engine.
    try:
        if granularity == "monthly":
            date.fromisoformat(f"{date_bucket}-01")
        else:
            date.fromisoformat(date_bucket)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    payload = get_tile_template(metric, date_bucket, granularity, opacity=opacity)  # type: ignore[arg-type]
    return TileTemplateResponse(**payload)


@router.get("/{metric}/{granularity}/{date_bucket}/{z}/{x}/{y}.png")
async def tile_png(
    metric: MetricId,
    granularity: str,
    date_bucket: str,
    z: int,
    x: int,
    y: int,
    request: Request,
    background_tasks: BackgroundTasks,
    v: str = Query("0"),
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

    settings = get_settings()
    cache_key = _tile_cache_key(str(metric), granularity, date_bucket, z, x, y, version=v)

    cache_dir: Path | None = None
    if settings.tile_cache_max_mb > 0:
        try:
            cache_dir = settings.tile_cache_path
            cached = await asyncio.to_thread(_get_cached_tile, cache_dir, str(metric), cache_key)
        except Exception:
            cached = None
            cache_dir = None
        if cached is not None:
            return Response(
                content=cached,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=3600"},
            )

    try:
        await _acquire_gee_slot_or_499(request)
        try:
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="Client disconnected")
            png_bytes: bytes = await asyncio.to_thread(_fetch_tile_png, metric, date_bucket, granularity, x, y, z)  # type: ignore[arg-type]
        finally:
            _gee_semaphore.release()
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

    if cache_dir is not None:
        background_tasks.add_task(
            _put_cached_tile,
            cache_dir,
            str(metric),
            cache_key,
            png_bytes,
            settings.tile_cache_max_mb,
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        background=background_tasks,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.delete("/cache/{metric}")
async def clear_metric_tile_cache(metric: MetricId) -> dict[str, str | int | bool]:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail="Invalid metric")

    settings = get_settings()
    if settings.tile_cache_max_mb <= 0:
        return {
            "metric": str(metric),
            "cache_enabled": False,
            "deleted_files": 0,
            "deleted_bytes": 0,
        }

    cache_dir = settings.tile_cache_path
    deleted_files, deleted_bytes = await asyncio.to_thread(_clear_metric_cached_tiles, cache_dir, str(metric))

    return {
        "metric": str(metric),
        "cache_enabled": True,
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
    }
