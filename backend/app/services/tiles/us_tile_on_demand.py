"""
US tile on-demand generator.

This module keeps the legacy public API used by the `/tiles/us/...` route, while
delegating implementation to the shared generator in `overlay_tile_on_demand`.

The only US-specific behavior is a quick reject for tiles that do not intersect
the continental US bounds (so we don't hit Earth Engine unnecessarily).
"""

from __future__ import annotations

from typing import Literal

from app.services.tiles.overlay_tile_on_demand import (
    DAILY_METRICS,
    ResolvedTileRequest,
    generate_overlay_tile_png,
    resolve_tile_request,
)
from app.services.tiles.us_tile_generator import US_BOUNDS_MERCATOR

TileGranularity = Literal["daily", "monthly"]


def resolve_us_tile_request(
    metric: str,
    date_str: str,
    requested_granularity: TileGranularity | None,
) -> ResolvedTileRequest:
    """Backwards-compatible wrapper around `resolve_tile_request()`."""
    return resolve_tile_request(
        metric=metric,
        date_str=date_str,
        requested_granularity=requested_granularity,
    )


async def generate_us_tile_png(
    metric: str,
    resolved: ResolvedTileRequest,
    z: int,
    x: int,
    y: int,
) -> bytes:
    """Generate a US overlay tile, returning a transparent tile outside US bounds."""
    return await generate_overlay_tile_png(
        metric=metric,
        resolved=resolved,
        z=z,
        x=x,
        y=y,
        reject_bounds_mercator=US_BOUNDS_MERCATOR,
    )

