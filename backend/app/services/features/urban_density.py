from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import numpy as np
from shapely.geometry import Polygon

from app.core.logging import get_logger
from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.satellite.base import SatelliteImagery

if TYPE_CHECKING:
    from app.services.satellite.gee_client import GHSLClient

logger = get_logger(__name__)


class UrbanDensityExtractor(BaseFeatureExtractor):
    """
    Urban density extractor using GHSL (Global Human Settlement Layer) data.

    Primary data source: GHSL pre-computed built-up surface data
    - JRC/GHSL/P2023A/GHS_BUILT_S: Built-up surface area (100m, 1975-2030)
    - JRC/GHSL/P2023A/GHS_SMOD: Settlement model (1km, urban-rural classification)

    Fallback: NDBI (Normalized Difference Built-up Index) when GHSL unavailable
    NDBI = (SWIR - NIR) / (SWIR + NIR)
    """

    # GHSL pixel size is 100m x 100m = 10,000 m²
    GHSL_PIXEL_AREA_M2 = 10000

    def __init__(self, ghsl_client: GHSLClient | None = None):
        """Initialize the extractor.

        Args:
            ghsl_client: Optional GHSLClient instance for GHSL data access.
                        If not provided, will be created on first use.
        """
        self._ghsl_client = ghsl_client
        self._ghsl_client_initialized = False

    @property
    def metric_name(self) -> str:
        return "urban_density"

    @property
    def required_bands(self) -> list[str]:
        # Required for NDBI fallback
        return ["B8", "B11"]  # NIR and SWIR1 for Sentinel-2

    @property
    def unit(self) -> str:
        return "ratio (0 to 1)"

    async def _get_ghsl_client(self) -> GHSLClient:
        """Lazy initialization of GHSL client."""
        if self._ghsl_client is None:
            from app.services.satellite.gee_client import GHSLClient
            self._ghsl_client = GHSLClient()

        if not self._ghsl_client_initialized:
            await self._ghsl_client.initialize()
            self._ghsl_client_initialized = True

        return self._ghsl_client

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Extract urban density, using GHSL data with NDBI fallback.

        The method first attempts to use GHSL pre-computed built-up surface data,
        which is more accurate than spectral indices. If GHSL data is unavailable
        for the requested date/location, it falls back to NDBI calculation.

        Args:
            imagery: Input satellite imagery (used for bounds, date, and NDBI fallback)
            geometry: Optional polygon to mask the result

        Returns:
            FeatureResult with urban_density, urban_fraction, urban_area_km2, etc.
        """
        # Try GHSL first
        try:
            result = await self._extract_from_ghsl(imagery, geometry)
            if result is not None:
                logger.info(
                    "Urban density extracted using GHSL",
                    date=str(imagery.date),
                    source="GHSL",
                )
                return result
        except Exception as e:
            logger.warning(
                "GHSL extraction failed, falling back to NDBI",
                error=str(e),
            )

        # Fall back to NDBI
        logger.info(
            "Using NDBI fallback for urban density",
            date=str(imagery.date),
            source="NDBI",
        )
        return await self._extract_from_ndbi(imagery, geometry)

    async def _extract_from_ghsl(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult | None:
        """Extract urban density from GHSL built-up surface data.

        Args:
            imagery: Reference imagery for bounds and date
            geometry: Optional polygon to mask the result

        Returns:
            FeatureResult or None if GHSL data unavailable
        """
        # Create geometry from imagery bounds if not provided
        if geometry is None:
            west, south, east, north = imagery.bounds
            geometry = Polygon([
                (west, south), (east, south),
                (east, north), (west, north), (west, south)
            ])

        ghsl_client = await self._get_ghsl_client()

        # Get GHSL built-up surface data
        ghsl_imagery = await ghsl_client.get_ghsl_built_surface(
            geometry=geometry,
            target_date=imagery.date,
            resolution=100,  # Native GHSL resolution
        )

        if ghsl_imagery is None:
            return None

        # Get the built-up surface data (m² per pixel)
        built_surface = ghsl_imagery.data[0].astype(np.float32)

        # Apply geometry mask if provided
        if geometry is not None:
            built_surface = self._mask_by_geometry(
                built_surface, geometry, ghsl_imagery.bounds
            )

        # Calculate urban fraction
        # Each GHSL pixel represents a 100m x 100m area (10,000 m²)
        # built_surface value is the built-up area in m² within each pixel
        # Urban fraction per pixel = built_surface / pixel_area
        pixel_area_m2 = self.GHSL_PIXEL_AREA_M2
        urban_fraction_raster = np.clip(built_surface / pixel_area_m2, 0, 1)

        # Statistics
        valid_pixels = ~np.isnan(urban_fraction_raster)
        total_pixels = int(np.sum(valid_pixels))

        if total_pixels == 0:
            return None

        # Mean urban density (fraction of built-up area)
        mean_density = float(np.nanmean(urban_fraction_raster))

        # Total built-up area
        total_built_m2 = float(np.nansum(built_surface))
        total_built_km2 = total_built_m2 / 1_000_000

        # Total analysis area
        total_area_km2 = (total_pixels * pixel_area_m2) / 1_000_000

        # Urban fraction (area-weighted)
        urban_fraction = total_built_km2 / total_area_km2 if total_area_km2 > 0 else 0

        # Count pixels above threshold for urban classification
        urban_threshold = 0.25  # 25% built-up = urban
        urban_pixel_count = int(np.sum(urban_fraction_raster > urban_threshold))

        # Also get settlement classification if available
        settlement_info = await self._get_settlement_classification(
            ghsl_client, geometry, imagery.date
        )

        return FeatureResult(
            metric_name=self.metric_name,
            value=mean_density,
            raster=urban_fraction_raster,
            bounds=ghsl_imagery.bounds,
            date=imagery.date,
            unit=self.unit,
            metadata={
                "source": "GHSL",
                "dataset": "JRC/GHSL/P2023A/GHS_BUILT_S",
                "ghsl_epoch": ghsl_imagery.metadata.get("epoch") if ghsl_imagery.metadata else None,
                "urban_fraction": float(urban_fraction),
                "urban_area_km2": float(total_built_km2),
                "total_area_km2": float(total_area_km2),
                "urban_pixel_count": urban_pixel_count,
                "total_pixel_count": total_pixels,
                "threshold": urban_threshold,
                "settlement_classification": settlement_info,
            },
        )

    async def _get_settlement_classification(
        self,
        ghsl_client: GHSLClient,
        geometry: Polygon,
        target_date: date,
    ) -> dict | None:
        """Get settlement classification breakdown from GHSL SMOD."""
        try:
            smod_imagery = await ghsl_client.get_ghsl_settlement_model(
                geometry=geometry,
                target_date=target_date,
            )

            if smod_imagery is None:
                return None

            smod_data = smod_imagery.data[0]
            valid_pixels = ~np.isnan(smod_data) & (smod_data > 0)
            total_valid = np.sum(valid_pixels)

            if total_valid == 0:
                return None

            # Calculate percentage for each settlement class
            class_names = {
                30: "urban_centre",
                23: "dense_urban_cluster",
                22: "semi_dense_urban_cluster",
                21: "suburban_peri_urban",
                13: "rural_cluster",
                12: "low_density_rural",
                11: "very_low_density_rural",
                10: "water",
            }

            classification = {}
            for code, name in class_names.items():
                count = np.sum(smod_data == code)
                classification[name] = float(count / total_valid) if total_valid > 0 else 0

            # Dominant class
            dominant_code = int(np.nanmedian(smod_data[valid_pixels]))
            classification["dominant_class"] = class_names.get(dominant_code, "unknown")

            return classification

        except Exception as e:
            logger.warning("Failed to get SMOD classification", error=str(e))
            return None

    async def _extract_from_ndbi(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Fallback: Calculate urban density using NDBI from satellite imagery.

        NDBI = (SWIR - NIR) / (SWIR + NIR)

        Args:
            imagery: Input Sentinel-2 imagery with B8 (NIR) and B11 (SWIR) bands
            geometry: Optional polygon to mask the result

        Returns:
            FeatureResult with NDBI-based urban density metrics
        """
        try:
            # Get band indices
            nir_idx = imagery.bands.index("B8") if "B8" in imagery.bands else 0
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
            urban_pixels = int(np.sum(urban_index > urban_threshold))
            total_pixels = int(np.sum(~np.isnan(urban_index)))
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
                    "source": "NDBI",
                    "method": "Normalized Difference Built-up Index",
                    "urban_fraction": float(urban_fraction),
                    "urban_area_km2": self._calculate_area(
                        urban_pixels, imagery.resolution
                    ),
                    "total_area_km2": self._calculate_area(
                        total_pixels, imagery.resolution
                    ),
                    "urban_pixel_count": urban_pixels,
                    "total_pixel_count": total_pixels,
                    "threshold": urban_threshold,
                },
            )

        except Exception as e:
            logger.error("NDBI urban density extraction failed", error=str(e))
            raise

    def _calculate_area(self, pixel_count: int, resolution: float) -> float:
        """Calculate area in km² from pixel count."""
        pixel_area_m2 = resolution * resolution
        return pixel_count * pixel_area_m2 / 1_000_000


