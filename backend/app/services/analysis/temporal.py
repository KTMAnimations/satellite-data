from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.observation import Observation

logger = get_logger(__name__)


async def compute_period_averages(
    db: AsyncSession,
    region_id: str,
    start_date: date,
    end_date: date,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute average values for metrics in a time period.

    Args:
        db: Database session
        region_id: Region to analyze
        start_date: Period start
        end_date: Period end
        metrics: Optional list of metrics to include

    Returns:
        Dictionary with averages and observation count
    """
    query = (
        select(Observation.metric, func.avg(Observation.value), func.count())
        .where(
            Observation.region_id == region_id,
            Observation.date >= start_date,
            Observation.date <= end_date,
        )
        .group_by(Observation.metric)
    )

    if metrics:
        query = query.where(Observation.metric.in_(metrics))

    result = await db.execute(query)
    rows = result.all()

    averages = {}
    total_count = 0

    for metric, avg_value, count in rows:
        averages[metric] = float(avg_value) if avg_value else 0.0
        total_count += count

    return {
        "averages": averages,
        "count": total_count,
    }


async def calculate_seasonal_change(
    db: AsyncSession,
    region_id: str,
    year: int,
    is_southern_hemisphere: bool = False,
) -> dict[str, Any]:
    """
    Calculate seasonal changes for a region.

    Args:
        db: Database session
        region_id: Region to analyze
        year: Year to analyze
        is_southern_hemisphere: If True, flip winter/summer definitions

    Returns:
        Dictionary with seasonal comparison
    """
    # Define seasons based on hemisphere
    if is_southern_hemisphere:
        winter_months = [6, 7, 8]  # Jun-Aug
        summer_months = [12, 1, 2]  # Dec-Feb
    else:
        winter_months = [12, 1, 2]  # Dec-Feb
        summer_months = [6, 7, 8]  # Jun-Aug

    # Winter query (handles year boundary for Dec)
    winter_query = (
        select(Observation.metric, func.avg(Observation.value))
        .where(
            Observation.region_id == region_id,
            func.extract("month", Observation.date).in_(winter_months),
        )
        .group_by(Observation.metric)
    )

    # Add year filter
    if 12 in winter_months:
        # Winter spans Dec of previous year and Jan-Feb of current year
        winter_query = winter_query.where(
            (
                (func.extract("year", Observation.date) == year)
                & (func.extract("month", Observation.date).in_([1, 2]))
            )
            | (
                (func.extract("year", Observation.date) == year - 1)
                & (func.extract("month", Observation.date) == 12)
            )
        )
    else:
        winter_query = winter_query.where(
            func.extract("year", Observation.date) == year
        )

    # Summer query
    summer_query = (
        select(Observation.metric, func.avg(Observation.value))
        .where(
            Observation.region_id == region_id,
            func.extract("year", Observation.date) == year,
            func.extract("month", Observation.date).in_(summer_months),
        )
        .group_by(Observation.metric)
    )

    winter_result = await db.execute(winter_query)
    summer_result = await db.execute(summer_query)

    winter_avgs = dict(winter_result.all())
    summer_avgs = dict(summer_result.all())

    # Calculate changes
    changes = {}
    for metric in set(winter_avgs.keys()) | set(summer_avgs.keys()):
        winter_val = winter_avgs.get(metric, 0) or 0
        summer_val = summer_avgs.get(metric, 0) or 0

        if winter_val != 0:
            pct_change = ((summer_val - winter_val) / winter_val) * 100
        else:
            pct_change = 0.0

        changes[metric] = {
            "winter": winter_val,
            "summer": summer_val,
            "change_pct": pct_change,
            "change_absolute": summer_val - winter_val,
        }

    return {
        "year": year,
        "is_southern_hemisphere": is_southern_hemisphere,
        "changes": changes,
    }


class TemporalAnalyzer:
    """Analyze temporal patterns in satellite data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_trend(
        self,
        region_id: str,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Analyze trend in a metric over time.

        Uses simple linear regression to identify trends.
        """
        import numpy as np

        query = (
            select(Observation.date, Observation.value)
            .where(
                Observation.region_id == region_id,
                Observation.metric == metric,
                Observation.date >= start_date,
                Observation.date <= end_date,
            )
            .order_by(Observation.date)
        )

        result = await self.db.execute(query)
        rows = result.all()

        if len(rows) < 2:
            return {
                "metric": metric,
                "trend": "insufficient_data",
                "slope": 0,
                "r_squared": 0,
            }

        # Convert to arrays
        dates = np.array([(r[0] - rows[0][0]).days for r in rows])
        values = np.array([r[1] for r in rows])

        # Linear regression
        n = len(dates)
        sum_x = np.sum(dates)
        sum_y = np.sum(values)
        sum_xy = np.sum(dates * values)
        sum_xx = np.sum(dates * dates)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x + 1e-10)
        intercept = (sum_y - slope * sum_x) / n

        # R-squared
        y_pred = slope * dates + intercept
        ss_res = np.sum((values - y_pred) ** 2)
        ss_tot = np.sum((values - np.mean(values)) ** 2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-10))

        # Interpret trend
        if abs(slope) < 0.001:
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "metric": metric,
            "trend": trend,
            "slope": float(slope),
            "slope_per_year": float(slope * 365),
            "r_squared": float(r_squared),
            "start_value": float(values[0]),
            "end_value": float(values[-1]),
            "data_points": len(rows),
        }

    async def detect_anomalies(
        self,
        region_id: str,
        metric: str,
        threshold_std: float = 2.0,
    ) -> list[dict]:
        """
        Detect anomalous values in a time series.

        Uses z-score based detection.
        """
        import numpy as np

        query = select(Observation).where(
            Observation.region_id == region_id,
            Observation.metric == metric,
        )

        result = await self.db.execute(query)
        observations = result.scalars().all()

        if len(observations) < 10:
            return []

        values = np.array([obs.value for obs in observations])
        mean = np.mean(values)
        std = np.std(values)

        anomalies = []
        for obs in observations:
            z_score = (obs.value - mean) / (std + 1e-10)
            if abs(z_score) > threshold_std:
                anomalies.append(
                    {
                        "date": str(obs.date),
                        "value": obs.value,
                        "z_score": float(z_score),
                        "type": "high" if z_score > 0 else "low",
                    }
                )

        return sorted(anomalies, key=lambda x: abs(x["z_score"]), reverse=True)
