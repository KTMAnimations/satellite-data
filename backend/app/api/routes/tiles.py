import math
from datetime import date
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import DBSession
from app.core.logging import get_logger
from app.models.region import Region

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# US-Wide Pre-generated Tiles
# ============================================================================

@router.get("/us/{metric}/{date_str}/{z}/{x}/{y}.png")
async def get_us_tile(
    metric: str,
    date_str: str,
    z: int,
    x: int,
    y: int,
) -> Response:
    """
    Get a pre-generated US-wide tile.

    These tiles cover the entire continental US and are generated in advance
    for fast loading. No region-specific data needed.

    Args:
        metric: One of ndvi, nightlights, urban_density, parking
        date_str: Format YYYY-MM (monthly) or YYYY-MM-DD (daily, nightlights only)
        z: Zoom level (8-10)
        x: Tile X coordinate
        y: Tile Y coordinate

    Note:
        Daily granularity (YYYY-MM-DD) is only supported for nightlights metric
        using NASA Black Marble VNP46A2 data. Other metrics use monthly composites.
    """
    from pathlib import Path
    from app.core.config import get_settings
    import re

    # Validate metric
    valid_metrics = [
        "ndvi", "nightlights", "urban_density", "parking",
        # Phase 1: Core datasets
        "land_cover", "surface_water", "active_fire",
        # Phase 2: Air quality & weather
        "no2", "temperature", "precipitation", "aerosol",
        # Phase 3: Agriculture
        "cropland", "evapotranspiration", "soil_moisture",
        # Phase 4: Historical & specialized
        "impervious", "fire_historical", "canopy_height",
    ]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric. Must be one of: {valid_metrics}",
        )

    # Validate zoom level (8-10 supported, 11 returns upscaled)
    if z < 8 or z > 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zoom level must be between 8 and 11 for US tiles",
        )

    # Validate date format: YYYY-MM (monthly) or YYYY-MM-DD (daily)
    is_daily = False
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        is_daily = True
        # Daily granularity only supported for nightlights
        if metric != "nightlights":
            # For non-nightlights metrics, fall back to monthly
            date_str = date_str[:7]  # Convert YYYY-MM-DD to YYYY-MM
            is_daily = False
    elif not re.match(r"^\d{4}-\d{2}$", date_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be in format YYYY-MM (monthly) or YYYY-MM-DD (daily for nightlights)",
        )

    # Look up the pre-generated tile
    settings = get_settings()
    tile_path = Path(settings.cache_dir) / "us_tiles" / metric / date_str / str(z) / str(x) / f"{y}.png"

    if tile_path.exists():
        # Shorter cache for daily tiles as they may be updated more frequently
        cache_duration = 86400 if is_daily else 604800  # 1 day vs 1 week
        return Response(
            content=tile_path.read_bytes(),
            media_type="image/png",
            headers={
                "Cache-Control": f"public, max-age={cache_duration}",
                "X-Tile-Source": "pregenerated",
                "X-Tile-Granularity": "daily" if is_daily else "monthly",
            },
        )

    # If daily tile not found, try falling back to monthly
    if is_daily:
        monthly_date = date_str[:7]
        monthly_path = Path(settings.cache_dir) / "us_tiles" / metric / monthly_date / str(z) / str(x) / f"{y}.png"
        if monthly_path.exists():
            return Response(
                content=monthly_path.read_bytes(),
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=604800",
                    "X-Tile-Source": "pregenerated",
                    "X-Tile-Granularity": "monthly-fallback",
                },
            )

    # Return empty transparent tile if not found
    from app.services.tiles.generator import create_empty_tile
    return Response(
        content=create_empty_tile(),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Tile-Source": "empty",
        },
    )


