from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.observation import Observation
from app.models.region import Region

logger = get_logger(__name__)


class MigrationAnalyzer:
    """
    Analyze migration patterns using proxy metrics.

    Detects seasonal population shifts by analyzing:
    - Nighttime light intensity changes
    - Urban activity patterns
    - Correlated changes between regions
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_seasonal_migration(
        self,
        region_id: str,
        year: int,
    ) -> dict[str, Any]:
        """
        Analyze seasonal migration patterns for a region.

        Compares winter vs summer activity to detect snowbird patterns.
        """
        # Get winter data (Dec-Feb)
        winter_query = (
            select(
                Observation.metric,
                func.avg(Observation.value).label("avg"),
                func.stddev(Observation.value).label("std"),
                func.count().label("count"),
            )
            .where(
                Observation.region_id == region_id,
                func.extract("month", Observation.date).in_([12, 1, 2]),
            )
            .group_by(Observation.metric)
        )

        # Get summer data (Jun-Aug)
        summer_query = (
            select(
                Observation.metric,
                func.avg(Observation.value).label("avg"),
                func.stddev(Observation.value).label("std"),
                func.count().label("count"),
            )
            .where(
                Observation.region_id == region_id,
                func.extract("year", Observation.date) == year,
                func.extract("month", Observation.date).in_([6, 7, 8]),
            )
            .group_by(Observation.metric)
        )

        winter_result = await self.db.execute(winter_query)
        summer_result = await self.db.execute(summer_query)

        winter_data = {r[0]: {"avg": r[1], "std": r[2], "count": r[3]} for r in winter_result.all()}
        summer_data = {r[0]: {"avg": r[1], "std": r[2], "count": r[3]} for r in summer_result.all()}

        # Analyze patterns
        patterns = {}
        for metric in set(winter_data.keys()) | set(summer_data.keys()):
            w = winter_data.get(metric, {})
            s = summer_data.get(metric, {})

            w_avg = float(w.get("avg", 0) or 0)
            s_avg = float(s.get("avg", 0) or 0)

            if w_avg != 0:
                change_pct = ((w_avg - s_avg) / s_avg * 100) if s_avg != 0 else 0
            else:
                change_pct = 0

            patterns[metric] = {
                "winter_avg": w_avg,
                "summer_avg": s_avg,
                "winter_increase_pct": change_pct,
            }

        # Determine migration type
        nightlights_change = patterns.get("nightlights", {}).get("winter_increase_pct", 0)

        if nightlights_change > 15:
            migration_type = "strong_winter_destination"
        elif nightlights_change > 5:
            migration_type = "moderate_winter_destination"
        elif nightlights_change < -15:
            migration_type = "strong_summer_destination"
        elif nightlights_change < -5:
            migration_type = "moderate_summer_destination"
        else:
            migration_type = "stable"

        return {
            "region_id": region_id,
            "year": year,
            "migration_type": migration_type,
            "patterns": patterns,
            "interpretation": self._interpret_migration(migration_type),
        }

    def _interpret_migration(self, migration_type: str) -> str:
        """Provide human-readable interpretation."""
        interpretations = {
            "strong_winter_destination": (
                "This region shows significant population increase during winter months, "
                "consistent with snowbird migration patterns. Activity levels are notably "
                "higher December through February."
            ),
            "moderate_winter_destination": (
                "This region shows moderate population increase during winter months, "
                "suggesting some seasonal migration inflow."
            ),
            "strong_summer_destination": (
                "This region shows significant population increase during summer months, "
                "consistent with vacation destination or academic patterns."
            ),
            "moderate_summer_destination": (
                "This region shows moderate population increase during summer months."
            ),
            "stable": (
                "This region shows relatively stable activity throughout the year "
                "with no strong seasonal migration patterns."
            ),
        }
        return interpretations.get(migration_type, "Pattern analysis complete.")

    async def find_correlated_regions(
        self,
        source_region_id: str,
        candidate_region_ids: list[str],
        metric: str = "nightlights",
        lag_months: int = 1,
    ) -> list[dict]:
        """
        Find regions with inversely correlated activity patterns.

        Useful for identifying migration corridors (e.g., NYC ↔ Florida).
        """
        # Get source region time series
        source_query = (
            select(
                func.to_char(Observation.date, "YYYY-MM").label("month"),
                func.avg(Observation.value).label("value"),
            )
            .where(
                Observation.region_id == source_region_id,
                Observation.metric == metric,
            )
            .group_by(func.to_char(Observation.date, "YYYY-MM"))
            .order_by(func.to_char(Observation.date, "YYYY-MM"))
        )

        source_result = await self.db.execute(source_query)
        source_series = {r[0]: r[1] for r in source_result.all()}

        correlations = []

        for candidate_id in candidate_region_ids:
            if candidate_id == source_region_id:
                continue

            # Get candidate region time series
            candidate_query = (
                select(
                    func.to_char(Observation.date, "YYYY-MM").label("month"),
                    func.avg(Observation.value).label("value"),
                )
                .where(
                    Observation.region_id == candidate_id,
                    Observation.metric == metric,
                )
                .group_by(func.to_char(Observation.date, "YYYY-MM"))
                .order_by(func.to_char(Observation.date, "YYYY-MM"))
            )

            candidate_result = await self.db.execute(candidate_query)
            candidate_series = {r[0]: r[1] for r in candidate_result.all()}

            # Calculate correlation
            common_months = sorted(set(source_series.keys()) & set(candidate_series.keys()))

            if len(common_months) < 6:
                continue

            source_values = np.array([source_series[m] for m in common_months])
            candidate_values = np.array([candidate_series[m] for m in common_months])

            # Pearson correlation
            correlation = np.corrcoef(source_values, candidate_values)[0, 1]

            correlations.append(
                {
                    "region_id": candidate_id,
                    "correlation": float(correlation),
                    "is_inverse": correlation < -0.3,
                    "data_points": len(common_months),
                }
            )

        # Sort by inverse correlation (most negative first)
        correlations.sort(key=lambda x: x["correlation"])

        return correlations

    async def generate_migration_flow(
        self,
        origin_regions: list[str],
        destination_regions: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """
        Generate migration flow data for visualization.

        Creates flow intensity values between origin and destination regions.
        """
        flows = []

        for origin_id in origin_regions:
            # Get origin region info
            origin_result = await self.db.execute(
                select(Region).where(Region.id == origin_id)
            )
            origin = origin_result.scalar_one_or_none()
            if not origin:
                continue

            for dest_id in destination_regions:
                if origin_id == dest_id:
                    continue

                # Get destination region info
                dest_result = await self.db.execute(
                    select(Region).where(Region.id == dest_id)
                )
                dest = dest_result.scalar_one_or_none()
                if not dest:
                    continue

                # Calculate flow intensity based on correlated activity changes
                origin_change = await self._calculate_period_change(
                    origin_id, "nightlights", start_date, end_date
                )
                dest_change = await self._calculate_period_change(
                    dest_id, "nightlights", start_date, end_date
                )

                # Flow intensity is higher when origin decreases and dest increases
                flow_intensity = max(0, dest_change - origin_change) / 100

                if flow_intensity > 0.1:  # Only include significant flows
                    flows.append(
                        {
                            "origin": {
                                "id": origin_id,
                                "name": origin.name,
                            },
                            "destination": {
                                "id": dest_id,
                                "name": dest.name,
                            },
                            "intensity": float(flow_intensity),
                            "origin_change_pct": float(origin_change),
                            "destination_change_pct": float(dest_change),
                        }
                    )

        # Sort by intensity
        flows.sort(key=lambda x: x["intensity"], reverse=True)

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "flows": flows,
        }

    async def _calculate_period_change(
        self,
        region_id: str,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> float:
        """Calculate percentage change in metric over a period."""
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
            return 0.0

        first_value = rows[0][1]
        last_value = rows[-1][1]

        if first_value == 0:
            return 0.0

        return ((last_value - first_value) / first_value) * 100
