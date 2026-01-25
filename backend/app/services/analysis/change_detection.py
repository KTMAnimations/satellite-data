from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.observation import Observation

logger = get_logger(__name__)


class ChangeDetector:
    """
    Detect and analyze changes in satellite-derived metrics.

    Supports:
    - Before/after comparisons
    - Trend break detection
    - Event impact analysis
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compare_periods(
        self,
        region_id: str,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Compare two time periods for a region.

        Returns detailed comparison including statistical significance.
        """
        # Get data for period 1
        p1_query = select(Observation.metric, Observation.value).where(
            Observation.region_id == region_id,
            Observation.date >= period1_start,
            Observation.date <= period1_end,
        )
        if metrics:
            p1_query = p1_query.where(Observation.metric.in_(metrics))

        p1_result = await self.db.execute(p1_query)
        p1_data = {}
        for metric, value in p1_result.all():
            if metric not in p1_data:
                p1_data[metric] = []
            p1_data[metric].append(value)

        # Get data for period 2
        p2_query = select(Observation.metric, Observation.value).where(
            Observation.region_id == region_id,
            Observation.date >= period2_start,
            Observation.date <= period2_end,
        )
        if metrics:
            p2_query = p2_query.where(Observation.metric.in_(metrics))

        p2_result = await self.db.execute(p2_query)
        p2_data = {}
        for metric, value in p2_result.all():
            if metric not in p2_data:
                p2_data[metric] = []
            p2_data[metric].append(value)

        # Compare metrics
        comparisons = {}
        for metric in set(p1_data.keys()) | set(p2_data.keys()):
            p1_values = np.array(p1_data.get(metric, []))
            p2_values = np.array(p2_data.get(metric, []))

            if len(p1_values) == 0 or len(p2_values) == 0:
                continue

            p1_mean = float(np.mean(p1_values))
            p2_mean = float(np.mean(p2_values))
            p1_std = float(np.std(p1_values))
            p2_std = float(np.std(p2_values))

            abs_change = p2_mean - p1_mean
            pct_change = (abs_change / p1_mean * 100) if p1_mean != 0 else 0

            # Simple t-test for significance
            pooled_std = np.sqrt(
                (p1_std**2 / len(p1_values)) + (p2_std**2 / len(p2_values))
            )
            t_stat = abs_change / pooled_std if pooled_std > 0 else 0

            comparisons[metric] = {
                "period1": {
                    "mean": p1_mean,
                    "std": p1_std,
                    "count": len(p1_values),
                },
                "period2": {
                    "mean": p2_mean,
                    "std": p2_std,
                    "count": len(p2_values),
                },
                "change": {
                    "absolute": abs_change,
                    "percentage": pct_change,
                    "direction": "increase" if abs_change > 0 else "decrease",
                },
                "significance": {
                    "t_statistic": float(t_stat),
                    "is_significant": abs(t_stat) > 1.96,  # 95% confidence
                },
            }

        return {
            "region_id": region_id,
            "period1": {"start": str(period1_start), "end": str(period1_end)},
            "period2": {"start": str(period2_start), "end": str(period2_end)},
            "comparisons": comparisons,
        }

    async def detect_events(
        self,
        region_id: str,
        metric: str,
        start_date: date,
        end_date: date,
        window_size: int = 30,
        threshold: float = 2.0,
    ) -> list[dict]:
        """
        Detect sudden changes (events) in a metric time series.

        Uses a sliding window to identify points where the value
        deviates significantly from the recent trend.
        """
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

        if len(rows) < window_size + 1:
            return []

        events = []
        values = [r[1] for r in rows]
        dates = [r[0] for r in rows]

        for i in range(window_size, len(values)):
            window = values[i - window_size : i]
            window_mean = np.mean(window)
            window_std = np.std(window)

            if window_std == 0:
                continue

            z_score = (values[i] - window_mean) / window_std

            if abs(z_score) > threshold:
                events.append(
                    {
                        "date": str(dates[i]),
                        "value": values[i],
                        "expected": float(window_mean),
                        "deviation": float(values[i] - window_mean),
                        "z_score": float(z_score),
                        "type": "spike" if z_score > 0 else "drop",
                    }
                )

        return events

    async def analyze_covid_impact(
        self,
        region_id: str,
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze COVID-19 impact by comparing 2019 vs 2020 vs 2021.

        Specifically designed preset analysis.
        """
        results = {}

        for year_pair in [(2019, 2020), (2020, 2021), (2019, 2021)]:
            comparison = await self.compare_periods(
                region_id=region_id,
                period1_start=date(year_pair[0], 1, 1),
                period1_end=date(year_pair[0], 12, 31),
                period2_start=date(year_pair[1], 1, 1),
                period2_end=date(year_pair[1], 12, 31),
                metrics=metrics,
            )
            results[f"{year_pair[0]}_vs_{year_pair[1]}"] = comparison

        # Monthly breakdown for 2020
        monthly_2020 = []
        for month in range(1, 13):
            month_start = date(2020, month, 1)
            if month == 12:
                month_end = date(2020, 12, 31)
            else:
                month_end = date(2020, month + 1, 1)

            prev_year_start = date(2019, month, 1)
            if month == 12:
                prev_year_end = date(2019, 12, 31)
            else:
                prev_year_end = date(2019, month + 1, 1)

            comparison = await self.compare_periods(
                region_id=region_id,
                period1_start=prev_year_start,
                period1_end=prev_year_end,
                period2_start=month_start,
                period2_end=month_end,
                metrics=metrics,
            )
            monthly_2020.append({"month": month, "comparison": comparison})

        results["monthly_2020"] = monthly_2020

        return {
            "analysis_type": "covid_impact",
            "region_id": region_id,
            "results": results,
        }
