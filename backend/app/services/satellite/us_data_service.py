"""
US-Wide Satellite Data Service

Fetches satellite data for the entire continental US for bulk tile generation.
"""

import asyncio
import io
from datetime import date

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Continental US bounding box
US_BOUNDS = {
    "west": -125.0,
    "east": -66.0,
    "south": 24.0,
    "north": 50.0,
}


class USDataService:
    """Fetch satellite data for the entire continental US."""

    def __init__(self):
        self._ee = None
        self._initialized = False
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
        if self._initialized:
            return

        import ee
        import json

        try:
            if self._settings.gee_service_account_key and self._settings.gee_project_id:
                with open(self._settings.gee_service_account_key) as f:
                    key_data = json.load(f)
                    service_account_email = key_data.get("client_email")

                credentials = ee.ServiceAccountCredentials(
                    service_account_email,
                    self._settings.gee_service_account_key,
                )
                ee.Initialize(credentials, project=self._settings.gee_project_id)
            else:
                ee.Initialize()

            self._ee = ee
            self._initialized = True
            logger.info("US Data Service initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Earth Engine", error=str(e))
            raise

    def _get_us_geometry(self):
        """Get Earth Engine geometry for continental US."""
        return self._ee.Geometry.Rectangle([
            US_BOUNDS["west"],
            US_BOUNDS["south"],
            US_BOUNDS["east"],
            US_BOUNDS["north"],
        ])

    async def _fetch_raster(
        self,
        image,
        bounds: dict,
        width: int = 512,
        height: int = 512,
    ) -> np.ndarray:
        """Fetch raster data from an Earth Engine image for a specific bounding box."""
        ee = self._ee

        request = {
            "expression": image,
            "fileFormat": "NPY",
            "grid": {
                "dimensions": {"width": width, "height": height},
                "affineTransform": {
                    "scaleX": (bounds["east"] - bounds["west"]) / width,
                    "shearX": 0,
                    "translateX": bounds["west"],
                    "shearY": 0,
                    "scaleY": -(bounds["north"] - bounds["south"]) / height,
                    "translateY": bounds["north"],
                },
                "crsCode": "EPSG:4326",
            },
        }

        loop = asyncio.get_event_loop()
        pixels = await loop.run_in_executor(
            None, lambda: ee.data.computePixels(request)
        )

        data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

        # Handle structured arrays
        if data_array.dtype.names:
            # Get first field
            field_name = data_array.dtype.names[0]
            return data_array[field_name].astype(np.float32)

        return data_array.astype(np.float32)

    async def _fetch_us_in_chunks(
        self,
        image,
        chunks_x: int = 6,
        chunks_y: int = 3,
        chunk_size: int = 512,
    ) -> np.ndarray:
        """
        Fetch US data by splitting into smaller chunks to avoid memory limits.

        Divides the US into a grid of chunks, fetches each separately,
        and stitches them together.
        """
        # Calculate chunk bounds
        lon_step = (US_BOUNDS["east"] - US_BOUNDS["west"]) / chunks_x
        lat_step = (US_BOUNDS["north"] - US_BOUNDS["south"]) / chunks_y

        # Initialize output array
        total_width = chunk_size * chunks_x
        total_height = chunk_size * chunks_y
        result = np.zeros((total_height, total_width), dtype=np.float32)

        for i in range(chunks_x):
            for j in range(chunks_y):
                chunk_bounds = {
                    "west": US_BOUNDS["west"] + i * lon_step,
                    "east": US_BOUNDS["west"] + (i + 1) * lon_step,
                    "south": US_BOUNDS["north"] - (j + 1) * lat_step,
                    "north": US_BOUNDS["north"] - j * lat_step,
                }

                try:
                    chunk_data = await self._fetch_raster(
                        image, chunk_bounds, chunk_size, chunk_size
                    )

                    # Place chunk in result array
                    y_start = j * chunk_size
                    y_end = (j + 1) * chunk_size
                    x_start = i * chunk_size
                    x_end = (i + 1) * chunk_size

                    result[y_start:y_end, x_start:x_end] = chunk_data

                except Exception as e:
                    logger.warning(f"Failed to fetch chunk ({i}, {j}): {e}")
                    # Leave as zeros

        return result

    async def get_ndvi(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get NDVI data for the entire US for a specific month.

        Uses Sentinel-2 imagery with cloud masking.
        Fetches in chunks to avoid GEE memory limits.
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        # Date range for the month
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        logger.info(f"Fetching NDVI for US: {start_date} to {end_date}")

        try:
            # Query Sentinel-2 collection
            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No Sentinel-2 imagery for {start_date}")
                return None

            # Cloud masking function
            def mask_clouds(image):
                scl = image.select("SCL")
                mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
                return image.updateMask(mask)

            # Apply cloud mask and create median composite
            collection = collection.map(mask_clouds)
            composite = collection.median()

            # Calculate NDVI
            ndvi = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")

            return await self._fetch_us_in_chunks(ndvi, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch NDVI: {e}")
            return None

    async def get_nightlights(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get VIIRS nighttime lights for the entire US for a specific month.
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        # VIIRS monthly composites
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        logger.info(f"Fetching nightlights for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["avg_rad"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No VIIRS data for {start_date}")
                return None

            # Get the monthly composite (usually just one image per month)
            image = collection.median()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch nightlights: {e}")
            return None

    async def get_urban_density(
        self,
        year: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get urban density from GHSL Built-up Surface for the US.

        Note: GHSL is available for specific epochs (2020, 2025, etc.),
        so we use the nearest available epoch.
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        # Available GHSL epochs
        epochs = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
        nearest_epoch = min(epochs, key=lambda x: abs(x - year))

        logger.info(f"Fetching urban density for US (epoch {nearest_epoch})")

        try:
            # Load GHSL Built-up Surface
            collection = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")

            # Get the image for the nearest epoch
            image = collection.filter(
                ee.Filter.eq("system:index", f"GHS_BUILT_S_E{nearest_epoch}_GLOBE_R2023A_54009_100_V1_0")
            ).first()

            if image is None:
                # Fallback to mosaic
                image = collection.mosaic()

            # Select built surface and normalize (values are in m²/pixel)
            # Normalize to 0-1 by dividing by max expected value (~10000 m²)
            image = image.select(["built_surface"]).divide(10000).clamp(0, 1)

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch urban density: {e}")
            return None

    async def get_parking(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get parking/impervious surface proxy from Sentinel-2 NDBI.

        Uses Normalized Difference Built-up Index as proxy for impervious surfaces.
        NDBI = (SWIR - NIR) / (SWIR + NIR)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        logger.info(f"Fetching parking/NDBI for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No Sentinel-2 data for parking: {start_date}")
                return None

            # Cloud masking
            def mask_clouds(image):
                scl = image.select("SCL")
                mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
                return image.updateMask(mask)

            collection = collection.map(mask_clouds)
            composite = collection.median()

            # Calculate NDBI (Normalized Difference Built-up Index)
            # NDBI = (SWIR - NIR) / (SWIR + NIR)
            # B11 = SWIR, B8 = NIR
            ndbi = composite.normalizedDifference(["B11", "B8"]).rename("ndbi")

            # Normalize to 0-1 range (NDBI ranges from -1 to 1, but built-up typically 0 to 0.5)
            ndbi = ndbi.add(1).divide(2).clamp(0, 1)

            return await self._fetch_us_in_chunks(ndbi, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch parking: {e}")
            return None
