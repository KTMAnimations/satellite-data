import csv
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.models.observation import Observation
from app.models.region import Region

logger = get_logger(__name__)


class CSVExporter:
    """Export observation data to CSV format."""

    def __init__(self):
        self.settings = get_settings()

    async def export(
        self,
        region_ids: list[str] | None = None,
        metrics: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include_metadata: bool = False,
        export_id: str | None = None,
    ) -> str:
        """
        Export observations to CSV.

        Returns:
            Path to the generated CSV file
        """
        async with get_db_context() as db:
            # Build query
            query = select(
                Observation.date,
                Region.name.label("region"),
                Observation.metric,
                Observation.value,
            ).join(Region, Observation.region_id == Region.id)

            if region_ids:
                query = query.where(Observation.region_id.in_(region_ids))
            if metrics:
                query = query.where(Observation.metric.in_(metrics))
            if start_date:
                query = query.where(Observation.date >= start_date)
            if end_date:
                query = query.where(Observation.date <= end_date)

            query = query.order_by(Observation.date, Region.name, Observation.metric)

            result = await db.execute(query)
            rows = result.all()

        # Generate CSV
        filename = f"{export_id}.csv" if export_id else "export.csv"
        output_path = Path(self.settings.exports_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            header = ["date", "region", "metric", "value"]
            if include_metadata:
                header.append("unit")
            writer.writerow(header)

            # Data
            unit_map = {
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

            for row in rows:
                csv_row = [str(row[0]), row[1], row[2], f"{row[3]:.4f}"]
                if include_metadata:
                    csv_row.append(unit_map.get(row[2], "unknown"))
                writer.writerow(csv_row)

        logger.info("CSV export complete", path=str(output_path), rows=len(rows))
        return str(output_path)

    async def export_comparison(
        self,
        region_id: str,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
    ) -> str:
        """Export a period comparison to CSV."""
        async with get_db_context() as db:
            # Get region name
            region_result = await db.execute(
                select(Region.name).where(Region.id == region_id)
            )
            region_name = region_result.scalar_one()

            # Get data for both periods
            p1_query = (
                select(Observation.metric, Observation.value)
                .where(
                    Observation.region_id == region_id,
                    Observation.date >= period1_start,
                    Observation.date <= period1_end,
                )
            )
            p2_query = (
                select(Observation.metric, Observation.value)
                .where(
                    Observation.region_id == region_id,
                    Observation.date >= period2_start,
                    Observation.date <= period2_end,
                )
            )

            p1_result = await db.execute(p1_query)
            p2_result = await db.execute(p2_query)

            # Aggregate by metric
            import numpy as np

            p1_data = {}
            for metric, value in p1_result.all():
                if metric not in p1_data:
                    p1_data[metric] = []
                p1_data[metric].append(value)

            p2_data = {}
            for metric, value in p2_result.all():
                if metric not in p2_data:
                    p2_data[metric] = []
                p2_data[metric].append(value)

        # Generate comparison CSV
        output_path = Path(self.settings.exports_dir) / f"{region_id}_comparison.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "metric",
                    f"period1_avg ({period1_start} to {period1_end})",
                    f"period2_avg ({period2_start} to {period2_end})",
                    "change_absolute",
                    "change_percent",
                ]
            )

            all_metrics = set(p1_data.keys()) | set(p2_data.keys())
            for metric in sorted(all_metrics):
                p1_values = p1_data.get(metric, [])
                p2_values = p2_data.get(metric, [])

                p1_avg = np.mean(p1_values) if p1_values else 0
                p2_avg = np.mean(p2_values) if p2_values else 0

                change_abs = p2_avg - p1_avg
                change_pct = (change_abs / p1_avg * 100) if p1_avg != 0 else 0

                writer.writerow(
                    [
                        metric,
                        f"{p1_avg:.4f}",
                        f"{p2_avg:.4f}",
                        f"{change_abs:.4f}",
                        f"{change_pct:.2f}%",
                    ]
                )

        logger.info("Comparison CSV export complete", path=str(output_path))
        return str(output_path)

    async def export_time_series(
        self,
        region_id: str,
        metric: str,
        start_date: date | None = None,
        end_date: date | None = None,
        granularity: str = "monthly",
    ) -> str:
        """Export a time series for a specific metric."""
        async with get_db_context() as db:
            # Get region name
            region_result = await db.execute(
                select(Region.name).where(Region.id == region_id)
            )
            region_name = region_result.scalar_one()

            # Get observations
            query = (
                select(Observation.date, Observation.value)
                .where(
                    Observation.region_id == region_id,
                    Observation.metric == metric,
                )
                .order_by(Observation.date)
            )

            if start_date:
                query = query.where(Observation.date >= start_date)
            if end_date:
                query = query.where(Observation.date <= end_date)

            result = await db.execute(query)
            rows = result.all()

        # Aggregate if needed
        if granularity == "monthly":
            from collections import defaultdict
            import numpy as np

            monthly = defaultdict(list)
            for obs_date, value in rows:
                key = obs_date.strftime("%Y-%m")
                monthly[key].append(value)

            aggregated = [(k, np.mean(v)) for k, v in sorted(monthly.items())]
        else:
            aggregated = [(str(d), v) for d, v in rows]

        # Write CSV
        output_path = (
            Path(self.settings.exports_dir) / f"{region_id}_{metric}_timeseries.csv"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "value"])
            for date_str, value in aggregated:
                writer.writerow([date_str, f"{value:.4f}"])

        logger.info(
            "Time series CSV export complete",
            path=str(output_path),
            rows=len(aggregated),
        )
        return str(output_path)
