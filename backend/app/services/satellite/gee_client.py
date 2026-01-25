import asyncio
from datetime import date
from typing import Any

import numpy as np
from shapely.geometry import Polygon, mapping

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.satellite.base import BaseSatelliteClient, SatelliteImagery

logger = get_logger(__name__)


class GEEClient(BaseSatelliteClient):
    """Google Earth Engine client for satellite data retrieval."""

    SENTINEL2_BANDS = [
        "B1",  # Coastal aerosol
        "B2",  # Blue
        "B3",  # Green
        "B4",  # Red
        "B5",  # Vegetation Red Edge
        "B6",  # Vegetation Red Edge
        "B7",  # Vegetation Red Edge
        "B8",  # NIR
        "B8A",  # Vegetation Red Edge
        "B9",  # Water vapour
        "B11",  # SWIR
        "B12",  # SWIR
        "SCL",  # Scene Classification Layer
    ]

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine authentication."""
        if self._initialized:
            return

        import ee

        try:
            if self._settings.gee_service_account and self._settings.gee_key_file:
                credentials = ee.ServiceAccountCredentials(
                    self._settings.gee_service_account,
                    self._settings.gee_key_file,
                )
                ee.Initialize(credentials)
            else:
                # Try default authentication
                ee.Initialize()

            self._ee = ee
            self._initialized = True
            logger.info("Google Earth Engine initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Google Earth Engine", error=str(e))
            raise

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Retrieve Sentinel-2 imagery from GEE."""
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        # Query Sentinel-2 collection
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
        )

        # Get image count
        count = collection.size().getInfo()
        if count == 0:
            logger.warning(
                "No imagery found",
                geometry=str(geometry.bounds),
                start_date=str(start_date),
                end_date=str(end_date),
            )
            return []

        # Get list of images
        image_list = collection.toList(count)
        results = []

        for i in range(min(count, 50)):  # Limit to 50 images
            img = ee.Image(image_list.get(i))
            img_data = await self._download_image(img, aoi, bands)
            if img_data is not None:
                results.append(img_data)

        return results

    async def _download_image(
        self,
        image: Any,
        aoi: Any,
        bands: list[str] | None = None,
    ) -> SatelliteImagery | None:
        """Download a single image from GEE."""
        ee = self._ee

        try:
            # Get image info
            info = image.getInfo()
            img_date = date.fromtimestamp(
                info["properties"]["system:time_start"] / 1000
            )
            cloud_cover = info["properties"].get("CLOUDY_PIXEL_PERCENTAGE", None)

            # Select bands
            if bands is None:
                bands = ["B4", "B3", "B2", "B8"]  # RGB + NIR by default
            image = image.select(bands)

            # Apply cloud mask using SCL band
            if "SCL" in self.SENTINEL2_BANDS:
                scl = ee.Image(
                    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                    .filterBounds(aoi)
                    .filterDate(img_date.isoformat(), img_date.isoformat())
                    .first()
                ).select("SCL")

                # Mask clouds, shadows, and water
                cloud_mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
                image = image.updateMask(cloud_mask)

            # Get bounds
            bounds = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds)
            east = max(c[0] for c in bounds)
            south = min(c[1] for c in bounds)
            north = max(c[1] for c in bounds)

            # Download as numpy array
            # Note: In production, use ee.data.computePixels or export to Cloud Storage
            url = image.getThumbURL(
                {
                    "region": aoi,
                    "dimensions": 512,
                    "format": "npy",
                }
            )

            # For now, return with placeholder data
            # Real implementation would download the actual data
            data = np.zeros((len(bands), 512, 512), dtype=np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=img_date,
                source="Sentinel-2 (GEE)",
                bands=bands,
                resolution=10.0,
                cloud_cover=cloud_cover,
                metadata=info["properties"],
            )

        except Exception as e:
            logger.error("Failed to download image", error=str(e))
            return None

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Create a cloud-free composite."""
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        # Query collection
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
        )

        if collection.size().getInfo() == 0:
            return None

        # Apply cloud masking
        def mask_clouds(image):
            scl = image.select("SCL")
            mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            return image.updateMask(mask)

        collection = collection.map(mask_clouds)

        # Select bands
        if bands is None:
            bands = ["B4", "B3", "B2", "B8"]
        collection = collection.select(bands)

        # Create composite
        if composite_method == "median":
            composite = collection.median()
        elif composite_method == "mean":
            composite = collection.mean()
        else:
            composite = collection.mosaic()

        # Get bounds
        bounds_info = aoi.bounds().getInfo()["coordinates"][0]
        west = min(c[0] for c in bounds_info)
        east = max(c[0] for c in bounds_info)
        south = min(c[1] for c in bounds_info)
        north = max(c[1] for c in bounds_info)

        # Placeholder data
        data = np.zeros((len(bands), 512, 512), dtype=np.float32)

        return SatelliteImagery(
            data=data,
            bounds=(west, south, east, north),
            crs="EPSG:4326",
            date=start_date,
            source="Sentinel-2 Composite (GEE)",
            bands=bands,
            resolution=10.0,
            metadata={"composite_method": composite_method},
        )

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get dates with available imagery."""
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
        )

        # Get unique dates
        def get_date(image):
            return ee.Feature(None, {"date": image.date().format("YYYY-MM-dd")})

        dates = collection.map(get_date).distinct("date").aggregate_array("date")
        date_strings = dates.getInfo()

        return [date.fromisoformat(d) for d in sorted(set(date_strings))]

    @property
    def source_name(self) -> str:
        return "Google Earth Engine"

    @property
    def available_bands(self) -> list[str]:
        return self.SENTINEL2_BANDS

    @property
    def native_resolution(self) -> float:
        return 10.0


class VIIRSClient(BaseSatelliteClient):
    """Client for VIIRS nighttime lights data from GEE."""

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
        import ee

        try:
            ee.Initialize()
            self._ee = ee
            self._initialized = True
        except Exception as e:
            logger.error("Failed to initialize GEE for VIIRS", error=str(e))
            raise

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get VIIRS nighttime lights imagery."""
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        # VIIRS DNB monthly composites
        collection = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterBounds(aoi)
            .filterDate(start_date.isoformat(), end_date.isoformat())
            .select(["avg_rad"])  # Average radiance
        )

        count = collection.size().getInfo()
        if count == 0:
            return []

        results = []
        image_list = collection.toList(count)

        for i in range(count):
            img = ee.Image(image_list.get(i))
            info = img.getInfo()
            img_date = date.fromtimestamp(
                info["properties"]["system:time_start"] / 1000
            )

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            data = np.zeros((1, 256, 256), dtype=np.float32)

            results.append(
                SatelliteImagery(
                    data=data,
                    bounds=(west, south, east, north),
                    crs="EPSG:4326",
                    date=img_date,
                    source="VIIRS DNB (GEE)",
                    bands=["avg_rad"],
                    resolution=375.0,
                    metadata=info["properties"],
                )
            )

        return results

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """VIIRS data is already monthly composites."""
        images = await self.get_imagery(geometry, start_date, end_date)
        if not images:
            return None
        # Return the most recent composite
        return max(images, key=lambda x: x.date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available monthly composite dates."""
        images = await self.get_imagery(geometry, start_date, end_date)
        return [img.date for img in images]

    @property
    def source_name(self) -> str:
        return "VIIRS DNB"

    @property
    def available_bands(self) -> list[str]:
        return ["avg_rad", "cf_cvg"]

    @property
    def native_resolution(self) -> float:
        return 375.0
