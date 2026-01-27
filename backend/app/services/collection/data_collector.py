"""
Data Collection Service

Orchestrates the complete data pipeline:
1. Fetch satellite imagery from GEE
2. Extract metrics (NDVI, nightlights, urban density, parking)
3. Store observations in the database
"""

import asyncio
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal
from uuid import uuid4

from geoalchemy2.functions import ST_AsGeoJSON
from shapely.geometry import Polygon, shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.observation import Observation
from app.models.region import Region
from app.services.features.ndvi import NDVIExtractor
from app.services.features.nightlights import NightlightsExtractor
from app.services.features.urban_density import UrbanDensityExtractor
from app.services.features.parking import ParkingDetector
from app.services.satellite.gee_client import GEEClient, VIIRSClient
from app.services.collection.raster_storage import save_raster

logger = get_logger(__name__)


MetricType = Literal["ndvi", "nightlights", "urban_density", "parking"]


def clean_nan_values(obj: Any) -> Any:
    """Recursively replace NaN/Inf values with None and convert numpy types for JSON serialization."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(clean_nan_values(item) for item in obj)
    elif isinstance(obj, (np.floating, float)):
        # Convert numpy floats to Python floats
        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(obj, (np.integer, int)):
        # Convert numpy ints to Python ints
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return clean_nan_values(obj.tolist())
    return obj


def is_valid_observation(value: float) -> bool:
    """Check if an observation value is valid (not NaN or Inf)."""
    import numpy as np

    if value is None:
        return False
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return False
    return True


@dataclass
class CollectionResult:
    """Result of a data collection operation."""
    region_id: str
    region_name: str
    start_date: date
    end_date: date
    metrics_collected: list[str]
    observations_created: int
    errors: list[str]


class DataCollectionService:
    """
    Service that orchestrates satellite data collection and storage.

    Usage:
        service = DataCollectionService(db_session)
        result = await service.collect_for_region(
            region_id="uuid",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            metrics=["ndvi", "nightlights"]
        )
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gee_client = GEEClient()
        self.viirs_client = VIIRSClient()

        # Initialize extractors
        self.extractors = {
            "ndvi": NDVIExtractor(),
            "nightlights": NightlightsExtractor(),
            "urban_density": UrbanDensityExtractor(),
            "parking": ParkingDetector(),
        }

    async def collect_for_region(
        self,
        region_id: str,
        start_date: date,
        end_date: date,
        metrics: list[MetricType] | None = None,
        granularity: Literal["daily", "weekly", "monthly"] = "monthly",
    ) -> CollectionResult:
        """
        Collect satellite data for a region and store observations.

        Args:
            region_id: UUID of the region
            start_date: Start of collection period
            end_date: End of collection period
            metrics: List of metrics to collect (default: all)
            granularity: Temporal granularity for composites

        Returns:
            CollectionResult with summary of what was collected
        """
        if metrics is None:
            metrics = ["ndvi", "nightlights", "urban_density", "parking"]

        errors = []
        observations_created = 0

        # 1. Get region from database
        result = await self.db.execute(
            select(Region, ST_AsGeoJSON(Region.geometry).label("geojson"))
            .where(Region.id == region_id)
        )
        row = result.one_or_none()

        if row is None:
            return CollectionResult(
                region_id=region_id,
                region_name="Unknown",
                start_date=start_date,
                end_date=end_date,
                metrics_collected=[],
                observations_created=0,
                errors=[f"Region {region_id} not found"],
            )

        region = row[0]
        geojson = row[1]

        import json
        geometry = shape(json.loads(geojson))

        logger.info(
            "Starting data collection",
            region=region.name,
            start_date=str(start_date),
            end_date=str(end_date),
            metrics=metrics,
        )

        # 2. Initialize satellite clients
        await self.gee_client.initialize()
        await self.viirs_client.initialize()

        # 3. Generate time periods based on granularity
        periods = self._generate_periods(start_date, end_date, granularity)

        # 4. Collect each metric
        for metric in metrics:
            try:
                if metric == "nightlights":
                    count = await self._collect_nightlights(
                        region_id, region.name, geometry, periods
                    )
                else:
                    count = await self._collect_optical_metric(
                        region_id, region.name, geometry, periods, metric
                    )
                observations_created += count
                logger.info(f"Collected {count} {metric} observations")
            except Exception as e:
                error_msg = f"Failed to collect {metric}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

        await self.db.commit()

        return CollectionResult(
            region_id=region_id,
            region_name=region.name,
            start_date=start_date,
            end_date=end_date,
            metrics_collected=metrics,
            observations_created=observations_created,
            errors=errors,
        )

    async def _collect_optical_metric(
        self,
        region_id: str,
        region_name: str,
        geometry: Polygon,
        periods: list[tuple[date, date]],
        metric: MetricType,
    ) -> int:
        """Collect optical metrics (NDVI, urban_density, parking) from Sentinel-2."""
        extractor = self.extractors[metric]
        observations_created = 0

        # Map metric to required bands
        band_mapping = {
            "ndvi": ["B4", "B8"],  # Red, NIR
            "urban_density": ["B8", "B11"],  # NIR, SWIR
            "parking": ["B2", "B3", "B4", "B8", "B11"],  # Full spectrum
        }
        bands = band_mapping.get(metric, ["B4", "B8"])

        for period_start, period_end in periods:
            try:
                # Check if observation already exists
                existing = await self._observation_exists(
                    region_id, metric, period_start
                )
                if existing:
                    logger.debug(f"Observation already exists: {metric} {period_start}")
                    continue

                # Get composite imagery for the period.
                #
                # Some regions/seasons (e.g., South Florida summer) often have
                # no Sentinel-2 scenes below a strict CLOUDY_PIXEL_PERCENTAGE cut.
                # We already apply an SCL-based cloud mask, so if the strict
                # filter yields nothing, progressively relax the threshold to
                # avoid missing entire months.
                imagery = None
                for cloud_threshold in (20.0, 40.0, 80.0, 100.0):
                    imagery = await self.gee_client.get_composite(
                        geometry=geometry,
                        start_date=period_start,
                        end_date=period_end,
                        bands=bands,
                        max_cloud_cover=cloud_threshold,
                        composite_method="median",
                    )
                    if imagery is not None:
                        if cloud_threshold != 20.0:
                            logger.info(
                                "Relaxed cloud threshold for composite",
                                region=region_name,
                                metric=metric,
                                period=f"{period_start} to {period_end}",
                                cloud_threshold=cloud_threshold,
                            )
                        break

                if imagery is None:
                    logger.warning(
                        f"No imagery available for {metric}",
                        region=region_name,
                        period=f"{period_start} to {period_end}",
                    )
                    continue

                # Extract metric
                result = await extractor.extract(imagery, geometry)

                # Validate the result
                if not is_valid_observation(result.value):
                    logger.warning(
                        f"Invalid observation value for {metric}",
                        region=region_name,
                        period=str(period_start),
                        value=result.value,
                    )
                    continue

                # Clean metadata for JSON serialization
                clean_metadata = clean_nan_values(result.metadata)

                # Save raster to file if available
                raster_path = None
                if result.raster is not None and result.bounds is not None:
                    raster_path = save_raster(
                        raster=result.raster,
                        bounds=result.bounds,
                        region_id=region_id,
                        metric=metric,
                        obs_date=period_start,
                    )
                    if raster_path:
                        logger.debug(f"Saved raster to {raster_path}")

                # Store observation
                observation = Observation(
                    id=str(uuid4()),
                    region_id=region_id,
                    date=period_start,
                    metric=metric,
                    value=result.value,
                    raster_path=raster_path,
                    extra_data=clean_metadata,
                )
                self.db.add(observation)
                observations_created += 1

                logger.debug(
                    f"Created observation",
                    metric=metric,
                    date=str(period_start),
                    value=result.value,
                    has_raster=raster_path is not None,
                )

            except Exception as e:
                logger.error(
                    f"Failed to collect {metric} for period {period_start}",
                    error=str(e),
                )
                continue

        return observations_created

    async def _collect_nightlights(
        self,
        region_id: str,
        region_name: str,
        geometry: Polygon,
        periods: list[tuple[date, date]],
    ) -> int:
        """Collect nighttime lights data from VIIRS."""
        extractor = self.extractors["nightlights"]
        observations_created = 0

        for period_start, period_end in periods:
            try:
                # Check if observation already exists
                existing = await self._observation_exists(
                    region_id, "nightlights", period_start
                )
                if existing:
                    continue

                # VIIRS data is monthly, so fetch the full period
                imagery_list = await self.viirs_client.get_imagery(
                    geometry=geometry,
                    start_date=period_start,
                    end_date=period_end,
                )

                if not imagery_list:
                    logger.warning(
                        f"No VIIRS data available",
                        region=region_name,
                        period=f"{period_start} to {period_end}",
                    )
                    continue

                # Use the first (usually only) monthly image
                imagery = imagery_list[0]

                # Extract metric
                result = await extractor.extract(imagery, geometry)

                # Validate the result
                if not is_valid_observation(result.value):
                    logger.warning(
                        f"Invalid nightlights value",
                        region=region_name,
                        period=str(period_start),
                        value=result.value,
                    )
                    continue

                # Clean metadata for JSON serialization
                clean_metadata = clean_nan_values(result.metadata)

                # Save raster to file if available
                raster_path = None
                if result.raster is not None and result.bounds is not None:
                    raster_path = save_raster(
                        raster=result.raster,
                        bounds=result.bounds,
                        region_id=region_id,
                        metric="nightlights",
                        obs_date=period_start,
                    )
                    if raster_path:
                        logger.debug(f"Saved nightlights raster to {raster_path}")

                # Store observation
                observation = Observation(
                    id=str(uuid4()),
                    region_id=region_id,
                    date=period_start,
                    metric="nightlights",
                    value=result.value,
                    raster_path=raster_path,
                    extra_data=clean_metadata,
                )
                self.db.add(observation)
                observations_created += 1

            except Exception as e:
                logger.error(
                    f"Failed to collect nightlights for period {period_start}",
                    error=str(e),
                )
                continue

        return observations_created

    async def _observation_exists(
        self,
        region_id: str,
        metric: str,
        obs_date: date,
    ) -> bool:
        """Check if an observation already exists."""
        result = await self.db.execute(
            select(Observation.id)
            .where(
                Observation.region_id == region_id,
                Observation.metric == metric,
                Observation.date == obs_date,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _generate_periods(
        self,
        start_date: date,
        end_date: date,
        granularity: str,
    ) -> list[tuple[date, date]]:
        """Generate time periods based on granularity."""
        periods = []
        current = start_date

        if granularity == "daily":
            while current <= end_date:
                periods.append((current, current))
                current += timedelta(days=1)
        elif granularity == "weekly":
            while current <= end_date:
                period_end = min(current + timedelta(days=6), end_date)
                periods.append((current, period_end))
                current += timedelta(days=7)
        else:  # monthly
            while current <= end_date:
                # Get the first day of next month
                if current.month == 12:
                    next_month = date(current.year + 1, 1, 1)
                else:
                    next_month = date(current.year, current.month + 1, 1)
                period_end = min(next_month - timedelta(days=1), end_date)
                periods.append((current, period_end))
                current = next_month

        return periods
