from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)


class PDFReportGenerator:
    """Generate PDF reports for satellite analysis results."""

    def __init__(self):
        self.settings = get_settings()
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self) -> None:
        """Set up custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                spaceAfter=30,
                alignment=1,  # Center
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="BodyText",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=6,
                spaceAfter=6,
            )
        )

    async def generate(
        self,
        region_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        metrics: list[str] | None = None,
        include_charts: bool = True,
        include_maps: bool = True,
        title: str | None = None,
        description: str | None = None,
        export_id: str | None = None,
    ) -> str:
        """
        Generate a PDF report for a region.

        Returns:
            Path to the generated PDF file
        """
        from sqlalchemy import select
        from app.models.region import Region
        from app.models.observation import Observation

        async with get_db_context() as db:
            # Get region info
            result = await db.execute(select(Region).where(Region.id == region_id))
            region = result.scalar_one_or_none()

            if not region:
                raise ValueError(f"Region {region_id} not found")

            # Get observations
            obs_query = select(Observation).where(Observation.region_id == region_id)
            if start_date:
                obs_query = obs_query.where(Observation.date >= start_date)
            if end_date:
                obs_query = obs_query.where(Observation.date <= end_date)
            if metrics:
                obs_query = obs_query.where(Observation.metric.in_(metrics))

            obs_result = await db.execute(obs_query.order_by(Observation.date))
            observations = obs_result.scalars().all()

        # Generate PDF
        filename = f"{export_id}.pdf" if export_id else f"{region_id}_report.pdf"
        output_path = Path(self.settings.exports_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        story = []

        # Title
        report_title = title or f"Migration Analysis Report: {region.name}"
        story.append(Paragraph(report_title, self.styles["ReportTitle"]))
        story.append(Spacer(1, 12))

        # Period info
        if start_date and end_date:
            period_text = f"Analysis Period: {start_date} to {end_date}"
        else:
            period_text = "Analysis Period: Full available data"
        story.append(Paragraph(period_text, self.styles["Normal"]))
        story.append(Spacer(1, 24))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))
        summary = description or self._generate_summary(region, observations)
        story.append(Paragraph(summary, self.styles["BodyText"]))
        story.append(Spacer(1, 12))

        # Metrics Table
        story.append(Paragraph("Key Metrics", self.styles["SectionHeader"]))
        metrics_table = self._create_metrics_table(observations)
        story.append(metrics_table)
        story.append(Spacer(1, 12))

        # Seasonal Comparison (if applicable)
        seasonal_data = self._calculate_seasonal_data(observations)
        if seasonal_data:
            story.append(
                Paragraph("Seasonal Comparison", self.styles["SectionHeader"])
            )
            seasonal_table = self._create_seasonal_table(seasonal_data)
            story.append(seasonal_table)
            story.append(Spacer(1, 12))

        # Methodology
        story.append(Paragraph("Methodology", self.styles["SectionHeader"]))
        methodology_text = self._get_methodology_text()
        story.append(Paragraph(methodology_text, self.styles["BodyText"]))

        # Build PDF
        doc.build(story)

        logger.info("PDF report generated", path=str(output_path))
        return str(output_path)

    def _generate_summary(self, region: Any, observations: list) -> str:
        """Generate an executive summary based on the data."""
        if not observations:
            return "No data available for this region and time period."

        # Calculate basic statistics
        by_metric = {}
        for obs in observations:
            if obs.metric not in by_metric:
                by_metric[obs.metric] = []
            by_metric[obs.metric].append(obs.value)

        summary_parts = [f"Analysis of {region.name} reveals the following patterns:"]

        for metric, values in by_metric.items():
            import numpy as np

            avg = np.mean(values)
            trend = "stable"
            if len(values) > 1:
                if values[-1] > values[0] * 1.1:
                    trend = "increasing"
                elif values[-1] < values[0] * 0.9:
                    trend = "decreasing"

            summary_parts.append(
                f"- {metric.replace('_', ' ').title()}: Average of {avg:.2f}, trend is {trend}"
            )

        return " ".join(summary_parts)

    def _create_metrics_table(self, observations: list) -> Table:
        """Create a table of metric statistics."""
        import numpy as np

        # Group by metric
        by_metric = {}
        for obs in observations:
            if obs.metric not in by_metric:
                by_metric[obs.metric] = []
            by_metric[obs.metric].append(obs.value)

        # Create table data
        data = [["Metric", "Mean", "Min", "Max", "Std Dev", "Count"]]

        for metric, values in by_metric.items():
            data.append(
                [
                    metric.replace("_", " ").title(),
                    f"{np.mean(values):.2f}",
                    f"{np.min(values):.2f}",
                    f"{np.max(values):.2f}",
                    f"{np.std(values):.2f}",
                    str(len(values)),
                ]
            )

        table = Table(data, colWidths=[1.5 * inch, inch, inch, inch, inch, 0.75 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        return table

    def _calculate_seasonal_data(self, observations: list) -> dict | None:
        """Calculate seasonal averages from observations."""
        import numpy as np

        winter_obs = [o for o in observations if o.date.month in [12, 1, 2]]
        summer_obs = [o for o in observations if o.date.month in [6, 7, 8]]

        if not winter_obs or not summer_obs:
            return None

        metrics = set(o.metric for o in observations)
        seasonal = {}

        for metric in metrics:
            w_values = [o.value for o in winter_obs if o.metric == metric]
            s_values = [o.value for o in summer_obs if o.metric == metric]

            if w_values and s_values:
                w_avg = np.mean(w_values)
                s_avg = np.mean(s_values)
                change = ((w_avg - s_avg) / s_avg * 100) if s_avg != 0 else 0

                seasonal[metric] = {
                    "winter": w_avg,
                    "summer": s_avg,
                    "change_pct": change,
                }

        return seasonal if seasonal else None

    def _create_seasonal_table(self, seasonal_data: dict) -> Table:
        """Create a seasonal comparison table."""
        data = [["Metric", "Winter Avg", "Summer Avg", "Change (%)"]]

        for metric, values in seasonal_data.items():
            change_str = f"{values['change_pct']:+.1f}%"
            data.append(
                [
                    metric.replace("_", " ").title(),
                    f"{values['winter']:.2f}",
                    f"{values['summer']:.2f}",
                    change_str,
                ]
            )

        table = Table(data, colWidths=[1.5 * inch, 1.25 * inch, 1.25 * inch, 1.25 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        return table

    def _get_methodology_text(self) -> str:
        """Return methodology description."""
        return """
        This analysis uses satellite-derived proxy metrics to estimate population and
        activity patterns. Data sources include Sentinel-2 optical imagery (10m resolution)
        and VIIRS nighttime lights (375m resolution).

        Key metrics:
        - NDVI (Normalized Difference Vegetation Index): Measures vegetation density
        - Nighttime Lights: Proxy for population density and economic activity
        - Urban Density: Built-up area estimation using spectral indices

        Limitations: At 10m resolution, individual vehicles cannot be detected.
        All metrics are proxy-based correlations, not direct measurements.
        """
