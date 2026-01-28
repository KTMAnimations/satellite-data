from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import imageio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee import METRICS, build_metric_image, bucket_end, bucket_starts, geojson_to_ee_geometry, initialize_ee
from app.models import ExportJob, Region
from app.schemas import AnimationRequest, CSVExportRequest, ExportRequest, ExportResponse
from app.settings import get_settings


router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job_to_response(job: ExportJob) -> ExportResponse:
    return ExportResponse(
        id=job.id,
        status=job.status,  # type: ignore[arg-type]
        format=job.format,
        progress=job.progress,
        message=job.message,
        download_url=f"/api/v1/exports/download/{job.id}" if job.status == "completed" else None,
        file_size=job.file_size,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
    )


async def _update_job(db: AsyncSession, job_id: str, **updates) -> None:
    result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return
    for k, v in updates.items():
        setattr(job, k, v)


async def _generate_csv(job_id: str, request: CSVExportRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        await _update_job(db, job_id, status="processing", progress=5.0, message="Generating CSV")
        await db.commit()

        region_ids = request.region_ids or []
        if not region_ids:
            # Default: all regions.
            regions = (await db.execute(select(Region.id))).scalars().all()
            region_ids = list(regions)

        metrics = request.metrics or list(METRICS.keys())
        start_date = request.start_date
        end_date = request.end_date
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date are required")

        rows: list[list[str]] = []
        header = ["date", "region", "metric", "value"]
        if request.include_metadata:
            header.append("unit")
        rows.append(header)

        for region_id in region_ids:
            region = (await db.execute(select(Region).where(Region.id == region_id))).scalar_one_or_none()
            if region is None:
                continue
            geometry = json.loads(region.geometry)
            for metric in metrics:
                # Monthly CSV for exports (keeps file size manageable)
                from app.gee import compute_time_series

                series = await asyncio.to_thread(
                    compute_time_series,
                    geometry_geojson=geometry,
                    metric=metric,
                    start_date=start_date,
                    end_date=end_date,
                    granularity="monthly",
                )
                unit = METRICS[metric].unit
                for d, v in series:
                    row = [d, region.name, metric, f"{v:.6f}"]
                    if request.include_metadata:
                        row.append(unit)
                    rows.append(row)

        output = Path(settings.exports_path) / f"{job_id}.csv"
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        await _update_job(
            db,
            job_id,
            status="completed",
            progress=100.0,
            message="Completed",
            output_path=str(output),
            file_size=output.stat().st_size,
            completed_at=_now(),
        )
        await db.commit()

    await engine.dispose()


async def _generate_pdf(job_id: str, request: ExportRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        await _update_job(db, job_id, status="processing", progress=5.0, message="Generating PDF")
        await db.commit()

        region = (await db.execute(select(Region).where(Region.id == request.region_id))).scalar_one_or_none()
        if region is None:
            raise ValueError("Region not found")

        start_date = request.start_date
        end_date = request.end_date
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date are required")

        metrics = request.metrics or list(METRICS.keys())
        geometry = json.loads(region.geometry)

        # Compute monthly time series per metric and summarize with mean/min/max.
        from app.gee import compute_time_series

        summary_rows: list[list[str]] = [["Metric", "Unit", "Mean", "Min", "Max", "Points"]]
        for metric in metrics:
            series = await asyncio.to_thread(
                compute_time_series,
                geometry_geojson=geometry,
                metric=metric,
                start_date=start_date,
                end_date=end_date,
                granularity="monthly",
            )
            values = [v for _, v in series]
            if not values:
                continue
            mean_v = sum(values) / len(values)
            summary_rows.append(
                [
                    metric,
                    METRICS[metric].unit,
                    f"{mean_v:.4f}",
                    f"{min(values):.4f}",
                    f"{max(values):.4f}",
                    str(len(values)),
                ]
            )

        output = Path(settings.exports_path) / f"{job_id}.pdf"
        doc = SimpleDocTemplate(str(output), pagesize=letter)
        styles = getSampleStyleSheet()

        story = []
        story.append(Paragraph(request.title or f"Report: {region.name}", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Period: {start_date} to {end_date}", styles["Normal"]))
        story.append(Spacer(1, 12))
        if request.description:
            story.append(Paragraph(request.description, styles["BodyText"]))
            story.append(Spacer(1, 12))

        table = Table(summary_rows, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ]
            )
        )
        story.append(table)
        doc.build(story)

        await _update_job(
            db,
            job_id,
            status="completed",
            progress=100.0,
            message="Completed",
            output_path=str(output),
            file_size=output.stat().st_size,
            completed_at=_now(),
        )
        await db.commit()

    await engine.dispose()


async def _generate_animation(job_id: str, request: AnimationRequest, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    settings = get_settings()
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        await _update_job(db, job_id, status="processing", progress=0.0, message="Rendering frames")
        await db.commit()

        region = (await db.execute(select(Region).where(Region.id == request.region_id))).scalar_one_or_none()
        if region is None:
            raise ValueError("Region not found")

        geometry = json.loads(region.geometry)
        metric_def = METRICS[request.metric]

        initialize_ee()
        import ee

        geom = geojson_to_ee_geometry(geometry)

        # Choose monthly frames by default; daily if <= 90 days and supported.
        days = (request.end_date - request.start_date).days
        frame_granularity: str = "monthly"
        if days <= 90 and "daily" in metric_def.supported_granularities:
            frame_granularity = "daily"

        starts = bucket_starts(request.start_date, request.end_date, frame_granularity)  # type: ignore[arg-type]
        total = max(1, len(starts))

        frames = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, d0 in enumerate(starts):
                d1 = bucket_end(d0, frame_granularity)  # type: ignore[arg-type]
                ee_start = ee.Date(d0.isoformat())
                ee_end = ee.Date(d1.isoformat())

                img = build_metric_image(request.metric, ee_start, ee_end, geom)
                vmin, vmax = metric_def.value_range
                thumb = await asyncio.to_thread(
                    img.getThumbURL,
                    {
                        "region": geom,
                        "dimensions": [request.width, request.height],
                        "format": "png",
                        "min": vmin,
                        "max": vmax,
                        "palette": metric_def.palette,
                    },
                )
                resp = await client.get(thumb)
                resp.raise_for_status()
                frames.append(imageio.imread(resp.content))

                progress = ((i + 1) / total) * 95.0
                await _update_job(db, job_id, progress=progress, message=f"Rendered {i + 1}/{total} frames")
                await db.commit()

        output = Path(settings.exports_path) / f"{job_id}.gif"
        imageio.mimsave(output, frames, duration=request.frame_duration_ms / 1000.0)

        await _update_job(
            db,
            job_id,
            status="completed",
            progress=100.0,
            message="Completed",
            output_path=str(output),
            file_size=output.stat().st_size,
            completed_at=_now(),
        )
        await db.commit()

    await engine.dispose()


@router.post("/pdf", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_pdf(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="pdf",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()

    from app.settings import get_settings

    settings = get_settings()
    background_tasks.add_task(_generate_pdf, job.id, request, settings.database_url)
    return _job_to_response(job)


@router.post("/csv", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_csv(
    request: CSVExportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="csv",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()

    settings = get_settings()
    background_tasks.add_task(_generate_csv, job.id, request, settings.database_url)
    return _job_to_response(job)


@router.post("/animation", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export_animation(
    request: AnimationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    job = ExportJob(
        id=str(uuid4()),
        format="gif",
        status="pending",
        progress=0.0,
        message="Queued",
        request_json=request.model_dump_json(),
        created_at=_now(),
    )
    db.add(job)
    await db.flush()

    settings = get_settings()
    background_tasks.add_task(_generate_animation, job.id, request, settings.database_url)
    return _job_to_response(job)


@router.get("/{export_id}/status", response_model=ExportResponse)
async def get_export_status(export_id: str, db: AsyncSession = Depends(get_db)) -> ExportResponse:
    job = (await db.execute(select(ExportJob).where(ExportJob.id == export_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return _job_to_response(job)


@router.get("/download/{export_id}")
async def download_export(export_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    job = (await db.execute(select(ExportJob).where(ExportJob.id == export_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    if job.status != "completed" or not job.output_path:
        raise HTTPException(status_code=400, detail="Export not ready")

    output_path = Path(job.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Export file missing")

    media = "application/octet-stream"
    if output_path.suffix == ".pdf":
        media = "application/pdf"
    elif output_path.suffix == ".csv":
        media = "text/csv"
    elif output_path.suffix == ".gif":
        media = "image/gif"

    return FileResponse(path=str(output_path), filename=output_path.name, media_type=media)
