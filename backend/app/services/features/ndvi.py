import numpy as np
from shapely.geometry import Polygon

from app.core.logging import get_logger
from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.satellite.base import SatelliteImagery

logger = get_logger(__name__)


class NDVIExtractor(BaseFeatureExtractor):
    """
    Normalized Difference Vegetation Index extractor.

    NDVI = (NIR - Red) / (NIR + Red)

    Values range from -1 to 1:
    - High values (0.6-0.9): Dense vegetation
    - Moderate values (0.2-0.5): Sparse vegetation
    - Low values (-0.1 to 0.1): Bare soil, rock, sand
    - Negative values: Water, snow, clouds
    """

    @property
    def metric_name(self) -> str:
        return "ndvi"

    @property
    def required_bands(self) -> list[str]:
        return ["B4", "B8"]  # Red and NIR for Sentinel-2

    @property
    def unit(self) -> str:
        return "index (-1 to 1)"

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Calculate NDVI from satellite imagery."""
        try:
            # Get band indices
            red_idx = imagery.bands.index("B4") if "B4" in imagery.bands else 0
            nir_idx = imagery.bands.index("B8") if "B8" in imagery.bands else 1

            red = imagery.data[red_idx].astype(np.float32)
            nir = imagery.data[nir_idx].astype(np.float32)

            # Avoid division by zero
            denominator = nir + red
            denominator[denominator == 0] = np.nan

            ndvi = (nir - red) / denominator

            # Clip to valid range
            ndvi = np.clip(ndvi, -1, 1)

            # Apply geometry mask if provided
            if geometry is not None:
                ndvi = self._mask_by_geometry(ndvi, geometry, imagery.bounds)

            # Calculate aggregate value (mean of valid pixels)
            mean_ndvi = float(np.nanmean(ndvi))

            return FeatureResult(
                metric_name=self.metric_name,
                value=mean_ndvi,
                raster=ndvi,
                bounds=imagery.bounds,
                date=imagery.date,
                unit=self.unit,
                metadata={
                    "min": float(np.nanmin(ndvi)),
                    "max": float(np.nanmax(ndvi)),
                    "std": float(np.nanstd(ndvi)),
                    "valid_pixels": int(np.sum(~np.isnan(ndvi))),
                },
            )

        except Exception as e:
            logger.error("NDVI extraction failed", error=str(e))
            raise


class EVIExtractor(BaseFeatureExtractor):
    """
    Enhanced Vegetation Index extractor.

    EVI is more sensitive in high biomass regions and reduces
    atmospheric influences.

    EVI = G * (NIR - Red) / (NIR + C1 * Red - C2 * Blue + L)

    Where G=2.5, C1=6, C2=7.5, L=1
    """

    @property
    def metric_name(self) -> str:
        return "evi"

    @property
    def required_bands(self) -> list[str]:
        return ["B2", "B4", "B8"]  # Blue, Red, NIR

    @property
    def unit(self) -> str:
        return "index (-1 to 1)"

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Calculate EVI from satellite imagery."""
        # EVI parameters
        G = 2.5
        C1 = 6.0
        C2 = 7.5
        L = 1.0

        blue_idx = imagery.bands.index("B2") if "B2" in imagery.bands else 0
        red_idx = imagery.bands.index("B4") if "B4" in imagery.bands else 1
        nir_idx = imagery.bands.index("B8") if "B8" in imagery.bands else 2

        blue = imagery.data[blue_idx].astype(np.float32) / 10000.0
        red = imagery.data[red_idx].astype(np.float32) / 10000.0
        nir = imagery.data[nir_idx].astype(np.float32) / 10000.0

        denominator = nir + C1 * red - C2 * blue + L
        denominator[denominator == 0] = np.nan

        evi = G * (nir - red) / denominator
        evi = np.clip(evi, -1, 1)

        if geometry is not None:
            evi = self._mask_by_geometry(evi, geometry, imagery.bounds)

        mean_evi = float(np.nanmean(evi))

        return FeatureResult(
            metric_name=self.metric_name,
            value=mean_evi,
            raster=evi,
            bounds=imagery.bounds,
            date=imagery.date,
            unit=self.unit,
            metadata={
                "min": float(np.nanmin(evi)),
                "max": float(np.nanmax(evi)),
                "std": float(np.nanstd(evi)),
            },
        )
