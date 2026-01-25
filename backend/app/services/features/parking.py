import numpy as np
from shapely.geometry import Polygon
from skimage import morphology, measure

from app.core.logging import get_logger
from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.satellite.base import SatelliteImagery

logger = get_logger(__name__)


class ParkingDetector(BaseFeatureExtractor):
    """
    Parking lot detection and occupancy estimation.

    Uses spectral characteristics to identify large paved areas
    (parking lots, roads) and estimate their usage through
    spectral variation analysis.

    At 10m resolution, individual cars are not detectable,
    but aggregate patterns in large parking lots can provide
    proxy metrics for activity levels.
    """

    # Minimum area for parking lot detection (in pixels at 10m = ~2500m² = 0.25ha)
    MIN_PARKING_AREA_PIXELS = 25

    @property
    def metric_name(self) -> str:
        return "parking"

    @property
    def required_bands(self) -> list[str]:
        return ["B2", "B3", "B4", "B8", "B11"]  # Blue, Green, Red, NIR, SWIR

    @property
    def unit(self) -> str:
        return "occupancy ratio"

    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """
        Detect parking lots and estimate occupancy.

        Approach:
        1. Identify impervious surfaces using spectral indices
        2. Filter for flat, uniform areas (parking lots vs roads)
        3. Analyze spectral variation as proxy for occupancy
        """
        try:
            # Get band indices
            bands = imagery.bands
            blue = imagery.data[bands.index("B2")].astype(np.float32)
            green = imagery.data[bands.index("B3")].astype(np.float32)
            red = imagery.data[bands.index("B4")].astype(np.float32)
            nir = imagery.data[bands.index("B8")].astype(np.float32)
            swir = imagery.data[bands.index("B11")].astype(np.float32)

            # Normalize bands
            for band in [blue, green, red, nir, swir]:
                band[band == 0] = np.nan

            # 1. Calculate impervious surface index
            # Built-up areas have high SWIR and low NIR vegetation response
            ndbi = (swir - nir) / (swir + nir + 1e-10)

            # 2. Calculate vegetation mask (exclude vegetated areas)
            ndvi = (nir - red) / (nir + red + 1e-10)
            non_vegetation = ndvi < 0.2

            # 3. Identify flat, bright surfaces (parking lots are usually light-colored)
            brightness = (blue + green + red) / 3
            bright_threshold = np.nanpercentile(brightness[~np.isnan(brightness)], 70)
            is_bright = brightness > bright_threshold

            # 4. Combine masks to identify potential parking lots
            parking_mask = non_vegetation & is_bright & (ndbi > 0)

            # 5. Filter by area - remove small isolated pixels
            parking_mask = morphology.remove_small_objects(
                parking_mask.astype(bool), min_size=self.MIN_PARKING_AREA_PIXELS
            )

            # 6. Label connected components (individual parking lots)
            labeled = measure.label(parking_mask)
            regions = measure.regionprops(labeled)

            # 7. Analyze each parking lot
            parking_lots = []
            total_occupancy = 0
            total_area = 0

            for region in regions:
                # Get spectral values for this parking lot
                mask = labeled == region.label
                lot_red = red[mask]
                lot_nir = nir[mask]

                # Estimate occupancy using spectral variation
                # Empty lots are more uniform, occupied lots show more variation
                variation = np.nanstd(lot_red) / (np.nanmean(lot_red) + 1e-10)

                # Normalize variation to 0-1 occupancy estimate
                # This is a rough proxy - higher variation = more occupied
                occupancy = min(variation * 2, 1.0)

                area_m2 = region.area * (imagery.resolution ** 2)

                parking_lots.append(
                    {
                        "centroid": region.centroid,
                        "area_m2": area_m2,
                        "occupancy": occupancy,
                    }
                )

                total_occupancy += occupancy * area_m2
                total_area += area_m2

            # Calculate overall occupancy
            mean_occupancy = total_occupancy / total_area if total_area > 0 else 0

            # Create occupancy raster
            occupancy_raster = np.zeros_like(red)
            for lot in parking_lots:
                # This is simplified - in practice you'd fill each region
                pass

            if geometry is not None:
                parking_mask = self._mask_by_geometry(
                    parking_mask.astype(np.float32), geometry, imagery.bounds
                )

            return FeatureResult(
                metric_name=self.metric_name,
                value=mean_occupancy,
                raster=parking_mask.astype(np.float32),
                bounds=imagery.bounds,
                date=imagery.date,
                unit=self.unit,
                metadata={
                    "parking_lot_count": len(parking_lots),
                    "total_parking_area_m2": total_area,
                    "total_parking_area_km2": total_area / 1_000_000,
                    "lots": parking_lots[:10],  # Limit to top 10
                },
            )

        except Exception as e:
            logger.error("Parking detection failed", error=str(e))
            raise


class LargeVenueAnalyzer:
    """
    Analyze activity at large venues (stadiums, malls, airports).

    These locations have parking lots large enough to detect
    aggregate patterns even at 10m resolution.
    """

    def __init__(self):
        self.detector = ParkingDetector()

    async def analyze_venue(
        self,
        imagery_list: list[SatelliteImagery],
        venue_geometry: Polygon,
    ) -> dict:
        """
        Analyze parking patterns at a specific venue over time.

        Args:
            imagery_list: Time series of satellite imagery
            venue_geometry: Polygon defining the venue area

        Returns:
            Analysis results with temporal patterns
        """
        results = []

        for imagery in sorted(imagery_list, key=lambda x: x.date):
            detection = await self.detector.extract(imagery, venue_geometry)
            results.append(
                {
                    "date": str(detection.date),
                    "occupancy": detection.value,
                    "parking_area_m2": detection.metadata.get("total_parking_area_m2", 0),
                }
            )

        # Analyze patterns
        occupancies = [r["occupancy"] for r in results]

        return {
            "timeline": results,
            "summary": {
                "mean_occupancy": np.mean(occupancies) if occupancies else 0,
                "max_occupancy": max(occupancies) if occupancies else 0,
                "min_occupancy": min(occupancies) if occupancies else 0,
                "occupancy_std": np.std(occupancies) if occupancies else 0,
            },
        }
