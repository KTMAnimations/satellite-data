from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.dependencies import DBSession
from app.models.observation import Observation
from app.models.region import Region
from app.schemas.observation import (
    MetricData,
    MetricDataPoint,
    MetricsResponse,
    SeasonalAverage,
    SeasonalSummary,
)

router = APIRouter()

Granularity = Literal["daily", "weekly", "monthly"]


def _bucket_date_for_granularity(
    obs_date: date,
    granularity: Granularity,
    *,
    start_date: date | None,
) -> date:
    if granularity == "daily":
        return obs_date

    if granularity == "monthly":
        return date(obs_date.year, obs_date.month, 1)

    # weekly
    if start_date is not None:
        # Anchor to the requested start_date (consistent with the collection
        # pipeline, which stores weekly observations at the start of each 7-day period).
        delta_days = (obs_date - start_date).days
        week_index = max(0, delta_days // 7)
        return start_date + timedelta(days=week_index * 7)

    # No start_date provided: fall back to ISO week start (Monday).
    return obs_date - timedelta(days=obs_date.weekday())


def _format_bucket_date(bucket_date: date, granularity: Granularity) -> str:
    # Frontend expects:
    # - monthly: "YYYY-MM"
    # - weekly/daily: "YYYY-MM-DD"
    if granularity == "monthly":
        return bucket_date.strftime("%Y-%m")
    return bucket_date.isoformat()


@router.get("/{region_id}", response_model=MetricsResponse)
async def get_region_metrics(
    region_id: str,
    db: DBSession,
    start_date: date | None = Query(None, description="Start date"),
    end_date: date | None = Query(None, description="End date"),
    metrics: list[str] | None = Query(None, description="Metrics to include"),
    granularity: Granularity = Query("monthly", description="Temporal granularity"),
) -> MetricsResponse:
    """Get time series metrics for a region."""
    if granularity not in {"daily", "weekly", "monthly"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="granularity must be one of: daily, weekly, monthly",
        )

    # Verify region exists
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region with ID {region_id} not found",
        )

    # Build query
    query = select(Observation).where(Observation.region_id == region_id)

    if start_date:
        query = query.where(Observation.date >= start_date)
    if end_date:
        query = query.where(Observation.date <= end_date)
    if metrics:
        query = query.where(Observation.metric.in_(metrics))

    query = query.order_by(Observation.date)
    result = await db.execute(query)
    observations = result.scalars().all()

    # Aggregate into requested granularity buckets.
    values_by_metric_and_bucket: dict[str, dict[date, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for obs in observations:
        bucket_date = _bucket_date_for_granularity(
            obs.date, granularity, start_date=start_date
        )
        values_by_metric_and_bucket[obs.metric][bucket_date].append(obs.value)

    metric_data: dict[str, MetricData] = {}
    metric_units = {
        # Original metrics
        "ndvi": "index (-1 to 1)",
        "nightlights": "nW/cm²/sr",
        "urban_density": "ratio (0 to 1)",
        "parking": "occupancy ratio",
        # Phase 1: Core datasets
        "land_cover": "probability (0 to 1)",
        "surface_water": "ratio (0 to 1)",
        "active_fire": "MW",
        # Phase 2: Air quality & weather
        "no2": "mol/m²",
        "temperature": "°C",
        "precipitation": "mm",
        "aerosol": "index",
        # Phase 3: Agriculture
        "cropland": "class code",
        "evapotranspiration": "mm",
        "soil_moisture": "m³/m³",
        # Phase 4: Historical & specialized
        "impervious": "ratio (0 to 1)",
        "fire_historical": "MW",
        "canopy_height": "m",
    }

    for metric, buckets in values_by_metric_and_bucket.items():
        points: list[MetricDataPoint] = []
        for bucket_date in sorted(buckets.keys()):
            values = buckets[bucket_date]
            if not values:
                continue
            avg_value = sum(values) / len(values)
            points.append(
                MetricDataPoint(
                    date=_format_bucket_date(bucket_date, granularity),
                    value=avg_value,
                )
            )

        metric_data[metric] = MetricData(
            unit=metric_units.get(metric, "unknown"),
            data=points,
        )

    # Calculate seasonal summary within the requested time range
    seasonal_summary = await calculate_seasonal_summary(
        db,
        region_id,
        start_date=start_date,
        end_date=end_date,
        metrics=metrics,
    )

    return MetricsResponse(
        region_id=region_id,
        region_name=region.name,
        metrics=metric_data,
        seasonal_summary=seasonal_summary,
    )


async def calculate_seasonal_summary(
    db: DBSession,
    region_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    metrics: list[str] | None = None,
) -> SeasonalSummary | None:
    """
    Calculate seasonal averages for a region within the requested time range.

    Returns None if data is not available for BOTH winter AND summer seasons.
    A valid seasonal comparison requires data from both seasons.
    """
    # Winter months: Dec, Jan, Feb (Northern Hemisphere)
    # Summer months: Jun, Jul, Aug

    supported_metrics = {"ndvi", "nightlights", "urban_density", "parking"}
    requested_metrics = set(metrics) if metrics else supported_metrics
    metric_filter = sorted(supported_metrics & requested_metrics)
    if not metric_filter:
        return None

    base_filters = [Observation.region_id == region_id]
    if start_date:
        base_filters.append(Observation.date >= start_date)
    if end_date:
        base_filters.append(Observation.date <= end_date)
    base_filters.append(Observation.metric.in_(metric_filter))

    # Get winter averages
    winter_query = (
        select(Observation.metric, func.avg(Observation.value))
        .where(
            *base_filters,
            func.extract("month", Observation.date).in_([12, 1, 2]),
        )
        .group_by(Observation.metric)
    )
    winter_result = await db.execute(winter_query)
    winter_avgs = dict(winter_result.all())

    # Get summer averages
    summer_query = (
        select(Observation.metric, func.avg(Observation.value))
        .where(
            *base_filters,
            func.extract("month", Observation.date).in_([6, 7, 8]),
        )
        .group_by(Observation.metric)
    )
    summer_result = await db.execute(summer_query)
    summer_avgs = dict(summer_result.all())

    # Require data for BOTH seasons to show a meaningful comparison
    # Without both seasons, a seasonal comparison is misleading
    if not winter_avgs or not summer_avgs:
        return None

    # Only include metrics that have data in BOTH seasons
    common_metrics = set(winter_avgs.keys()) & set(summer_avgs.keys())

    if not common_metrics:
        return None

    # Calculate percentage change only for metrics with data in both seasons
    change_pct = {}
    for metric in common_metrics:
        winter_val = winter_avgs[metric]
        summer_val = summer_avgs[metric]
        if winter_val != 0:
            change_pct[metric] = ((summer_val - winter_val) / winter_val) * 100
        else:
            change_pct[metric] = 0.0

    # Only return values for metrics that exist in BOTH seasons
    return SeasonalSummary(
        winter_avg=SeasonalAverage(
            ndvi=winter_avgs.get("ndvi") if "ndvi" in common_metrics else None,
            nightlights=winter_avgs.get("nightlights") if "nightlights" in common_metrics else None,
            urban_density=winter_avgs.get("urban_density") if "urban_density" in common_metrics else None,
            parking=winter_avgs.get("parking") if "parking" in common_metrics else None,
        ),
        summer_avg=SeasonalAverage(
            ndvi=summer_avgs.get("ndvi") if "ndvi" in common_metrics else None,
            nightlights=summer_avgs.get("nightlights") if "nightlights" in common_metrics else None,
            urban_density=summer_avgs.get("urban_density") if "urban_density" in common_metrics else None,
            parking=summer_avgs.get("parking") if "parking" in common_metrics else None,
        ),
        change_pct=SeasonalAverage(
            ndvi=change_pct.get("ndvi"),
            nightlights=change_pct.get("nightlights"),
            urban_density=change_pct.get("urban_density"),
            parking=change_pct.get("parking"),
        ),
    )