class GHSLExtractor(BaseFeatureExtractor):
    """
    Global Human Settlement Layer data extractor.

    Uses pre-computed GHSL data from Google Earth Engine:
    - JRC/GHSL/P2023A/GHS_BUILT_S: Built-up surface (100m, 1975-2030)
    - JRC/GHSL/P2023A/GHS_SMOD: Settlement model (urban-rural classification)

    This extractor can work with:
    1. Pre-loaded GHSL imagery (SatelliteImagery with built_surface band)
    2. Any imagery + geometry (will fetch GHSL data from GEE)
    """

    def __init__(self, ghsl_client: GHSLClient | None = None):
        """Initialize the extractor.

        Args:
            ghsl_client: Optional GHSLClient instance. Created on demand if not provided.
        """
        self._ghsl_client = ghsl_client
        self._ghsl_client_initialized = False

    @property
    def metric_name(self) -> str:
        return "ghsl_builtup"

    @property
    def required_bands(self) -> list[str]:
        return ["built_surface"]  # GHSL built-up band

    @property
    def unit(self) -> str:
        return "m²/pixel"

    async def _get_ghsl_client(self) -> GHSLClient:
        """Lazy initialization of GHSL client."""
        if self._ghsl_client is None:
            from app.services.satellite.gee_client import GHSLClient
            self._ghsl_client = GHSLClient()

        if not self._ghsl_client_initialized:
            await self._ghsl_client.initialize()
            self._ghsl_client_initialized = True

        return self._ghsl_client

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """Extract built-up area from GHSL data.

        If the provided imagery is already GHSL data (has built_surface band),
        it will be used directly. Otherwise, GHSL data will be fetched from GEE.

        Args:
            imagery: Input imagery (GHSL or reference for bounds/date)
            geometry: Optional polygon to mask the result

        Returns:
            FeatureResult with built-up area metrics
        """
        # Check if imagery is already GHSL data
        if "built_surface" in imagery.bands or imagery.source.startswith("GHSL"):
            built = imagery.data[0].astype(np.float32) if imagery.data.ndim == 3 else imagery.data.astype(np.float32)
            ghsl_metadata = imagery.metadata or {}
        else:
            # Fetch GHSL data from GEE
            if geometry is None:
                west, south, east, north = imagery.bounds
                geometry = Polygon([
                    (west, south), (east, south),
                    (east, north), (west, north), (west, south)
                ])

            ghsl_client = await self._get_ghsl_client()
            ghsl_imagery = await ghsl_client.get_ghsl_built_surface(
                geometry=geometry,
                target_date=imagery.date,
            )

            if ghsl_imagery is None:
                raise ValueError(f"No GHSL data available for date {imagery.date}")

            built = ghsl_imagery.data[0].astype(np.float32)
            ghsl_metadata = ghsl_imagery.metadata or {}
            imagery = ghsl_imagery  # Use GHSL bounds

        if geometry is not None:
            built = self._mask_by_geometry(built, geometry, imagery.bounds)

        # Calculate statistics
        valid_mask = ~np.isnan(built)
        total_built = float(np.nansum(built))
        mean_built = float(np.nanmean(built))
        total_pixels = int(np.sum(valid_mask))

        # GHSL pixel area is 100m x 100m = 10,000 m²
        pixel_area_m2 = 10000
        total_area_m2 = total_pixels * pixel_area_m2

        return FeatureResult(
            metric_name=self.metric_name,
            value=mean_built,
            raster=built,
            bounds=imagery.bounds,
            date=imagery.date,
            unit=self.unit,
            metadata={
                "source": "GHSL",
                "dataset": "JRC/GHSL/P2023A/GHS_BUILT_S",
                "epoch": ghsl_metadata.get("epoch"),
                "total_built_area_m2": total_built,
                "total_built_area_km2": total_built / 1_000_000,
                "total_area_m2": total_area_m2,
                "total_area_km2": total_area_m2 / 1_000_000,
                "built_fraction": total_built / total_area_m2 if total_area_m2 > 0 else 0,
                "pixel_count": total_pixels,
            },
        )


