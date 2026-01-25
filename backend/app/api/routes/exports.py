from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.dependencies import DBSession, OptionalAPIKey
from app.models.region import Region
from app.schemas.export import (
    AnimationRequest,
    AnimationResponse,
    CSVExportRequest,
    ExportRequest,
    ExportResponse,
)

router = APIRouter()

# In-memory export status tracking
export_status: dict[str, dict] = {}


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

    export_status[export_id] = {
        "id": export_id,
        "status": "pending",
        "format": "pdf",
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    # Queue background task
    background_tasks.add_task(
        generate_pdf_report,
        export_id,
        request,
    )

    return ExportResponse(**export_status[export_id])


async def generate_pdf_report(export_id: str, request: ExportRequest) -> None:
    """Background task to generate PDF report."""
    from app.services.export.pdf import PDFReportGenerator

    export_status[export_id]["status"] = "processing"

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
        )

        export_status[export_id]["status"] = "completed"
        export_status[export_id]["download_url"] = f"/api/v1/exports/download/{export_id}"
        export_status[export_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        export_status[export_id]["status"] = "failed"
        export_status[export_id]["error"] = str(e)


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

    export_status[export_id] = {
        "id": export_id,
        "status": "pending",
        "format": "csv",
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(
        generate_csv_export,
        export_id,
        request,
    )

    return ExportResponse(**export_status[export_id])


async def generate_csv_export(export_id: str, request: CSVExportRequest) -> None:
    """Background task to generate CSV export."""
    from app.services.export.csv import CSVExporter

    export_status[export_id]["status"] = "processing"

    try:
        exporter = CSVExporter()
        file_path = await exporter.export(
            region_ids=request.region_ids,
            metrics=request.metrics,
            start_date=request.start_date,
            end_date=request.end_date,
            include_metadata=request.include_metadata,
        )

        export_status[export_id]["status"] = "completed"
        export_status[export_id]["download_url"] = f"/api/v1/exports/download/{export_id}"
        export_status[export_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        export_status[export_id]["status"] = "failed"
        export_status[export_id]["error"] = str(e)


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

    export_status[export_id] = {
        "id": export_id,
        "status": "pending",
        "format": request.format,
        "frame_count": None,
        "download_url": None,
        "file_size": None,
        "created_at": now.isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(
        generate_animation,
        export_id,
        request,
    )

    return AnimationResponse(**export_status[export_id])


async def generate_animation(export_id: str, request: AnimationRequest) -> None:
    """Background task to generate animation."""
    from app.services.export.animation import AnimationGenerator

    export_status[export_id]["status"] = "processing"

    try:
        generator = AnimationGenerator()
        result = await generator.generate(
            region_id=request.region_id,
            metric=request.metric,
            start_date=request.start_date,
            end_date=request.end_date,
            format=request.format,
            frame_duration_ms=request.frame_duration_ms,
            width=request.width,
            height=request.height,
        )

        export_status[export_id]["status"] = "completed"
        export_status[export_id]["frame_count"] = result["frame_count"]
        export_status[export_id]["download_url"] = f"/api/v1/exports/download/{export_id}"
        export_status[export_id]["file_size"] = result["file_size"]
        export_status[export_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        export_status[export_id]["status"] = "failed"
        export_status[export_id]["error"] = str(e)


@router.get("/{export_id}/status")
async def get_export_status(export_id: str) -> ExportResponse | AnimationResponse:
    """Get the status of an export request."""
    if export_id not in export_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export with ID {export_id} not found",
        )

    status_data = export_status[export_id]
    if "frame_count" in status_data:
        return AnimationResponse(**status_data)
    return ExportResponse(**status_data)


@router.get("/download/{export_id}")
async def download_export(export_id: str) -> FileResponse:
    """Download a completed export."""
    if export_id not in export_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export with ID {export_id} not found",
        )

    status_data = export_status[export_id]
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
        "webm": ".webm",
    }
    ext = format_ext.get(status_data["format"], "")

    return FileResponse(
        path=f"{file_path}{ext}",
        filename=f"export_{export_id}{ext}",
        media_type="application/octet-stream",
    )