@router.get("/us/available")
async def get_us_available_tiles() -> dict:
    """
    List available pre-generated US tiles.

    Returns information about which metrics and months have tiles available.
    """
    from pathlib import Path
    from app.core.config import get_settings

    settings = get_settings()
    tiles_dir = Path(settings.cache_dir) / "us_tiles"

    available = {}

    if tiles_dir.exists():
        for metric_dir in tiles_dir.iterdir():
            if metric_dir.is_dir():
                metric = metric_dir.name
                months = []
                for month_dir in metric_dir.iterdir():
                    if month_dir.is_dir():
                        # Count tiles
                        tile_count = sum(1 for _ in month_dir.rglob("*.png"))
                        months.append({
                            "year_month": month_dir.name,
                            "tile_count": tile_count,
                        })
                available[metric] = sorted(months, key=lambda x: x["year_month"])

    return {
        "status": "ok",
        "tiles_dir": str(tiles_dir),
        "metrics": available,
    }


@router.get("/{region_id}/{metric}/{z}/{x}/{y}.png")
async def get_tile(
    region_id: str,
    metric: str,
    z: int,
    x: int,
    y: int,
    db: DBSession,
    date: date | None = Query(None, description="Date for the tile"),
) -> Response:
    """Get a map tile for a region and metric."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    # Validate metric
    valid_metrics = [
        "ndvi", "nightlights", "urban_density", "parking",
        # Phase 1: Core datasets
        "land_cover", "surface_water", "active_fire",
        # Phase 2: Air quality & weather
        "no2", "temperature", "precipitation", "aerosol",
        # Phase 3: Agriculture
        "cropland", "evapotranspiration", "soil_moisture",
        # Phase 4: Historical & specialized
        "impervious", "fire_historical", "canopy_height",
    ]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric. Must be one of: {valid_metrics}",
        )

    # Generate tile
    try:
        from app.services.tiles.generator import TileGenerator

        generator = TileGenerator()
        tile_data = await generator.generate_tile(
            region_id=region_id,
            metric=metric,
            z=z,
            x=x,
            y=y,
            tile_date=date,
        )

        return Response(
            content=tile_data,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",
            },
        )
    except FileNotFoundError:
        # Return a transparent tile if data doesn't exist
        from app.services.tiles.generator import create_empty_tile

        return Response(
            content=create_empty_tile(),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate tile: {str(e)}",
        )


@router.get("/{region_id}/bounds")
async def get_region_bounds(
    region_id: str,
    db: DBSession,
) -> dict:
    """Get the bounding box for a region."""
    from geoalchemy2.functions import ST_Envelope, ST_AsGeoJSON

    result = await db.execute(
        select(ST_AsGeoJSON(ST_Envelope(Region.geometry))).where(
            Region.id == region_id
        )
    )
    bounds_geojson = result.scalar_one_or_none()

    if bounds_geojson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    import json

    bounds = json.loads(bounds_geojson)

    # Extract min/max from the envelope polygon
    coords = bounds["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    return {
        "region_id": region_id,
        "bounds": {
            "west": min(lons),
            "south": min(lats),
            "east": max(lons),
            "north": max(lats),
        },
        "center": {
            "lon": (min(lons) + max(lons)) / 2,
            "lat": (min(lats) + max(lats)) / 2,
        },
    }


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to tile coordinates."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return x, y


class WarmTilesRequest(BaseModel):
    """Request schema for tile warming."""
    zoom_levels: list[int] = Field(default=[10, 11, 12], description="Zoom levels to pre-warm")
    metrics: list[Literal[
        "ndvi", "nightlights", "urban_density", "parking",
        "land_cover", "surface_water", "active_fire",
        "no2", "temperature", "precipitation", "aerosol",
        "cropland", "evapotranspiration", "soil_moisture",
        "impervious", "fire_historical", "canopy_height",
    ]] = Field(
        default=["ndvi", "nightlights", "urban_density", "parking"],
        description="Metrics to warm",
    )
    dates: list[str] | None = Field(
        default=None,
        description="Specific dates to warm (YYYY-MM-DD). If None, warms latest data.",
    )


class WarmTilesResponse(BaseModel):
    """Response for tile warming."""
    region_id: str
    tiles_generated: int
    status: str


async def _warm_tiles_background(
    region_id: str,
    bounds: dict,
    zoom_levels: list[int],
    metrics: list[str],
    dates: list[str] | None,
):
    """Background task to warm tiles."""
    from app.services.tiles.generator import TileGenerator

    generator = TileGenerator()
    tiles_generated = 0

    west, south, east, north = bounds["west"], bounds["south"], bounds["east"], bounds["north"]

    # Use a few representative dates if none specified
    if dates is None:
        dates = ["2023-01-01", "2023-06-01", "2024-01-01", "2024-06-01"]

    for zoom in zoom_levels:
        x_min, y_max = lat_lon_to_tile(north, west, zoom)
        x_max, y_min = lat_lon_to_tile(south, east, zoom)

        for metric in metrics:
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    for tile_date in dates:
                        try:
                            await generator.generate_tile(
                                region_id=region_id,
                                metric=metric,
                                z=zoom,
                                x=x,
                                y=y,
                                tile_date=date.fromisoformat(tile_date),
                            )
                            tiles_generated += 1
                        except Exception as e:
                            logger.debug(f"Tile warming failed for {metric}/{zoom}/{x}/{y}: {e}")

    logger.info(f"Tile warming complete for region {region_id}: {tiles_generated} tiles")


@router.post("/{region_id}/warm")
async def warm_tiles(
    region_id: str,
    request: WarmTilesRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> WarmTilesResponse:
    """
    Pre-generate tiles for a region to enable fast loading.

    This endpoint generates and caches tiles at the specified zoom levels
    for all metrics. Running this after data collection will significantly
    improve map loading times.
    """
    from geoalchemy2.functions import ST_Envelope, ST_AsGeoJSON

    # Get region bounds
    result = await db.execute(
        select(ST_AsGeoJSON(ST_Envelope(Region.geometry))).where(
            Region.id == region_id
        )
    )
    bounds_geojson = result.scalar_one_or_none()

    if bounds_geojson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    import json
    bounds_data = json.loads(bounds_geojson)
    coords = bounds_data["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    bounds = {
        "west": min(lons),
        "south": min(lats),
        "east": max(lons),
        "north": max(lats),
    }

    # Start background task
    background_tasks.add_task(
        _warm_tiles_background,
        region_id,
        bounds,
        request.zoom_levels,
        request.metrics,
        request.dates,
    )

    return WarmTilesResponse(
        region_id=region_id,
        tiles_generated=0,  # Will be updated in background
        status="warming_started",
    )


@router.post("/warm-all-presets")
async def warm_all_preset_tiles(
    request: WarmTilesRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> dict:
    """
    Pre-generate tiles for ALL preset regions.

    This is a bulk operation that warms tiles for all predefined regions.
    Useful for initial deployment or after bulk data collection.
    """
    from geoalchemy2.functions import ST_Envelope, ST_AsGeoJSON

    # Get all preset regions
    result = await db.execute(
        select(Region.id, ST_AsGeoJSON(ST_Envelope(Region.geometry)))
        .where(Region.type == "predefined")
    )
    regions = result.fetchall()

    if not regions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preset regions found",
        )

    import json
    for region_id, bounds_geojson in regions:
        bounds_data = json.loads(bounds_geojson)
        coords = bounds_data["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]

        bounds = {
            "west": min(lons),
            "south": min(lats),
            "east": max(lons),
            "north": max(lats),
        }

        background_tasks.add_task(
            _warm_tiles_background,
            region_id,
            bounds,
            request.zoom_levels,
            request.metrics,
            request.dates,
        )

    return {
        "message": f"Started warming tiles for {len(regions)} preset regions",
        "regions_count": len(regions),
        "status": "warming_started",
    }
