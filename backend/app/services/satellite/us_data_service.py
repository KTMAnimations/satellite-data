"""
US-Wide Satellite Data Service

Fetches satellite data for the entire continental US for bulk tile generation.
Uses Web Mercator (EPSG:3857) projection to match XYZ tile coordinates.
"""

import asyncio
import io
import math
from datetime import date

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Continental US bounding box (EPSG:4326 - lat/lon)
US_BOUNDS = {
    "west": -125.0,
    "east": -66.0,
    "south": 24.0,
    "north": 50.0,
}


def lon_to_mercator_x(lon: float) -> float:
    """Convert longitude to Web Mercator X (meters)."""
    return lon * 20037508.34 / 180.0


def lat_to_mercator_y(lat: float) -> float:
    """Convert latitude to Web Mercator Y (meters)."""
    lat_rad = math.radians(lat)
    y = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    return y * 20037508.34 / math.pi


# US bounds in Web Mercator (EPSG:3857)
US_BOUNDS_MERCATOR = {
    "west": lon_to_mercator_x(US_BOUNDS["west"]),
    "east": lon_to_mercator_x(US_BOUNDS["east"]),
    "south": lat_to_mercator_y(US_BOUNDS["south"]),
    "north": lat_to_mercator_y(US_BOUNDS["north"]),
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
        """
        Fetch raster data from an Earth Engine image for a specific bounding box.

        Uses Web Mercator (EPSG:3857) projection to match XYZ tile coordinates.
        Bounds should be provided in Web Mercator meters.
        """
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
                "crsCode": "EPSG:3857",  # Web Mercator to match XYZ tiles
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

        Divides the US into a grid of chunks, fetches each separately with overlap,
        and blends them together to eliminate seams. Uses Web Mercator projection.
        """
        # Overlap size in pixels (for blending adjacent chunks)
        overlap = 32

        # Calculate chunk bounds in Web Mercator (meters)
        x_step = (US_BOUNDS_MERCATOR["east"] - US_BOUNDS_MERCATOR["west"]) / chunks_x
        y_step = (US_BOUNDS_MERCATOR["north"] - US_BOUNDS_MERCATOR["south"]) / chunks_y

        # Initialize output array
        total_width = chunk_size * chunks_x
        total_height = chunk_size * chunks_y
        result = np.zeros((total_height, total_width), dtype=np.float32)
        weight = np.zeros((total_height, total_width), dtype=np.float32)

        # Calculate overlap in meters
        x_res = x_step / chunk_size
        y_res = y_step / chunk_size
        overlap_x_meters = overlap * x_res
        overlap_y_meters = overlap * y_res

        for i in range(chunks_x):
            for j in range(chunks_y):
                # Add overlap to chunk bounds (except at edges)
                west_overlap = overlap_x_meters if i > 0 else 0
                east_overlap = overlap_x_meters if i < chunks_x - 1 else 0
                north_overlap = overlap_y_meters if j > 0 else 0
                south_overlap = overlap_y_meters if j < chunks_y - 1 else 0

                chunk_bounds = {
                    "west": US_BOUNDS_MERCATOR["west"] + i * x_step - west_overlap,
                    "east": US_BOUNDS_MERCATOR["west"] + (i + 1) * x_step + east_overlap,
                    "south": US_BOUNDS_MERCATOR["north"] - (j + 1) * y_step - south_overlap,
                    "north": US_BOUNDS_MERCATOR["north"] - j * y_step + north_overlap,
                }

                # Calculate fetch size with overlap
                fetch_width = chunk_size + (overlap if i > 0 else 0) + (overlap if i < chunks_x - 1 else 0)
                fetch_height = chunk_size + (overlap if j > 0 else 0) + (overlap if j < chunks_y - 1 else 0)

                try:
                    chunk_data = await self._fetch_raster(
                        image, chunk_bounds, fetch_width, fetch_height
                    )

                    # Calculate where to place this chunk in the result
                    y_start = j * chunk_size - (overlap if j > 0 else 0)
                    y_end = y_start + fetch_height
                    x_start = i * chunk_size - (overlap if i > 0 else 0)
                    x_end = x_start + fetch_width

                    # Clamp to valid range
                    y_start_clamped = max(0, y_start)
                    y_end_clamped = min(total_height, y_end)
                    x_start_clamped = max(0, x_start)
                    x_end_clamped = min(total_width, x_end)

                    # Calculate corresponding region in chunk data
                    chunk_y_start = y_start_clamped - y_start
                    chunk_y_end = chunk_y_start + (y_end_clamped - y_start_clamped)
                    chunk_x_start = x_start_clamped - x_start
                    chunk_x_end = chunk_x_start + (x_end_clamped - x_start_clamped)

                    # Create blend weight (feather edges in overlap regions)
                    chunk_weight = np.ones_like(chunk_data)

                    # Feather left edge if there's overlap
                    if i > 0 and overlap > 0:
                        for k in range(min(overlap, chunk_weight.shape[1])):
                            chunk_weight[:, k] *= k / overlap

                    # Feather right edge if there's overlap
                    if i < chunks_x - 1 and overlap > 0:
                        for k in range(min(overlap, chunk_weight.shape[1])):
                            chunk_weight[:, -(k+1)] *= k / overlap

                    # Feather top edge if there's overlap
                    if j > 0 and overlap > 0:
                        for k in range(min(overlap, chunk_weight.shape[0])):
                            chunk_weight[k, :] *= k / overlap

                    # Feather bottom edge if there's overlap
                    if j < chunks_y - 1 and overlap > 0:
                        for k in range(min(overlap, chunk_weight.shape[0])):
                            chunk_weight[-(k+1), :] *= k / overlap

                    # Extract the region that fits in the result
                    chunk_region = chunk_data[chunk_y_start:chunk_y_end, chunk_x_start:chunk_x_end]
                    weight_region = chunk_weight[chunk_y_start:chunk_y_end, chunk_x_start:chunk_x_end]

                    # Add weighted contribution
                    result[y_start_clamped:y_end_clamped, x_start_clamped:x_end_clamped] += chunk_region * weight_region
                    weight[y_start_clamped:y_end_clamped, x_start_clamped:x_end_clamped] += weight_region

                except Exception as e:
                    logger.warning(f"Failed to fetch chunk ({i}, {j}): {e}")
                    # Leave as zeros

        # Normalize by weight (avoid division by zero)
        weight = np.maximum(weight, 1e-10)
        result = result / weight

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
        day: int | None = None,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get VIIRS nighttime lights for the entire US.

        Args:
            year: Year
            month: Month (1-12)
            day: Day (1-31) for daily data, None for monthly composite
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Raster data array or None if no data available
        """
        if day is not None:
            return await self._get_nightlights_daily(year, month, day, chunks_x, chunks_y)
        else:
            return await self._get_nightlights_monthly(year, month, chunks_x, chunks_y)

    async def _get_nightlights_monthly(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """Get VIIRS monthly composite nighttime lights."""
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

        logger.info(f"Fetching monthly nightlights for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["avg_rad"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No monthly VIIRS data for {start_date}")
                return None

            # Get the monthly composite (usually just one image per month)
            image = collection.median()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch monthly nightlights: {e}")
            return None

    async def _get_nightlights_daily(
        self,
        year: int,
        month: int,
        day: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get daily VIIRS nighttime lights using NASA Black Marble VNP46A2.

        VNP46A2 provides gap-filled, moonlight-adjusted daily nighttime lights.
        This gives much finer temporal resolution than monthly composites.
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        target_date = f"{year}-{month:02d}-{day:02d}"
        # Query a small window around target date to handle data availability
        from datetime import datetime, timedelta
        target_dt = datetime(year, month, day)
        start_dt = target_dt - timedelta(days=1)
        end_dt = target_dt + timedelta(days=2)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        logger.info(f"Fetching daily nightlights for US: {target_date}")

        try:
            # NASA Black Marble VNP46A2 - Daily gap-filled nighttime lights
            # This dataset provides moonlight-corrected, gap-filled daily composites
            collection = (
                ee.ImageCollection("NASA/VIIRS/002/VNP46A2")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No daily VIIRS data for {target_date}, falling back to monthly")
                # Fallback to monthly if daily not available
                return await self._get_nightlights_monthly(year, month, chunks_x, chunks_y)

            # Select the Gap_Filled_DNB_BRDF-Corrected_NTL band
            # This is the primary nighttime lights band, already corrected
            image = collection.select(["DNB_BRDF_Corrected_NTL"]).median()

            # Apply quality masking using the mandatory QA flags
            # QA values: 0=high quality, 1=good, 2=gap filled, 255=fill value
            qa_collection = (
                ee.ImageCollection("NASA/VIIRS/002/VNP46A2")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["Mandatory_Quality_Flag"])
            )

            if qa_collection.size().getInfo() > 0:
                qa = qa_collection.median()
                # Mask out fill values (255) and poor quality
                quality_mask = qa.lt(3)  # Keep 0, 1, 2 (high, good, gap-filled)
                image = image.updateMask(quality_mask)

            # Scale the values - VNP46A2 values are in nW/cm²/sr
            # Typical range is 0-200, similar to monthly composites
            image = image.clamp(0, 200)

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch daily nightlights: {e}", exc_info=True)
            # Fallback to monthly on error
            logger.info("Falling back to monthly composite")
            return await self._get_nightlights_monthly(year, month, chunks_x, chunks_y)

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

    async def get_dynamic_world(
        self,
        year: int,
        month: int,
        land_cover_class: str = "built",
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get Dynamic World land cover probability for the US.

        Args:
            year: Year
            month: Month (1-12)
            land_cover_class: One of water, trees, grass, flooded_vegetation,
                            crops, shrub_and_scrub, built, bare, snow_and_ice
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks
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

        logger.info(f"Fetching Dynamic World ({land_cover_class}) for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select([land_cover_class])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No Dynamic World data for {start_date}")
                return None

            image = collection.median()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch Dynamic World: {e}")
            return None

    async def get_surface_water(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get JRC Surface Water extent for the US.

        Args:
            year: Year (1984-2021)
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        target_date = f"{year}-{month:02d}"
        logger.info(f"Fetching JRC Surface Water for US: {target_date}")

        try:
            collection = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterBounds(aoi)
            image = collection.filter(ee.Filter.eq("system:index", target_date)).first()

            if image is None:
                logger.warning(f"No JRC Surface Water data for {target_date}")
                return None

            # Convert to binary water mask (2 = water)
            water_mask = image.select(["water"]).eq(2)

            return await self._fetch_us_in_chunks(water_mask, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch surface water: {e}")
            return None

    async def get_active_fire(
        self,
        year: int,
        month: int,
        day: int | None = None,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get VIIRS 375m active fire detections for the US.

        Args:
            year: Year
            month: Month (1-12)
            day: Optional day for daily data
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        if day:
            start_date = f"{year}-{month:02d}-{day:02d}"
            from datetime import datetime, timedelta
            end_dt = datetime(year, month, day) + timedelta(days=1)
            end_date = end_dt.strftime("%Y-%m-%d")
        else:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"

        logger.info(f"Fetching VIIRS active fire for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["FRP"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No VIIRS fire data for {start_date}")
                return None

            # Max composite to capture all fires
            image = collection.max()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch active fire: {e}")
            return None

    async def get_no2(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get Sentinel-5P NO2 for the US.

        Args:
            year: Year (2018+)
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks
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

        logger.info(f"Fetching S5P NO2 for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["tropospheric_NO2_column_number_density"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No S5P NO2 data for {start_date}")
                return None

            image = collection.mean()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch NO2: {e}")
            return None

    async def get_temperature(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get ERA5-Land 2m temperature for the US.

        Args:
            year: Year
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Temperature in Celsius
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

        logger.info(f"Fetching ERA5-Land temperature for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["temperature_2m"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No ERA5-Land data for {start_date}")
                return None

            # Mean temperature, convert Kelvin to Celsius
            image = collection.mean().subtract(273.15)

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch temperature: {e}")
            return None

    async def get_precipitation(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get ERA5-Land precipitation for the US.

        Args:
            year: Year
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Total precipitation in mm
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

        logger.info(f"Fetching ERA5-Land precipitation for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["total_precipitation_hourly"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No ERA5-Land precipitation data for {start_date}")
                return None

            # Sum precipitation, convert m to mm
            image = collection.sum().multiply(1000)

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch precipitation: {e}")
            return None

    async def get_aerosol(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get Sentinel-5P Aerosol Index for the US.

        Args:
            year: Year (2018+)
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks
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

        logger.info(f"Fetching S5P Aerosol for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_AER_AI")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["absorbing_aerosol_index"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No S5P Aerosol data for {start_date}")
                return None

            image = collection.mean()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch aerosol: {e}")
            return None

    async def get_cropland(
        self,
        year: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get USDA Cropland Data Layer for the US.

        Args:
            year: Year (2008+)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Crop type codes
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = self._get_us_geometry()

        logger.info(f"Fetching USDA CDL for US: {year}")

        try:
            collection = (
                ee.ImageCollection("USDA/NASS/CDL")
                .filterBounds(aoi)
                .filter(ee.Filter.calendarRange(year, year, "year"))
                .select(["cropland"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No USDA CDL data for {year}")
                return None

            image = collection.first()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch cropland: {e}")
            return None

    async def get_evapotranspiration(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get OpenET evapotranspiration for the US.

        Args:
            year: Year
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            ET in mm
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

        logger.info(f"Fetching OpenET for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("OpenET/SSEBOP/CONUS/GRIDMET/MONTHLY/v2_0")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["et"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No OpenET data for {start_date}")
                return None

            image = collection.first()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch evapotranspiration: {e}")
            return None

    async def get_soil_moisture(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get SMAP soil moisture for the US.

        Args:
            year: Year
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Soil moisture in mm
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

        logger.info(f"Fetching SMAP soil moisture for US: {start_date} to {end_date}")

        try:
            # Use SMAP Level-4 soil moisture (9km, 3-hourly)
            # sm_surface = surface soil moisture (0-5cm) in m³/m³
            collection = (
                ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["sm_surface"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No SMAP data for {start_date}")
                return None

            image = collection.mean()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch soil moisture: {e}")
            return None

    async def get_impervious(
        self,
        year: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get GAIA impervious surface for the US.

        Args:
            year: Year (1985-2018, returns urbanization up to this year)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Binary impervious mask
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee

        # Clamp year to valid range
        year = min(max(year, 1985), 2018)

        logger.info(f"Fetching GAIA impervious surface for US up to: {year}")

        try:
            image = ee.Image("Tsinghua/FROM-GLC/GAIA/v10")
            # Create binary mask for urbanized by target year
            urbanized = image.lte(year).And(image.gt(0))

            return await self._fetch_us_in_chunks(urbanized, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch impervious surface: {e}")
            return None

    async def get_fire_historical(
        self,
        year: int,
        month: int,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get MODIS FIRMS historical fire data for the US.

        Args:
            year: Year (2000+)
            month: Month (1-12)
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Fire Radiative Power in MW
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

        logger.info(f"Fetching MODIS FIRMS for US: {start_date} to {end_date}")

        try:
            collection = (
                ee.ImageCollection("MODIS/061/MOD14A1")
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["MaxFRP"])
            )

            count = collection.size().getInfo()
            if count == 0:
                logger.warning(f"No MODIS fire data for {start_date}")
                return None

            image = collection.max()

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch fire historical: {e}")
            return None

    async def get_canopy_height(
        self,
        chunks_x: int = 6,
        chunks_y: int = 3,
    ) -> np.ndarray | None:
        """
        Get GEDI canopy height for the US.

        Args:
            chunks_x: Number of horizontal chunks
            chunks_y: Number of vertical chunks

        Returns:
            Canopy height in meters
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee

        logger.info("Fetching GEDI canopy height for US")

        try:
            image = ee.Image("LARSE/GEDI/GRIDDEDVEG_002/V1/1KM").select(["rh98"])

            return await self._fetch_us_in_chunks(image, chunks_x, chunks_y)

        except Exception as e:
            logger.error(f"Failed to fetch canopy height: {e}")
            return None
