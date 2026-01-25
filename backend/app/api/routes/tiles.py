from datetime import date
from io import BytesIO

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from app.api.dependencies import DBSession
from app.models.region import Region

router = APIRouter()


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
    valid_metrics = ["ndvi", "nightlights", "urban_density", "parking"]
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
            date=date,
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
