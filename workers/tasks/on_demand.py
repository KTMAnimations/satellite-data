import asyncio
from datetime import date
from typing import Any

from celery import shared_task

from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=2)
def process_custom_region(
    self,
    region_id: str,
    start_date: str,
    end_date: str,
    metrics: list[str],
) -> dict[str, Any]:
    """
    Process a custom user-defined region on demand.

    Args:
        region_id: Region ID
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        metrics: Metrics to compute

    Returns:
        Processing results
    """
    return asyncio.run(
        _process_custom_region_async(
            region_id,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
            metrics,
        )
    )


async def _process_custom_region_async(
    region_id: str,
    start_date: date,
    end_date: date,
    metrics: list[str],
) -> dict[str, Any]:
    """Async implementation of custom region processing."""
    from workers.tasks.precompute import _precompute_region_metrics_async

    return await _precompute_region_metrics_async(
        region_id, start_date, end_date, metrics
    )


@shared_task(bind=True, max_retries=2)
def run_analysis(
    self,
    region_id: str,
    analysis_type: str,
    start_date: str,
    end_date: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a specific analysis on a region.

    Args:
        region_id: Region to analyze
        analysis_type: Type of analysis
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        parameters: Additional analysis parameters

    Returns:
        Analysis results
    """
    return asyncio.run(
        _run_analysis_async(
            region_id,
            analysis_type,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
            parameters,
        )
    )


async def _run_analysis_async(
    region_id: str,
    analysis_type: str,
    start_date: date,
    end_date: date,
    parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    """Async implementation of analysis execution."""
    from sqlalchemy import select

    from app.models.region import Region
    from app.models.analysis import AnalysisResult
    from app.services.analysis.temporal import calculate_seasonal_change
    from app.services.analysis.change_detection import ChangeDetector
    from app.services.analysis.migration import MigrationAnalyzer

    async with get_db_context() as db:
        # Verify region exists
        result = await db.execute(select(Region).where(Region.id == region_id))
        region = result.scalar_one_or_none()

        if not region:
            raise ValueError(f"Region {region_id} not found")

        logger.info(
            "Running analysis",
            region=region.name,
            type=analysis_type,
        )

        # Run appropriate analysis
        if analysis_type == "seasonal_change":
            year = parameters.get("year", start_date.year) if parameters else start_date.year
            is_southern = parameters.get("is_southern_hemisphere", False) if parameters else False
            results = await calculate_seasonal_change(db, region_id, year, is_southern)

        elif analysis_type == "covid_impact":
            detector = ChangeDetector(db)
            results = await detector.analyze_covid_impact(
                region_id,
                parameters.get("metrics") if parameters else None,
            )

        elif analysis_type == "migration":
            analyzer = MigrationAnalyzer(db)
            year = parameters.get("year", start_date.year) if parameters else start_date.year
            results = await analyzer.analyze_seasonal_migration(region_id, year)

        elif analysis_type == "urban_growth":
            detector = ChangeDetector(db)
            results = await detector.compare_periods(
                region_id,
                start_date,
                start_date.replace(year=start_date.year + 1) - timedelta(days=1),
                end_date.replace(year=end_date.year - 1) + timedelta(days=1),
                end_date,
                parameters.get("metrics") if parameters else None,
            )

        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        # Store results
        analysis_result = AnalysisResult(
            region_id=region_id,
            analysis_type=analysis_type,
            start_date=start_date,
            end_date=end_date,
            results={
                "summary": results,
                "metrics": {},
                "methodology": f"Analysis type: {analysis_type}",
            },
        )
        db.add(analysis_result)

        logger.info("Analysis complete", region=region.name, type=analysis_type)

        return {
            "id": analysis_result.id,
            "status": "completed",
            "results": results,
        }


@shared_task(bind=True)
def generate_export(
    self,
    export_type: str,
    region_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate an export (PDF, CSV, animation).

    Args:
        export_type: Type of export
        region_id: Region to export
        parameters: Export parameters

    Returns:
        Export file info
    """
    return asyncio.run(_generate_export_async(export_type, region_id, parameters))


async def _generate_export_async(
    export_type: str,
    region_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Async implementation of export generation."""
    from app.services.export import PDFReportGenerator, CSVExporter, AnimationGenerator

    if export_type == "pdf":
        generator = PDFReportGenerator()
        path = await generator.generate(
            region_id=region_id,
            start_date=date.fromisoformat(parameters.get("start_date")) if parameters.get("start_date") else None,
            end_date=date.fromisoformat(parameters.get("end_date")) if parameters.get("end_date") else None,
            metrics=parameters.get("metrics"),
            include_charts=parameters.get("include_charts", True),
            include_maps=parameters.get("include_maps", True),
            title=parameters.get("title"),
            description=parameters.get("description"),
        )
        return {"path": path, "format": "pdf"}

    elif export_type == "csv":
        exporter = CSVExporter()
        path = await exporter.export(
            region_ids=[region_id],
            metrics=parameters.get("metrics"),
            start_date=date.fromisoformat(parameters.get("start_date")) if parameters.get("start_date") else None,
            end_date=date.fromisoformat(parameters.get("end_date")) if parameters.get("end_date") else None,
            include_metadata=parameters.get("include_metadata", False),
        )
        return {"path": path, "format": "csv"}

    elif export_type == "animation":
        generator = AnimationGenerator()
        result = await generator.generate(
            region_id=region_id,
            metric=parameters.get("metric", "nightlights"),
            start_date=date.fromisoformat(parameters["start_date"]),
            end_date=date.fromisoformat(parameters["end_date"]),
            format=parameters.get("format", "gif"),
            frame_duration_ms=parameters.get("frame_duration_ms", 500),
            width=parameters.get("width", 800),
            height=parameters.get("height", 600),
        )
        return result

    else:
        raise ValueError(f"Unknown export type: {export_type}")
