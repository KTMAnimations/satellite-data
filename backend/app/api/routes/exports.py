from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.dependencies import DBSession, OptionalAPIKey
from app.core.redis import STATUS_PREFIX_EXPORT, get_redis_client
from app.models.region import Region
from app.schemas.export import (
    AnimationRequest,
    AnimationResponse,
    CSVExportRequest,
    ExportRequest,
    ExportResponse,
)

router = APIRouter()


@router.post("/pdf", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_pdf(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> ExportResponse:
    """Generate a PDF report for a region."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == request.region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {request.region_id} not found",
        )

    export_id = str(uuid4())
    now = datetime.now(timezone.utc)

    status_data = {
        "id": export_id,
        "status": "pending",
        "format": "pdf",
        "progress": 0.0,
        "message": "Queued",
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    redis_client = get_redis_client()
    await redis_client.set_status(export_id, status_data, STATUS_PREFIX_EXPORT)

    # Queue background task
    background_tasks.add_task(
        generate_pdf_report,
        export_id,
        request,
    )

    return ExportResponse(**status_data)


async def generate_pdf_report(export_id: str, request: ExportRequest) -> None:
    """Background task to generate PDF report."""
    from app.services.export.pdf import PDFReportGenerator

    redis_client = get_redis_client()
    await redis_client.update_status(
        export_id,
        {"status": "processing", "progress": 5.0, "message": "Generating PDF"},
        STATUS_PREFIX_EXPORT,
    )

    try:
        generator = PDFReportGenerator()
        file_path = await generator.generate(
            region_id=request.region_id,
            start_date=request.start_date,
            end_date=request.end_date,
            metrics=request.metrics,
            include_charts=request.include_charts,
            include_maps=request.include_maps,
            title=request.title,
            description=request.description,
            export_id=export_id,
        )

        await redis_client.update_status(
            export_id,
            {
                "status": "completed",
                "progress": 100.0,
                "message": "Completed",
                "download_url": f"/api/v1/exports/download/{export_id}",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            STATUS_PREFIX_EXPORT,
        )
    except Exception as e:
        await redis_client.update_status(
            export_id,
            {"status": "failed", "message": "Failed", "error": str(e)},
            STATUS_PREFIX_EXPORT,
        )


@router.post("/csv", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_csv(
    request: CSVExportRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> ExportResponse:
    """Export data as CSV."""
    export_id = str(uuid4())
    now = datetime.now(timezone.utc)

    status_data = {
        "id": export_id,
        "status": "pending",
        "format": "csv",
        "progress": 0.0,
        "message": "Queued",
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    redis_client = get_redis_client()
    await redis_client.set_status(export_id, status_data, STATUS_PREFIX_EXPORT)

    background_tasks.add_task(
        generate_csv_export,
        export_id,
        request,
    )

    return ExportResponse(**status_data)


async def generate_csv_export(export_id: str, request: CSVExportRequest) -> None:
    """Background task to generate CSV export."""
    from app.services.export.csv import CSVExporter

    redis_client = get_redis_client()
    await redis_client.update_status(
        export_id,
        {"status": "processing", "progress": 5.0, "message": "Generating CSV"},
        STATUS_PREFIX_EXPORT,
    )

    try:
        exporter = CSVExporter()
        file_path = await exporter.export(
            region_ids=request.region_ids,
            metrics=request.metrics,
            start_date=request.start_date,
            end_date=request.end_date,
            include_metadata=request.include_metadata,
            export_id=export_id,
        )

        await redis_client.update_status(
            export_id,
            {
                "status": "completed",
                "progress": 100.0,
                "message": "Completed",
                "download_url": f"/api/v1/exports/download/{export_id}",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            STATUS_PREFIX_EXPORT,
        )
    except Exception as e:
        await redis_client.update_status(
            export_id,
            {"status": "failed", "message": "Failed", "error": str(e)},
            STATUS_PREFIX_EXPORT,
        )


@router.post(
    "/animation", response_model=AnimationResponse, status_code=status.HTTP_202_ACCEPTED
)
async def export_animation(
    request: AnimationRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
    api_key: OptionalAPIKey,
) -> AnimationResponse:
    """Generate a time-lapse animation."""
    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == request.region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {request.region_id} not found",
        )

    export_id = str(uuid4())
    now = datetime.now(timezone.utc)

    status_data = {
        "id": export_id,
        "status": "pending",
        "format": request.format,
        "progress": 0.0,
        "message": "Queued",
        "frame_count": None,
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    redis_client = get_redis_client()
    await redis_client.set_status(export_id, status_data, STATUS_PREFIX_EXPORT)

    background_tasks.add_task(
        generate_animation,
        export_id,
        request,
    )

    return AnimationResponse(**status_data)


async def generate_animation(export_id: str, request: AnimationRequest) -> None:
    """Background task to generate animation."""
    from app.services.export.animation import AnimationGenerator

    redis_client = get_redis_client()
    await redis_client.update_status(
        export_id,
        {"status": "processing", "progress": 0.0, "message": "Starting"},
        STATUS_PREFIX_EXPORT,
    )

    try:
        generator = AnimationGenerator()
        async def on_progress(updates: dict) -> None:
            await redis_client.update_status(export_id, updates, STATUS_PREFIX_EXPORT)

        result = await generator.generate(
            region_id=request.region_id,
            metric=request.metric,
            start_date=request.start_date,
            end_date=request.end_date,
            format=request.format,
            frame_duration_ms=request.frame_duration_ms,
            width=request.width,
            height=request.height,
            export_id=export_id,
            lock_view=request.lock_view,
            view_center=request.view_center,
            view_zoom=request.view_zoom,
            progress_callback=on_progress,
        )

        await redis_client.update_status(
            export_id,
            {
                "status": "completed",
                "frame_count": result["frame_count"],
                "progress": 100.0,
                "message": "Completed",
                "download_url": f"/api/v1/exports/download/{export_id}",
                "file_size": result["file_size"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            STATUS_PREFIX_EXPORT,
        )
    except Exception as e:
        await redis_client.update_status(
            export_id,
            {"status": "failed", "message": "Failed", "error": str(e)},
            STATUS_PREFIX_EXPORT,
        )


@router.get("/{export_id}/status")
async def get_export_status(export_id: str) -> ExportResponse | AnimationResponse:
    """Get the status of an export request."""
    redis_client = get_redis_client()
    status_data = await redis_client.get_status(export_id, STATUS_PREFIX_EXPORT)

    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export with ID {export_id} not found",
        )

    if "frame_count" in status_data:
        return AnimationResponse(**status_data)
    return ExportResponse(**status_data)


@router.get("/download/{export_id}")
async def download_export(export_id: str) -> FileResponse:
    """Download a completed export."""
    redis_client = get_redis_client()
    status_data = await redis_client.get_status(export_id, STATUS_PREFIX_EXPORT)

    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export with ID {export_id} not found",
        )

    if status_data["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export is not yet complete",
        )

    from app.core.config import get_settings

    settings = get_settings()
    file_path = f"{settings.exports_dir}/{export_id}"

    # Determine file extension
    format_ext = {
        "pdf": ".pdf",
        "csv": ".csv",
        "gif": ".gif",
    }
    ext = format_ext.get(status_data["format"], "")

    return FileResponse(
        path=f"{file_path}{ext}",
        filename=f"export_{export_id}{ext}",
        media_type="application/octet-stream",
    )
