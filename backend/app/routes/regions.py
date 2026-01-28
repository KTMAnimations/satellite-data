from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Region
from app.schemas import RegionCreate, RegionListResponse, RegionResponse


router = APIRouter()


def _loads_geometry(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception:
        return {"type": "Polygon", "coordinates": []}


@router.get("", response_model=RegionListResponse)
async def list_regions(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: str | None = Query(None),
    category: str | None = Query(None),
    country: str | None = Query(None),
    search: str | None = Query(None),
) -> RegionListResponse:
    query = select(Region)

    if type:
        query = query.where(Region.type == type)
    if category:
        query = query.where(Region.category == category)
    if country:
        query = query.where(Region.country == country)
    if search:
        needle = f"%{search.lower()}%"
        query = query.where(func.lower(Region.name).like(needle))

    count_query = select(func.count()).select_from(query.subquery())
    total = int((await db.scalar(count_query)) or 0)

    query = query.order_by(Region.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    regions = result.scalars().all()

    return RegionListResponse(
        regions=[
            RegionResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                geometry=_loads_geometry(r.geometry),
                type=r.type,  # type: ignore[arg-type]
                country=r.country,
                state_province=r.state_province,
                category=r.category,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in regions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=RegionResponse, status_code=status.HTTP_201_CREATED)
async def create_region(
    payload: RegionCreate,
    db: AsyncSession = Depends(get_db),
) -> RegionResponse:
    try:
        geometry_str = json.dumps(payload.geometry)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid geometry: {e}") from e

    region = Region(
        name=payload.name,
        description=payload.description,
        geometry=geometry_str,
        type="custom",
        country=payload.country,
        state_province=payload.state_province,
        category=payload.category,
    )
    db.add(region)
    await db.flush()

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        geometry=payload.geometry,
        type=region.type,  # type: ignore[arg-type]
        country=region.country,
        state_province=region.state_province,
        category=region.category,
        created_at=region.created_at,
        updated_at=region.updated_at,
    )


@router.get("/{region_id}", response_model=RegionResponse)
async def get_region(region_id: str, db: AsyncSession = Depends(get_db)) -> RegionResponse:
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        geometry=_loads_geometry(region.geometry),
        type=region.type,  # type: ignore[arg-type]
        country=region.country,
        state_province=region.state_province,
        category=region.category,
        created_at=region.created_at,
        updated_at=region.updated_at,
    )


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(region_id: str, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    if region.type == "predefined":
        raise HTTPException(status_code=403, detail="Cannot delete predefined regions")
    await db.delete(region)

