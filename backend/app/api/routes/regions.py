import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON
from sqlalchemy import func, select

from app.api.dependencies import DBSession, OptionalAPIKey, Pagination
from app.models.region import Region
from app.schemas.region import (
    RegionCreate,
    RegionListResponse,
    RegionResponse,
)

router = APIRouter()


def geometry_to_geojson(geom: Any) -> dict:
    """Convert geometry to GeoJSON dict."""
    if isinstance(geom, str):
        return json.loads(geom)
    return geom


@router.get("", response_model=RegionListResponse)
async def list_regions(
    db: DBSession,
    pagination: Pagination,
    type: str | None = Query(None, description="Filter by region type"),
    category: str | None = Query(None, description="Filter by category"),
    country: str | None = Query(None, description="Filter by country"),
    search: str | None = Query(None, description="Search by name"),
) -> RegionListResponse:
    """List all regions with optional filtering."""
    query = select(Region, ST_AsGeoJSON(Region.geometry).label("geojson"))

    # Apply filters
    if type:
        query = query.where(Region.type == type)
    if category:
        query = query.where(Region.category == category)
    if country:
        query = query.where(Region.country == country)
    if search:
        query = query.where(Region.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    rows = result.all()

    regions = []
    for row in rows:
        region = row[0]
        geojson = row[1]
        region_dict = {
            "id": region.id,
            "name": region.name,
            "description": region.description,
            "geometry": json.loads(geojson) if geojson else None,
            "type": region.type,
            "country": region.country,
            "state_province": region.state_province,
            "category": region.category,
            "created_at": region.created_at,
            "updated_at": region.updated_at,
        }
        regions.append(RegionResponse(**region_dict))

    return RegionListResponse(
        regions=regions,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("", response_model=RegionResponse, status_code=status.HTTP_201_CREATED)
async def create_region(
    region_data: RegionCreate,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> RegionResponse:
    """Create a new custom region."""
    # Convert GeoJSON to PostGIS geometry
    geojson_str = json.dumps(region_data.geometry)

    region = Region(
        name=region_data.name,
        description=region_data.description,
        geometry=ST_GeomFromGeoJSON(geojson_str),
        type="custom",
        country=region_data.country,
        state_province=region_data.state_province,
        category=region_data.category,
    )

    db.add(region)
    await db.flush()

    # Fetch the created region with geometry as GeoJSON
    result = await db.execute(
        select(Region, ST_AsGeoJSON(Region.geometry).label("geojson")).where(
            Region.id == region.id
        )
    )
    row = result.one()
    created_region = row[0]
    geojson = row[1]

    return RegionResponse(
        id=created_region.id,
        name=created_region.name,
        description=created_region.description,
        geometry=json.loads(geojson),
        type=created_region.type,
        country=created_region.country,
        state_province=created_region.state_province,
        category=created_region.category,
        created_at=created_region.created_at,
        updated_at=created_region.updated_at,
    )


@router.get("/{region_id}", response_model=RegionResponse)
async def get_region(region_id: str, db: DBSession) -> RegionResponse:
    """Get a specific region by ID."""
    result = await db.execute(
        select(Region, ST_AsGeoJSON(Region.geometry).label("geojson")).where(
            Region.id == region_id
        )
    )
    row = result.one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    region = row[0]
    geojson = row[1]

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        geometry=json.loads(geojson),
        type=region.type,
        country=region.country,
        state_province=region.state_province,
        category=region.category,
        created_at=region.created_at,
        updated_at=region.updated_at,
    )


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    region_id: str,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> None:
    """Delete a custom region."""
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    if region.type == "predefined":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete predefined regions",
        )

    await db.delete(region)
