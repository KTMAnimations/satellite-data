from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DBSession, OptionalAPIKey
from app.models.analysis import AnalysisResult
from app.models.region import Region
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResults,
    AnalysisStatus,
    CompareRequest,
    CompareResponse,
    PeriodSummary,
)
from app.services.analysis.temporal import compute_period_averages

router = APIRouter()

# In-memory status tracking (in production, use Redis)
analysis_status: dict[str, dict] = {}


async def run_analysis_task(
    analysis_id: str,
    request: AnalysisRequest,
    db_url: str,
) -> None:
    """Background task to run analysis."""
    # This would be replaced with actual Celery task
    analysis_status[analysis_id]["status"] = "processing"
    analysis_status[analysis_id]["progress"] = 50.0

    # Simulate processing
    import asyncio

    await asyncio.sleep(2)

    analysis_status[analysis_id]["status"] = "completed"
    analysis_status[analysis_id]["progress"] = 100.0
    analysis_status[analysis_id]["completed_at"] = datetime.now(timezone.utc)


@router.post("", response_model=AnalysisStatus, status_code=status.HTTP_202_ACCEPTED)
async def request_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> AnalysisStatus:
    """Request a new analysis for a region."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == request.region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {request.region_id} not found",
        )

    # Check for existing analysis
    existing = await db.execute(
        select(AnalysisResult).where(
            AnalysisResult.region_id == request.region_id,
            AnalysisResult.analysis_type == request.analysis_type,
            AnalysisResult.start_date == request.start_date,
            AnalysisResult.end_date == request.end_date,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis with these parameters already exists",
        )

    # Create analysis task
    analysis_id = str(uuid4())
    now = datetime.now(timezone.utc)

    analysis_status[analysis_id] = {
        "id": analysis_id,
        "status": "pending",
        "progress": 0.0,
        "message": "Analysis queued",
        "created_at": now,
        "completed_at": None,
    }

    # Queue background task
    from app.core.config import get_settings

    settings = get_settings()
    background_tasks.add_task(
        run_analysis_task,
        analysis_id,
        request,
        settings.database_url,
    )

    return AnalysisStatus(
        id=analysis_id,
        status="pending",
        progress=0.0,
        message="Analysis queued",
        created_at=now,
        completed_at=None,
    )


@router.get("/{analysis_id}/status", response_model=AnalysisStatus)
async def get_analysis_status(analysis_id: str) -> AnalysisStatus:
    """Check the status of an analysis request."""
    if analysis_id not in analysis_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {analysis_id} not found",
        )

    status_data = analysis_status[analysis_id]
    return AnalysisStatus(**status_data)


@router.get("/{region_id}", response_model=list[AnalysisResponse])
async def get_region_analyses(
    region_id: str,
    db: DBSession,
    analysis_type: str | None = None,
) -> list[AnalysisResponse]:
    """Get all cached analyses for a region."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    query = select(AnalysisResult).where(AnalysisResult.region_id == region_id)
    if analysis_type:
        query = query.where(AnalysisResult.analysis_type == analysis_type)

    result = await db.execute(query)
    analyses = result.scalars().all()

    return [
        AnalysisResponse(
            id=a.id,
            region_id=a.region_id,
            region_name=region.name,
            analysis_type=a.analysis_type,
            start_date=a.start_date,
            end_date=a.end_date,
            results=AnalysisResults(**a.results),
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.post("/compare", response_model=CompareResponse)
async def compare_periods(
    request: CompareRequest,
    db: DBSession,
) -> CompareResponse:
    """Compare two time periods for a region."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == request.region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {request.region_id} not found",
        )

    # Compute averages for both periods
    period_a = await compute_period_averages(
        db,
        request.region_id,
        request.period_a_start,
        request.period_a_end,
        request.metrics,
    )

    period_b = await compute_period_averages(
        db,
        request.region_id,
        request.period_b_start,
        request.period_b_end,
        request.metrics,
    )

    # Calculate changes
    change = {}
    change_absolute = {}
    for metric in period_a["averages"]:
        if metric in period_b["averages"]:
            a_val = period_a["averages"][metric]
            b_val = period_b["averages"][metric]
            if a_val != 0:
                change[metric] = ((b_val - a_val) / a_val) * 100
            else:
                change[metric] = 0.0
            change_absolute[metric] = b_val - a_val

    return CompareResponse(
        region_id=request.region_id,
        region_name=region.name,
        period_a=PeriodSummary(
            start_date=request.period_a_start,
            end_date=request.period_a_end,
            averages=period_a["averages"],
            observation_count=period_a["count"],
        ),
        period_b=PeriodSummary(
            start_date=request.period_b_start,
            end_date=request.period_b_end,
            averages=period_b["averages"],
            observation_count=period_b["count"],
        ),
        change=change,
        change_absolute=change_absolute,
    )
