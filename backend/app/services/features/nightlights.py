import numpy as np
from shapely.geometry import Polygon

from app.core.logging import get_logger
from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.satellite.base import SatelliteImagery

logger = get_logger(__name__)


class NightlightsExtractor(BaseFeatureExtractor):
    """
    Nighttime lights intensity extractor.

    Uses VIIRS Day/Night Band (DNB) data to measure artificial light
    intensity as a proxy for human activity and population density.

    Higher values indicate more intense lighting, typically correlating
    with commercial areas, urban centers, and industrial zones.
    """

    @property
    def metric_name(self) -> str:
        return "nightlights"

    @property
    def required_bands(self) -> list[str]:
        return ["avg_rad"]  # VIIRS average radiance

    @property
    def unit(self) -> str:
        return "nW/cm²/sr"  # nano Watts per square centimeter per steradian

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Extract nighttime light intensity from VIIRS data."""
        try:
            # Get radiance band
            if imagery.data.ndim == 2:
                radiance = imagery.data.astype(np.float32)
            else:
                rad_idx = (
                    imagery.bands.index("avg_rad")
                    if "avg_rad" in imagery.bands
                    else 0
                )
                radiance = imagery.data[rad_idx].astype(np.float32)

            # Remove negative values (noise)
            radiance = np.clip(radiance, 0, None)

            # Apply geometry mask if provided
            if geometry is not None:
                radiance = self._mask_by_geometry(radiance, geometry, imagery.bounds)

            # Calculate statistics
            mean_radiance = float(np.nanmean(radiance))
            total_radiance = float(np.nansum(radiance))

            # Calculate lit area percentage (pixels above threshold)
            lit_threshold = 0.5  # nW/cm²/sr
            lit_pixels = np.sum(radiance > lit_threshold)
            total_pixels = np.sum(~np.isnan(radiance))
            lit_percentage = (lit_pixels / total_pixels * 100) if total_pixels > 0 else 0

            return FeatureResult(
                metric_name=self.metric_name,
                value=mean_radiance,
                raster=radiance,
                bounds=imagery.bounds,
                date=imagery.date,
                unit=self.unit,
                metadata={
                    "total_radiance": total_radiance,
                    "max_radiance": float(np.nanmax(radiance)),
                    "lit_area_pct": lit_percentage,
                    "lit_threshold": lit_threshold,
                },
            )

        except Exception as e:
            logger.error("Nightlights extraction failed", error=str(e))
            raise


class NightlightsChangeDetector:
    """
    Detect changes in nighttime lights between two periods.

    Useful for:
    - Seasonal migration patterns (snowbirds)
    - Event impacts (COVID, natural disasters)
    - Urban development
    """

    def __init__(self):
        self.extractor = NightlightsExtractor()

    async def detect_change(
        self,
        imagery_before: SatelliteImagery,
        imagery_after: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> dict:
        """
        Calculate change in nighttime lights between two periods.

        Returns:
            Dictionary with change statistics
        """
        before = await self.extractor.extract(imagery_before, geometry)
        after = await self.extractor.extract(imagery_after, geometry)

        # Calculate absolute and percentage change
        abs_change = after.value - before.value
        pct_change = (
            (abs_change / before.value * 100) if before.value != 0 else 0
        )

        # Calculate spatial change map if rasters available
        change_map = None
        if before.raster is not None and after.raster is not None:
            change_map = after.raster - before.raster

        return {
            "before": {
                "date": str(before.date),
                "mean_radiance": before.value,
                "metadata": before.metadata,
            },
            "after": {
                "date": str(after.date),
                "mean_radiance": after.value,
                "metadata": after.metadata,
            },
            "change": {
                "absolute": abs_change,
                "percentage": pct_change,
                "interpretation": self._interpret_change(pct_change),
            },
            "change_map": change_map,
        }

    def _interpret_change(self, pct_change: float) -> str:
        """Provide human-readable interpretation of change."""
        if pct_change > 20:
            return "Significant increase in activity"
        elif pct_change > 5:
            return "Moderate increase in activity"
        elif pct_change > -5:
            return "Relatively stable activity"
        elif pct_change > -20:
            return "Moderate decrease in activity"
        else:
            return "Significant decrease in activity"
