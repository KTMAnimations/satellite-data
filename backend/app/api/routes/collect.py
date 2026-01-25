"""
Data Collection API Routes

Endpoints for triggering satellite data collection for regions.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import DBSession, OptionalAPIKey
from app.core.redis import STATUS_PREFIX_COLLECTION, get_redis_client
from app.models.region import Region
from app.services.collection import DataCollectionService

router = APIRouter()


class CollectionRequest(BaseModel):
    """Request schema for data collection."""
    start_date: date = Field(..., description="Start date for collection")
    end_date: date = Field(..., description="End date for collection")
    metrics: list[Literal["ndvi", "nightlights", "urban_density", "parking"]] | None = Field(
        None,
        description="Metrics to collect (default: all)",
    )
    granularity: Literal["daily", "weekly", "monthly"] = Field(
        "monthly",
        description="Temporal granularity for composites",
    )


class CollectionResponse(BaseModel):
    """Response schema for data collection."""
    region_id: str
    region_name: str
    start_date: date
    end_date: date
    metrics_collected: list[str]
    observations_created: int
    errors: list[str]
    status: str


@router.post("/{region_id}", response_model=CollectionResponse)
async def collect_data_for_region(
    region_id: str,
    request: CollectionRequest,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> CollectionResponse:
    """
    Trigger data collection for a region.

    This endpoint fetches satellite imagery from Google Earth Engine,
    extracts the requested metrics, and stores observations in the database.

    Note: This is a synchronous operation for small date ranges. For large
    date ranges (> 6 months), use the background collection endpoint.
    """
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    # Validate date range
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    # Limit synchronous collection to 6 months
    date_diff = (request.end_date - request.start_date).days
    if date_diff > 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range exceeds 6 months. Use background collection endpoint for larger ranges.",
        )

    # Run collection
    service = DataCollectionService(db)
    result = await service.collect_for_region(
        region_id=region_id,
        start_date=request.start_date,
        end_date=request.end_date,
        metrics=request.metrics,
        granularity=request.granularity,
    )

    return CollectionResponse(
        region_id=result.region_id,
        region_name=result.region_name,
        start_date=result.start_date,
        end_date=result.end_date,
        metrics_collected=result.metrics_collected,
        observations_created=result.observations_created,
        errors=result.errors,
        status="completed" if not result.errors else "completed_with_errors",
    )


class BackgroundCollectionRequest(BaseModel):
    """Request schema for background data collection."""
    start_date: date = Field(..., description="Start date for collection")
    end_date: date = Field(..., description="End date for collection")
    metrics: list[Literal["ndvi", "nightlights", "urban_density", "parking"]] | None = Field(
        None,
        description="Metrics to collect (default: all)",
    )


class BackgroundCollectionResponse(BaseModel):
    """Response for background collection."""
    task_id: str
    region_id: str
    region_name: str
    status: str
    message: str


async def _run_background_collection(
    task_id: str,
    region_id: str,
    start_date: date,
    end_date: date,
    metrics: list[str] | None,
    db_url: str,
):
    """Background task to run collection."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    redis_client = get_redis_client()
    await redis_client.update_status(
        task_id,
        {"status": "running"},
        STATUS_PREFIX_COLLECTION,
    )

    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            service = DataCollectionService(db)
            result = await service.collect_for_region(
                region_id=region_id,
                start_date=start_date,
                end_date=end_date,
                metrics=metrics,
                granularity="monthly",
            )

        await redis_client.update_status(
            task_id,
            {
                "status": "completed",
                "result": {
                    "observations_created": result.observations_created,
                    "errors": result.errors,
                },
            },
            STATUS_PREFIX_COLLECTION,
        )

    except Exception as e:
        await redis_client.update_status(
            task_id,
            {"status": "failed", "error": str(e)},
            STATUS_PREFIX_COLLECTION,
        )


@router.post("/{region_id}/background", response_model=BackgroundCollectionResponse)
async def collect_data_background(
    region_id: str,
    request: BackgroundCollectionRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> BackgroundCollectionResponse:
    """
    Trigger background data collection for a region.

    Use this endpoint for large date ranges (> 6 months).
    Returns a task_id that can be used to check progress.
    """
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    from uuid import uuid4
    task_id = str(uuid4())

    status_data = {
        "status": "pending",
        "region_id": region_id,
        "region_name": region.name,
    }

    redis_client = get_redis_client()
    await redis_client.set_status(task_id, status_data, STATUS_PREFIX_COLLECTION)

    from app.core.config import get_settings
    settings = get_settings()

    background_tasks.add_task(
        _run_background_collection,
        task_id,
        region_id,
        request.start_date,
        request.end_date,
        request.metrics,
        settings.database_url,
    )

    return BackgroundCollectionResponse(
        task_id=task_id,
        region_id=region_id,
        region_name=region.name,
        status="pending",
        message="Collection started in background",
    )


@router.get("/status/{task_id}")
async def get_collection_status(task_id: str) -> dict:
    """Get the status of a background collection task."""
    redis_client = get_redis_client()
    status_data = await redis_client.get_status(task_id, STATUS_PREFIX_COLLECTION)

    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return status_data
