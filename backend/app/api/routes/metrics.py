from datetime import date

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


@router.get("/{region_id}", response_model=MetricsResponse)
async def get_region_metrics(
    region_id: str,
    db: DBSession,
    start_date: date | None = Query(None, description="Start date"),
    end_date: date | None = Query(None, description="End date"),
    metrics: list[str] | None = Query(None, description="Metrics to include"),
    granularity: str = Query("monthly", description="Temporal granularity"),
) -> MetricsResponse:
    """Get time series metrics for a region."""
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

    # Group by metric
    metric_data: dict[str, MetricData] = {}
    metric_units = {
        "ndvi": "index (-1 to 1)",
        "nightlights": "nW/cm\u00b2/sr",
        "urban_density": "ratio (0 to 1)",
        "parking": "occupancy ratio",
    }

    for obs in observations:
        if obs.metric not in metric_data:
            metric_data[obs.metric] = MetricData(
                unit=metric_units.get(obs.metric, "unknown"),
                data=[],
            )

        # Format date based on granularity
        if granularity == "monthly":
            date_str = obs.date.strftime("%Y-%m")
        elif granularity == "weekly":
            date_str = obs.date.strftime("%Y-W%W")
        else:
            date_str = obs.date.isoformat()

        metric_data[obs.metric].data.append(
            MetricDataPoint(date=date_str, value=obs.value)
        )

    # Calculate seasonal summary if we have enough data
    seasonal_summary = await calculate_seasonal_summary(db, region_id)

    return MetricsResponse(
        region_id=region_id,
        region_name=region.name,
        metrics=metric_data,
        seasonal_summary=seasonal_summary,
    )


async def calculate_seasonal_summary(
    db: DBSession,
    region_id: str,
) -> SeasonalSummary | None:
    """Calculate seasonal averages for a region."""
    # Winter months: Dec, Jan, Feb (Northern Hemisphere)
    # Summer months: Jun, Jul, Aug

    # Get winter averages
    winter_query = (
        select(Observation.metric, func.avg(Observation.value))
        .where(
            Observation.region_id == region_id,
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
            Observation.region_id == region_id,
            func.extract("month", Observation.date).in_([6, 7, 8]),
        )
        .group_by(Observation.metric)
    )
    summer_result = await db.execute(summer_query)
    summer_avgs = dict(summer_result.all())

    if not winter_avgs and not summer_avgs:
        return None

    # Calculate percentage change
    change_pct = {}
    for metric in set(winter_avgs.keys()) | set(summer_avgs.keys()):
        winter_val = winter_avgs.get(metric, 0)
        summer_val = summer_avgs.get(metric, 0)
        if winter_val != 0:
            change_pct[metric] = ((summer_val - winter_val) / winter_val) * 100
        else:
            change_pct[metric] = 0.0

    return SeasonalSummary(
        winter_avg=SeasonalAverage(
            ndvi=winter_avgs.get("ndvi"),
            nightlights=winter_avgs.get("nightlights"),
            urban_density=winter_avgs.get("urban_density"),
            parking=winter_avgs.get("parking"),
        ),
        summer_avg=SeasonalAverage(
            ndvi=summer_avgs.get("ndvi"),
            nightlights=summer_avgs.get("nightlights"),
            urban_density=summer_avgs.get("urban_density"),
            parking=summer_avgs.get("parking"),
        ),
        change_pct=SeasonalAverage(
            ndvi=change_pct.get("ndvi"),
            nightlights=change_pct.get("nightlights"),
            urban_density=change_pct.get("urban_density"),
            parking=change_pct.get("parking"),
        ),
    )
