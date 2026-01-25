import numpy as np
from shapely.geometry import Polygon

from app.core.logging import get_logger
from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.satellite.base import SatelliteImagery

logger = get_logger(__name__)


class UrbanDensityExtractor(BaseFeatureExtractor):
    """
    Urban density extractor using built-up area indices.

    Can use multiple approaches:
    1. GHSL (Global Human Settlement Layer) data
    2. NDBI (Normalized Difference Built-up Index)
    3. Spectral unmixing for impervious surfaces

    NDBI = (SWIR - NIR) / (SWIR + NIR)
    """

    @property
    def metric_name(self) -> str:
        return "urban_density"

    @property
    def required_bands(self) -> list[str]:
        return ["B08", "B11"]  # NIR and SWIR1 for Sentinel-2

    @property
    def unit(self) -> str:
        return "ratio (0 to 1)"

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Calculate urban density using NDBI."""
        try:
            # Get band indices
            nir_idx = imagery.bands.index("B08") if "B08" in imagery.bands else 0
            swir_idx = imagery.bands.index("B11") if "B11" in imagery.bands else 1

            nir = imagery.data[nir_idx].astype(np.float32)
            swir = imagery.data[swir_idx].astype(np.float32)

            # Calculate NDBI
            denominator = swir + nir
            denominator[denominator == 0] = np.nan

            ndbi = (swir - nir) / denominator

            # Normalize to 0-1 range (NDBI ranges roughly -1 to 1)
            # Higher values indicate built-up areas
            urban_index = (ndbi + 1) / 2
            urban_index = np.clip(urban_index, 0, 1)

            # Apply geometry mask
            if geometry is not None:
                urban_index = self._mask_by_geometry(
                    urban_index, geometry, imagery.bounds
                )

            # Calculate urban fraction
            # Pixels with NDBI > 0 are typically built-up
            urban_threshold = 0.5  # Normalized threshold
            urban_pixels = np.sum(urban_index > urban_threshold)
            total_pixels = np.sum(~np.isnan(urban_index))
            urban_fraction = urban_pixels / total_pixels if total_pixels > 0 else 0

            mean_density = float(np.nanmean(urban_index))

            return FeatureResult(
                metric_name=self.metric_name,
                value=mean_density,
                raster=urban_index,
                bounds=imagery.bounds,
                date=imagery.date,
                unit=self.unit,
                metadata={
                    "urban_fraction": float(urban_fraction),
                    "urban_area_km2": self._calculate_area(
                        urban_pixels, imagery.resolution
                    ),
                    "total_area_km2": self._calculate_area(
                        total_pixels, imagery.resolution
                    ),
                    "threshold": urban_threshold,
                },
            )

        except Exception as e:
            logger.error("Urban density extraction failed", error=str(e))
            raise

    def _calculate_area(self, pixel_count: int, resolution: float) -> float:
        """Calculate area in km² from pixel count."""
        pixel_area_m2 = resolution * resolution
        return pixel_count * pixel_area_m2 / 1_000_000


class GHSLExtractor(BaseFeatureExtractor):
    """
    Global Human Settlement Layer data extractor.

    Uses pre-computed GHSL data which provides:
    - Built-up surface (GHS-BUILT)
    - Population distribution (GHS-POP)
    - Settlement model (GHS-SMOD)
    """

    @property
    def metric_name(self) -> str:
        return "ghsl_builtup"

    @property
    def required_bands(self) -> list[str]:
        return ["built"]  # GHSL built-up band

    @property
    def unit(self) -> str:
        return "m²/pixel"

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Extract built-up area from GHSL data."""
        if imagery.data.ndim == 2:
            built = imagery.data.astype(np.float32)
        else:
            built = imagery.data[0].astype(np.float32)

        if geometry is not None:
            built = self._mask_by_geometry(built, geometry, imagery.bounds)

        # Calculate statistics
        total_built = float(np.nansum(built))
        mean_built = float(np.nanmean(built))

        return FeatureResult(
            metric_name=self.metric_name,
            value=mean_built,
            raster=built,
            bounds=imagery.bounds,
            date=imagery.date,
            unit=self.unit,
            metadata={
                "total_built_area_m2": total_built,
                "total_built_area_km2": total_built / 1_000_000,
            },
        )


class UrbanGrowthAnalyzer:
    """Analyze urban growth over time."""

    def __init__(self):
        self.extractor = UrbanDensityExtractor()

    async def analyze_growth(
        self,
        imagery_list: list[SatelliteImagery],
        geometry: Polygon | None = None,
    ) -> dict:
        """
        Analyze urban growth from a time series of imagery.

        Returns:
            Dictionary with growth statistics and timeline
        """
        results = []
        for imagery in sorted(imagery_list, key=lambda x: x.date):
            result = await self.extractor.extract(imagery, geometry)
            results.append(
                {
                    "date": str(result.date),
                    "urban_density": result.value,
                    "urban_fraction": result.metadata.get("urban_fraction", 0),
                    "urban_area_km2": result.metadata.get("urban_area_km2", 0),
                }
            )

        # Calculate overall growth
        if len(results) >= 2:
            first = results[0]
            last = results[-1]
            growth_rate = (
                (last["urban_area_km2"] - first["urban_area_km2"])
                / first["urban_area_km2"]
                * 100
                if first["urban_area_km2"] > 0
                else 0
            )
            years = (
                int(last["date"][:4]) - int(first["date"][:4])
            ) or 1
            annual_growth = growth_rate / years
        else:
            growth_rate = 0
            annual_growth = 0

        return {
            "timeline": results,
            "summary": {
                "start_date": results[0]["date"] if results else None,
                "end_date": results[-1]["date"] if results else None,
                "total_growth_pct": growth_rate,
                "annual_growth_pct": annual_growth,
                "start_urban_km2": results[0]["urban_area_km2"] if results else 0,
                "end_urban_km2": results[-1]["urban_area_km2"] if results else 0,
            },
        }