class UrbanGrowthAnalyzer:
    """Analyze urban growth over time using GHSL data.

    This analyzer leverages the GHSL (Global Human Settlement Layer) multi-temporal
    dataset which provides consistent built-up area measurements from 1975 to 2030.
    """

    def __init__(self, ghsl_client: GHSLClient | None = None):
        """Initialize the analyzer.

        Args:
            ghsl_client: Optional GHSLClient instance for data access.
        """
        self.extractor = UrbanDensityExtractor(ghsl_client=ghsl_client)
        self._ghsl_client = ghsl_client

    async def analyze_growth(
        self,
        imagery_list: list[SatelliteImagery],
        geometry: Polygon | None = None,
    ) -> dict:
        """
        Analyze urban growth from a time series of imagery.

        Uses GHSL data for accurate multi-temporal comparison when available.

        Args:
            imagery_list: List of imagery for different dates
            geometry: Optional polygon to constrain analysis area

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
                    "source": result.metadata.get("source", "unknown"),
                    "ghsl_epoch": result.metadata.get("ghsl_epoch"),
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
                "data_source": results[0].get("source", "unknown") if results else None,
            },
        }

    async def analyze_growth_ghsl_epochs(
        self,
        geometry: Polygon,
        start_year: int = 1975,
        end_year: int = 2020,
    ) -> dict:
        """
        Analyze urban growth using GHSL multi-temporal epochs directly.

        This method fetches GHSL data for multiple epochs and provides
        a comprehensive urban growth analysis.

        Args:
            geometry: Polygon defining the area of interest
            start_year: Start year for analysis (default 1975)
            end_year: End year for analysis (default 2020)

        Returns:
            Dictionary with growth statistics across GHSL epochs
        """
        from app.services.satellite.gee_client import GHSLClient

        if self._ghsl_client is None:
            self._ghsl_client = GHSLClient()
            await self._ghsl_client.initialize()

        # Get available epochs in range
        epochs = [e for e in GHSLClient.AVAILABLE_EPOCHS if start_year <= e <= end_year]

        results = []
        for epoch in epochs:
            try:
                ghsl_imagery = await self._ghsl_client.get_ghsl_built_surface(
                    geometry=geometry,
                    target_date=date(epoch, 1, 1),
                )

                if ghsl_imagery is None:
                    continue

                result = await self.extractor.extract(ghsl_imagery, geometry)
                results.append(
                    {
                        "date": str(date(epoch, 1, 1)),
                        "epoch": epoch,
                        "urban_density": result.value,
                        "urban_fraction": result.metadata.get("urban_fraction", 0),
                        "urban_area_km2": result.metadata.get("urban_area_km2", 0),
                        "source": "GHSL",
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to get GHSL data for epoch {epoch}: {e}")

        if len(results) < 2:
            return {
                "timeline": results,
                "summary": {
                    "error": "Insufficient data points for growth analysis",
                },
            }

        first = results[0]
        last = results[-1]
        total_years = last["epoch"] - first["epoch"]
        total_growth_km2 = last["urban_area_km2"] - first["urban_area_km2"]
        growth_rate = (
            total_growth_km2 / first["urban_area_km2"] * 100
            if first["urban_area_km2"] > 0
            else 0
        )
        annual_growth = growth_rate / total_years if total_years > 0 else 0

        # Calculate period-by-period growth
        period_growth = []
        for i in range(1, len(results)):
            prev = results[i - 1]
            curr = results[i]
            period_years = curr["epoch"] - prev["epoch"]
            period_km2 = curr["urban_area_km2"] - prev["urban_area_km2"]
            period_pct = (
                period_km2 / prev["urban_area_km2"] * 100
                if prev["urban_area_km2"] > 0
                else 0
            )
            period_growth.append({
                "period": f"{prev['epoch']}-{curr['epoch']}",
                "growth_km2": period_km2,
                "growth_pct": period_pct,
                "annual_growth_pct": period_pct / period_years if period_years > 0 else 0,
            })

        return {
            "timeline": results,
            "period_growth": period_growth,
            "summary": {
                "start_epoch": first["epoch"],
                "end_epoch": last["epoch"],
                "start_date": first["date"],
                "end_date": last["date"],
                "total_growth_km2": total_growth_km2,
                "total_growth_pct": growth_rate,
                "annual_growth_pct": annual_growth,
                "start_urban_km2": first["urban_area_km2"],
                "end_urban_km2": last["urban_area_km2"],
                "data_source": "GHSL",
                "epochs_analyzed": len(results),
            },
        }
