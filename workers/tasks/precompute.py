import asyncio
from datetime import date, timedelta
from typing import Any

from celery import shared_task

from app.core.database import get_db_context
from app.core.logging import get_logger
from app.services.satellite import GEEClient, PlanetaryComputerClient
from app.services.features import (
    NDVIExtractor,
    NightlightsExtractor,
    UrbanDensityExtractor,
)

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def precompute_region_metrics(
    self,
    region_id: str,
    start_date: str,
    end_date: str,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Pre-compute metrics for a region over a time period.

    Args:
        region_id: Region to process
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        metrics: Specific metrics to compute (or all if None)

    Returns:
        Dictionary with processing results
    """
    return asyncio.run(
        _precompute_region_metrics_async(
            region_id,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
            metrics,
        )
    )


async def _precompute_region_metrics_async(
    region_id: str,
    start_date: date,
    end_date: date,
    metrics: list[str] | None,
) -> dict[str, Any]:
    """Async implementation of region metric precomputation."""
    from sqlalchemy import select
    from geoalchemy2.functions import ST_AsGeoJSON
    from shapely.geometry import shape
    import json

    from app.models.region import Region
    from app.models.observation import Observation

    async with get_db_context() as db:
        # Get region geometry
        result = await db.execute(
            select(Region, ST_AsGeoJSON(Region.geometry).label("geojson")).where(
                Region.id == region_id
            )
        )
        row = result.one_or_none()

        if not row:
            raise ValueError(f"Region {region_id} not found")

        region = row[0]
        geometry = shape(json.loads(row[1]))

        logger.info(
            "Starting precomputation",
            region=region.name,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Initialize clients
        gee_client = GEEClient()
        await gee_client.initialize()

        # Define extractors
        extractors = {
            "ndvi": NDVIExtractor(),
            "nightlights": NightlightsExtractor(),
            "urban_density": UrbanDensityExtractor(),
        }

        if metrics:
            extractors = {k: v for k, v in extractors.items() if k in metrics}

        results = {"processed": 0, "errors": 0, "metrics": {}}

        # Process monthly composites
        current = start_date.replace(day=1)
        while current <= end_date:
            month_end = (current.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)

            try:
                # Get composite imagery
                imagery = await gee_client.get_composite(
                    geometry=geometry,
                    start_date=current,
                    end_date=month_end,
                    composite_method="median",
                )

                if imagery is None:
                    logger.warning(
                        "No imagery for period",
                        region=region.name,
                        period=str(current),
                    )
                    current = month_end + timedelta(days=1)
                    continue

                # Extract each metric
                for metric_name, extractor in extractors.items():
                    try:
                        result = await extractor.extract(imagery, geometry)

                        # Store observation
                        obs = Observation(
                            region_id=region_id,
                            date=current,
                            metric=metric_name,
                            value=result.value,
                            metadata=result.metadata,
                        )
                        db.add(obs)

                        if metric_name not in results["metrics"]:
                            results["metrics"][metric_name] = 0
                        results["metrics"][metric_name] += 1
                        results["processed"] += 1

                    except Exception as e:
                        logger.error(
                            "Metric extraction failed",
                            metric=metric_name,
                            error=str(e),
                        )
                        results["errors"] += 1

                await db.commit()

            except Exception as e:
                logger.error(
                    "Period processing failed",
                    period=str(current),
                    error=str(e),
                )
                results["errors"] += 1

            current = month_end + timedelta(days=1)

        logger.info(
            "Precomputation complete",
            region=region.name,
            processed=results["processed"],
            errors=results["errors"],
        )

        return results


@shared_task(bind=True)
def precompute_all_regions(self, metrics: list[str] | None = None) -> dict[str, Any]:
    """Pre-compute metrics for all predefined regions."""
    return asyncio.run(_precompute_all_regions_async(metrics))


async def _precompute_all_regions_async(metrics: list[str] | None) -> dict[str, Any]:
    """Process all predefined regions."""
    from sqlalchemy import select

    from app.models.region import Region

    async with get_db_context() as db:
        result = await db.execute(
            select(Region.id).where(Region.type == "predefined")
        )
        region_ids = [r[0] for r in result.all()]

    results = {"total": len(region_ids), "completed": 0, "failed": 0}

    # Process sequentially to avoid overwhelming APIs
    end_date = date.today()
    start_date = end_date.replace(year=end_date.year - 1)

    for region_id in region_ids:
        try:
            await _precompute_region_metrics_async(
                region_id, start_date, end_date, metrics
            )
            results["completed"] += 1
        except Exception as e:
            logger.error("Region precomputation failed", region_id=region_id, error=str(e))
            results["failed"] += 1

    return results
