import asyncio
import io
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
            if self._settings.gee_service_account_key and self._settings.gee_project_id:
                # Read service account email from the JSON key file
                import json
                with open(self._settings.gee_service_account_key) as f:
                    key_data = json.load(f)
                    service_account_email = key_data.get("client_email")

                credentials = ee.ServiceAccountCredentials(
                    service_account_email,
                    self._settings.gee_service_account_key,
                )
                ee.Initialize(credentials, project=self._settings.gee_project_id)
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
        scale: float = 100.0,  # meters per pixel (100m for faster downloads)
    ) -> SatelliteImagery | None:
        """Download a single image from GEE using computePixels."""
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
            scl = image.select([]).addBands(
                ee.Image(info["id"]).select("SCL")
            ).select("SCL")
            # Mask: 3=cloud shadow, 8=cloud medium prob, 9=cloud high prob, 10=thin cirrus
            cloud_mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
            image = image.updateMask(cloud_mask)

            # Get bounds
            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            # Use computePixels to download actual data
            # This is the recommended approach for programmatic access
            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            # Run in thread pool since this is blocking I/O
            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            # Parse numpy array from bytes
            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            # Convert structured array to regular array if needed
            if data_array.dtype.names:
                # Structured array with band names
                data = np.stack([data_array[band] for band in bands], axis=0)
            else:
                data = data_array

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=img_date,
                source="Sentinel-2 (GEE)",
                bands=bands,
                resolution=scale,
                cloud_cover=cloud_cover,
                metadata=info["properties"],
            )

        except Exception as e:
            logger.error("Failed to download image", error=str(e), exc_info=True)
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

        # Download actual data using computePixels
        request = {
            "expression": composite,
            "fileFormat": "NPY",
            "grid": {
                "dimensions": {"width": 512, "height": 512},
                "affineTransform": {
                    "scaleX": (east - west) / 512,
                    "shearX": 0,
                    "translateX": west,
                    "shearY": 0,
                    "scaleY": -(north - south) / 512,
                    "translateY": north,
                },
                "crsCode": "EPSG:4326",
            },
        }

        try:
            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            # Convert structured array to regular array if needed
            if data_array.dtype.names:
                data = np.stack([data_array[band] for band in bands], axis=0)
            else:
                data = data_array

            data = data.astype(np.float32)
        except Exception as e:
            logger.error("Failed to download composite", error=str(e))
            # Return zeros as fallback
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


class GHSLClient(BaseSatelliteClient):
    """Client for GHSL (Global Human Settlement Layer) data from GEE.

    Provides access to pre-computed urban settlement data:
    - GHS_BUILT_S: Built-up surface area (100m resolution, 1975-2030)
    - GHS_SMOD: Settlement model (1km resolution, urban-rural classification)
    """

    # GHSL dataset IDs
    GHSL_BUILT_S = "JRC/GHSL/P2023A/GHS_BUILT_S"
    GHSL_SMOD = "JRC/GHSL/P2023A/GHS_SMOD"

    # Available epochs for GHSL data
    AVAILABLE_EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("GHSL client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for GHSL", error=str(e))
            raise

    def _get_nearest_epoch(self, target_year: int) -> int:
        """Find the nearest available GHSL epoch for a given year."""
        return min(self.AVAILABLE_EPOCHS, key=lambda x: abs(x - target_year))

    async def get_ghsl_built_surface(
        self,
        geometry: Polygon,
        target_date: date,
        resolution: int = 100,
    ) -> SatelliteImagery | None:
        """Get GHSL built-up surface data for a given geometry and date.

        Args:
            geometry: Polygon defining the area of interest
            target_date: Target date (will use nearest available epoch)
            resolution: Output resolution in meters (default 100m)

        Returns:
            SatelliteImagery with built-up surface data (m² per pixel)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        # Get the nearest available epoch
        target_epoch = self._get_nearest_epoch(target_date.year)

        try:
            # Load the GHSL Built-up Surface collection and filter by epoch
            collection = ee.ImageCollection(self.GHSL_BUILT_S)

            # Filter to the specific epoch
            image = collection.filter(
                ee.Filter.eq("system:index", f"GHS_BUILT_S_E{target_epoch}_GLOBE_R2023A_54009_100_V1_0")
            ).first()

            if image is None:
                # Try alternative: get by epoch band
                image = collection.mosaic()

            # Select the built-up surface band
            image = image.select(["built_surface"])

            # Get bounds
            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            # Calculate dimensions based on resolution
            width = max(64, min(1024, int((east - west) * 111320 / resolution)))
            height = max(64, min(1024, int((north - south) * 111320 / resolution)))

            # Download using computePixels
            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": width, "height": height},
                    "affineTransform": {
                        "scaleX": (east - west) / width,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / height,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["built_surface"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(target_epoch, 1, 1),
                source=f"GHSL Built-up Surface (epoch {target_epoch})",
                bands=["built_surface"],
                resolution=float(resolution),
                metadata={
                    "dataset": self.GHSL_BUILT_S,
                    "epoch": target_epoch,
                    "requested_year": target_date.year,
                    "unit": "m²/pixel",
                },
            )

        except Exception as e:
            logger.error("Failed to get GHSL built surface data", error=str(e), exc_info=True)
            return None

    async def get_ghsl_settlement_model(
        self,
        geometry: Polygon,
        target_date: date,
    ) -> SatelliteImagery | None:
        """Get GHSL settlement model (SMOD) data for urban-rural classification.

        Settlement classes:
        - 30: Urban centre
        - 23: Dense urban cluster
        - 22: Semi-dense urban cluster
        - 21: Suburban or peri-urban
        - 13: Rural cluster
        - 12: Low density rural
        - 11: Very low density rural
        - 10: Water

        Args:
            geometry: Polygon defining the area of interest
            target_date: Target date (will use nearest available epoch)

        Returns:
            SatelliteImagery with settlement classification
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        target_epoch = self._get_nearest_epoch(target_date.year)

        try:
            collection = ee.ImageCollection(self.GHSL_SMOD)
            image = collection.mosaic().select(["smod_code"])

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            # SMOD is 1km resolution
            width = max(32, min(512, int((east - west) * 111.32)))
            height = max(32, min(512, int((north - south) * 111.32)))

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": width, "height": height},
                    "affineTransform": {
                        "scaleX": (east - west) / width,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / height,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["smod_code"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(target_epoch, 1, 1),
                source=f"GHSL Settlement Model (epoch {target_epoch})",
                bands=["smod_code"],
                resolution=1000.0,
                metadata={
                    "dataset": self.GHSL_SMOD,
                    "epoch": target_epoch,
                    "requested_year": target_date.year,
                    "settlement_classes": {
                        30: "Urban centre",
                        23: "Dense urban cluster",
                        22: "Semi-dense urban cluster",
                        21: "Suburban/peri-urban",
                        13: "Rural cluster",
                        12: "Low density rural",
                        11: "Very low density rural",
                        10: "Water",
                    },
                },
            )

        except Exception as e:
            logger.error("Failed to get GHSL SMOD data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get GHSL imagery - returns built surface data for available epochs in range."""
        results = []
        start_year = start_date.year
        end_year = end_date.year

        # Find epochs within the date range
        relevant_epochs = [e for e in self.AVAILABLE_EPOCHS if start_year <= e <= end_year]

        if not relevant_epochs:
            # Get nearest epoch
            relevant_epochs = [self._get_nearest_epoch((start_year + end_year) // 2)]

        for epoch in relevant_epochs:
            epoch_date = date(epoch, 1, 1)
            imagery = await self.get_ghsl_built_surface(geometry, epoch_date)
            if imagery:
                results.append(imagery)

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
        """Get GHSL data - returns single epoch nearest to date range center."""
        mid_date = date(
            (start_date.year + end_date.year) // 2,
            (start_date.month + end_date.month) // 2 or 1,
            1
        )
        return await self.get_ghsl_built_surface(geometry, mid_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available GHSL epoch dates."""
        return [date(e, 1, 1) for e in self.AVAILABLE_EPOCHS
                if start_date.year <= e <= end_date.year]

    @property
    def source_name(self) -> str:
        return "GHSL (Global Human Settlement Layer)"

    @property
    def available_bands(self) -> list[str]:
        return ["built_surface", "smod_code"]

    @property
    def native_resolution(self) -> float:
        return 100.0  # GHS_BUILT_S is 100m


class VIIRSClient(BaseSatelliteClient):
    """Client for VIIRS nighttime lights data from GEE."""

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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

        # Get bounds once
        bounds_info = aoi.bounds().getInfo()["coordinates"][0]
        west = min(c[0] for c in bounds_info)
        east = max(c[0] for c in bounds_info)
        south = min(c[1] for c in bounds_info)
        north = max(c[1] for c in bounds_info)

        for i in range(count):
            img = ee.Image(image_list.get(i))
            info = img.getInfo()
            img_date = date.fromtimestamp(
                info["properties"]["system:time_start"] / 1000
            )

            # Download actual data using computePixels
            # Use 512x512 for higher resolution nightlights visualization
            # VIIRS native resolution is ~375m, so 512 gives better detail
            grid_size = 512
            request = {
                "expression": img,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": grid_size, "height": grid_size},
                    "affineTransform": {
                        "scaleX": (east - west) / grid_size,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / grid_size,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            try:
                loop = asyncio.get_event_loop()
                pixels = await loop.run_in_executor(
                    None, lambda: ee.data.computePixels(request)
                )

                data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

                if data_array.dtype.names:
                    data = data_array["avg_rad"][np.newaxis, :, :]
                else:
                    data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

                data = data.astype(np.float32)
            except Exception as e:
                logger.error("Failed to download VIIRS image", error=str(e))
                data = np.zeros((1, grid_size, grid_size), dtype=np.float32)

            # Calculate actual resolution based on grid size and bounds
            actual_resolution = max(
                (east - west) * 111000 / grid_size,  # approx meters per pixel (lon)
                (north - south) * 111000 / grid_size  # approx meters per pixel (lat)
            )
            results.append(
                SatelliteImagery(
                    data=data,
                    bounds=(west, south, east, north),
                    crs="EPSG:4326",
                    date=img_date,
                    source="VIIRS DNB (GEE)",
                    bands=["avg_rad"],
                    resolution=actual_resolution,
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


class DynamicWorldClient(BaseSatelliteClient):
    """Client for Google Dynamic World land cover data from GEE.

    Provides near real-time land cover probabilities at 10m resolution.
    Classes: water, trees, grass, flooded_vegetation, crops, shrub_and_scrub,
    built, bare, snow_and_ice
    """

    DATASET_ID = "GOOGLE/DYNAMICWORLD/V1"
    LAND_COVER_CLASSES = [
        "water", "trees", "grass", "flooded_vegetation", "crops",
        "shrub_and_scrub", "built", "bare", "snow_and_ice"
    ]

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("Dynamic World client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for Dynamic World", error=str(e))
            raise

    async def get_land_cover_probabilities(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        land_cover_class: str = "built",
    ) -> SatelliteImagery | None:
        """Get land cover probability for a specific class.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date
            land_cover_class: One of the LAND_COVER_CLASSES

        Returns:
            SatelliteImagery with probability values (0-1)
        """
        if not self._initialized:
            await self.initialize()

        if land_cover_class not in self.LAND_COVER_CLASSES:
            raise ValueError(f"Invalid class. Must be one of: {self.LAND_COVER_CLASSES}")

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select([land_cover_class])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Create median composite
            image = collection.median()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array[land_cover_class][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source=f"Dynamic World ({land_cover_class})",
                bands=[land_cover_class],
                resolution=10.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "class": land_cover_class,
                    "unit": "probability",
                },
            )

        except Exception as e:
            logger.error("Failed to get Dynamic World data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get Dynamic World imagery - returns built-up probability by default."""
        imagery = await self.get_land_cover_probabilities(
            geometry, start_date, end_date, "built"
        )
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get Dynamic World composite."""
        return await self.get_land_cover_probabilities(
            geometry, start_date, end_date, bands[0] if bands else "built"
        )

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "Google Dynamic World"

    @property
    def available_bands(self) -> list[str]:
        return self.LAND_COVER_CLASSES

    @property
    def native_resolution(self) -> float:
        return 10.0


class JRCSurfaceWaterClient(BaseSatelliteClient):
    """Client for JRC Global Surface Water data from GEE.

    Provides monthly water occurrence data from 1984-2021 at 30m resolution.
    """

    DATASET_ID = "JRC/GSW1_4/MonthlyHistory"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("JRC Surface Water client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for JRC Surface Water", error=str(e))
            raise

    async def get_water_occurrence(
        self,
        geometry: Polygon,
        year: int,
        month: int,
    ) -> SatelliteImagery | None:
        """Get monthly water occurrence.

        Values:
        - 0: No data
        - 1: Not water
        - 2: Water

        Args:
            geometry: Area of interest
            year: Year (1984-2021)
            month: Month (1-12)

        Returns:
            SatelliteImagery with water occurrence
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            # Filter to specific month
            collection = ee.ImageCollection(self.DATASET_ID).filterBounds(aoi)

            # Create filter for year and month
            target_date = f"{year}-{month:02d}"
            image = collection.filter(
                ee.Filter.eq("system:index", target_date)
            ).first()

            if image is None:
                return None

            image = image.select(["water"])

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["water"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            # Convert to binary water mask (2 = water)
            data = (data == 2).astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(year, month, 1),
                source="JRC Global Surface Water",
                bands=["water"],
                resolution=30.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "year": year,
                    "month": month,
                    "unit": "binary",
                },
            )

        except Exception as e:
            logger.error("Failed to get JRC Surface Water data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get JRC Surface Water imagery."""
        imagery = await self.get_water_occurrence(
            geometry, start_date.year, start_date.month
        )
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get JRC Surface Water composite."""
        return await self.get_water_occurrence(
            geometry, start_date.year, start_date.month
        )

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (monthly from 1984-2021)."""
        dates = []
        current = date(max(start_date.year, 1984), start_date.month, 1)
        end = date(min(end_date.year, 2021), end_date.month, 1)
        while current <= end:
            dates.append(current)
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
        return dates

    @property
    def source_name(self) -> str:
        return "JRC Global Surface Water"

    @property
    def available_bands(self) -> list[str]:
        return ["water"]

    @property
    def native_resolution(self) -> float:
        return 30.0


class VIIRS375mFireClient(BaseSatelliteClient):
    """Client for VIIRS 375m active fire data from GEE.

    Provides near real-time active fire detections at 375m resolution.
    Includes Fire Radiative Power (FRP) for fire intensity analysis.
    """

    DATASET_ID = "NASA/LANCE/SNPP_VIIRS/C2"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("VIIRS 375m Fire client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for VIIRS Fire", error=str(e))
            raise

    async def get_active_fires(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get active fire detections with Fire Radiative Power.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with FRP values (MW)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["FRP"])  # Fire Radiative Power in MW
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Max composite to capture all fire detections
            image = collection.max()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["FRP"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            # Replace NaN/negative with 0
            data = np.nan_to_num(data, nan=0.0)
            data = np.clip(data, 0, None)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="VIIRS 375m Active Fire",
                bands=["FRP"],
                resolution=375.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "MW",
                },
            )

        except Exception as e:
            logger.error("Failed to get VIIRS Fire data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get VIIRS active fire imagery."""
        imagery = await self.get_active_fires(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get fire composite."""
        return await self.get_active_fires(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "VIIRS 375m Active Fire"

    @property
    def available_bands(self) -> list[str]:
        return ["FRP", "Bright_ti4", "Bright_ti5", "confidence"]

    @property
    def native_resolution(self) -> float:
        return 375.0


class Sentinel5PNO2Client(BaseSatelliteClient):
    """Client for Sentinel-5P NO2 data from GEE.

    Provides tropospheric NO2 column density at ~7km resolution.
    Useful for air quality monitoring and industrial activity tracking.
    """

    DATASET_ID = "COPERNICUS/S5P/OFFL/L3_NO2"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("Sentinel-5P NO2 client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for S5P NO2", error=str(e))
            raise

    async def get_no2(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get tropospheric NO2 column density.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with NO2 values (mol/m²)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["tropospheric_NO2_column_number_density"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Apply quality filtering (qa_value > 0.75)
            def filter_quality(img):
                qa = ee.Image(self.DATASET_ID).select("qa_value")
                return img.updateMask(qa.gt(0.75))

            # Create mean composite
            image = collection.mean()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["tropospheric_NO2_column_number_density"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="Sentinel-5P NO2",
                bands=["NO2"],
                resolution=7000.0,  # ~7km
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "mol/m²",
                },
            )

        except Exception as e:
            logger.error("Failed to get S5P NO2 data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get Sentinel-5P NO2 imagery."""
        imagery = await self.get_no2(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get NO2 composite."""
        return await self.get_no2(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (daily from 2018)."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "Sentinel-5P NO2"

    @property
    def available_bands(self) -> list[str]:
        return ["tropospheric_NO2_column_number_density", "qa_value"]

    @property
    def native_resolution(self) -> float:
        return 7000.0


class ERA5LandClient(BaseSatelliteClient):
    """Client for ERA5-Land reanalysis data from GEE.

    Provides hourly weather/climate data at ~11km resolution from 1950-present.
    Useful for temperature, precipitation, and weather context.
    """

    DATASET_ID = "ECMWF/ERA5_LAND/HOURLY"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("ERA5-Land client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for ERA5-Land", error=str(e))
            raise

    async def get_temperature(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get 2m air temperature.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with temperature values (°C)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["temperature_2m"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Create mean composite and convert from Kelvin to Celsius
            image = collection.mean().subtract(273.15)

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["temperature_2m"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="ERA5-Land Temperature",
                bands=["temperature_2m"],
                resolution=11132.0,  # ~11km
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "°C",
                },
            )

        except Exception as e:
            logger.error("Failed to get ERA5-Land temperature data", error=str(e), exc_info=True)
            return None

    async def get_precipitation(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get total precipitation.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with precipitation values (mm)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["total_precipitation_hourly"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Sum precipitation over period, convert m to mm
            image = collection.sum().multiply(1000)

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["total_precipitation_hourly"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)
            data = np.clip(data, 0, None)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="ERA5-Land Precipitation",
                bands=["precipitation"],
                resolution=11132.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "mm",
                },
            )

        except Exception as e:
            logger.error("Failed to get ERA5-Land precipitation data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get ERA5-Land imagery - returns temperature by default."""
        imagery = await self.get_temperature(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get ERA5-Land composite."""
        return await self.get_temperature(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (hourly from 1950)."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "ERA5-Land"

    @property
    def available_bands(self) -> list[str]:
        return ["temperature_2m", "total_precipitation_hourly", "u_component_of_wind_10m",
                "v_component_of_wind_10m", "surface_pressure"]

    @property
    def native_resolution(self) -> float:
        return 11132.0


class Sentinel5PAerosolClient(BaseSatelliteClient):
    """Client for Sentinel-5P Aerosol Index data from GEE.

    Provides UV Aerosol Index at ~7km resolution for smoke/dust tracking.
    """

    DATASET_ID = "COPERNICUS/S5P/OFFL/L3_AER_AI"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("Sentinel-5P Aerosol client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for S5P Aerosol", error=str(e))
            raise

    async def get_aerosol_index(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get UV Aerosol Index.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with aerosol index values
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["absorbing_aerosol_index"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Create mean composite
            image = collection.mean()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["absorbing_aerosol_index"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="Sentinel-5P Aerosol",
                bands=["aerosol_index"],
                resolution=7000.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "index",
                },
            )

        except Exception as e:
            logger.error("Failed to get S5P Aerosol data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get Sentinel-5P Aerosol imagery."""
        imagery = await self.get_aerosol_index(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get Aerosol composite."""
        return await self.get_aerosol_index(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "Sentinel-5P Aerosol"

    @property
    def available_bands(self) -> list[str]:
        return ["absorbing_aerosol_index"]

    @property
    def native_resolution(self) -> float:
        return 7000.0


class USDAcroplandClient(BaseSatelliteClient):
    """Client for USDA Cropland Data Layer (CDL) from GEE.

    Provides annual crop-specific land cover at 30m resolution.
    Covers CONUS from 2008-present.
    """

    DATASET_ID = "USDA/NASS/CDL"

    # Major crop codes
    CROP_CODES = {
        1: "Corn",
        5: "Soybeans",
        24: "Winter Wheat",
        28: "Oats",
        36: "Alfalfa",
        37: "Other Hay",
        61: "Fallow/Idle",
        176: "Grassland/Pasture",
    }

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("USDA CDL client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for USDA CDL", error=str(e))
            raise

    async def get_cropland(
        self,
        geometry: Polygon,
        year: int,
    ) -> SatelliteImagery | None:
        """Get cropland classification for a year.

        Args:
            geometry: Area of interest
            year: Year (2008-present)

        Returns:
            SatelliteImagery with crop type codes
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            # Filter to specific year
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filter(ee.Filter.calendarRange(year, year, "year"))
                .select(["cropland"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            image = collection.first()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["cropland"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(year, 1, 1),
                source="USDA Cropland Data Layer",
                bands=["cropland"],
                resolution=30.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "year": year,
                    "crop_codes": self.CROP_CODES,
                },
            )

        except Exception as e:
            logger.error("Failed to get USDA CDL data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get USDA CDL imagery."""
        imagery = await self.get_cropland(geometry, start_date.year)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get CDL for year."""
        return await self.get_cropland(geometry, start_date.year)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (annual from 2008)."""
        return [date(y, 1, 1) for y in range(max(2008, start_date.year), end_date.year + 1)]

    @property
    def source_name(self) -> str:
        return "USDA Cropland Data Layer"

    @property
    def available_bands(self) -> list[str]:
        return ["cropland", "cultivated", "confidence"]

    @property
    def native_resolution(self) -> float:
        return 30.0


class OpenETClient(BaseSatelliteClient):
    """Client for OpenET SSEBop evapotranspiration data from GEE.

    Provides monthly evapotranspiration at 30m resolution for CONUS.
    Useful for water stress detection and agricultural monitoring.
    """

    DATASET_ID = "OpenET/SSEBOP/CONUS/GRIDMET/MONTHLY/v2_0"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("OpenET client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for OpenET", error=str(e))
            raise

    async def get_evapotranspiration(
        self,
        geometry: Polygon,
        year: int,
        month: int,
    ) -> SatelliteImagery | None:
        """Get monthly evapotranspiration.

        Args:
            geometry: Area of interest
            year: Year
            month: Month (1-12)

        Returns:
            SatelliteImagery with ET values (mm)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"

            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date, end_date)
                .select(["et"])
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            image = collection.first()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["et"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)
            data = np.clip(data, 0, None)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(year, month, 1),
                source="OpenET SSEBop",
                bands=["et"],
                resolution=30.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "year": year,
                    "month": month,
                    "unit": "mm",
                },
            )

        except Exception as e:
            logger.error("Failed to get OpenET data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get OpenET imagery."""
        imagery = await self.get_evapotranspiration(
            geometry, start_date.year, start_date.month
        )
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get ET for month."""
        return await self.get_evapotranspiration(
            geometry, start_date.year, start_date.month
        )

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "OpenET SSEBop"

    @property
    def available_bands(self) -> list[str]:
        return ["et"]

    @property
    def native_resolution(self) -> float:
        return 30.0


class SMAPSoilMoistureClient(BaseSatelliteClient):
    """Client for SMAP Level-4 soil moisture data from GEE.

    Provides surface and root-zone soil moisture at 9km resolution.
    Useful for drought detection and agricultural monitoring.
    Uses NASA/SMAP/SPL4SMGP/008 dataset (March 2015 - present).
    """

    DATASET_ID = "NASA/SMAP/SPL4SMGP/008"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("SMAP client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for SMAP", error=str(e))
            raise

    async def get_soil_moisture(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get root-zone soil moisture.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with soil moisture (mm)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            collection = (
                ee.ImageCollection(self.DATASET_ID)
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["sm_surface"])  # Surface soil moisture (0-5cm) m³/m³
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            image = collection.mean()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["ssm"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="SMAP Soil Moisture",
                bands=["ssm"],
                resolution=10000.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "mm",
                },
            )

        except Exception as e:
            logger.error("Failed to get SMAP data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get SMAP imagery."""
        imagery = await self.get_soil_moisture(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get soil moisture composite."""
        return await self.get_soil_moisture(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "SMAP Soil Moisture"

    @property
    def available_bands(self) -> list[str]:
        return ["ssm", "susm", "smp"]

    @property
    def native_resolution(self) -> float:
        return 10000.0


class GAIAImperviousClient(BaseSatelliteClient):
    """Client for GAIA Impervious Surface data from GEE.

    Provides year of urbanization per pixel from 1985-2018 at 30m resolution.
    Excellent for urban expansion animations.
    """

    DATASET_ID = "Tsinghua/FROM-GLC/GAIA/v10"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("GAIA client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for GAIA", error=str(e))
            raise

    async def get_impervious_surface(
        self,
        geometry: Polygon,
        year: int,
    ) -> SatelliteImagery | None:
        """Get impervious surface extent up to a given year.

        Args:
            geometry: Area of interest
            year: Year (1985-2018) - returns all urbanization up to this year

        Returns:
            SatelliteImagery with binary impervious mask
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            # GAIA provides a single image with year of urbanization per pixel
            image = ee.Image(self.DATASET_ID)

            # Create binary mask for urbanized by target year
            # GAIA values: year of urbanization (1985-2018), 0 = not impervious
            urbanized = image.lte(year).And(image.gt(0))

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": urbanized,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                field_name = data_array.dtype.names[0]
                data = data_array[field_name][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(year, 1, 1),
                source="GAIA Impervious Surface",
                bands=["impervious"],
                resolution=30.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "year": year,
                    "unit": "binary",
                },
            )

        except Exception as e:
            logger.error("Failed to get GAIA data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get GAIA imagery."""
        imagery = await self.get_impervious_surface(geometry, start_date.year)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get impervious surface."""
        return await self.get_impervious_surface(geometry, start_date.year)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (annual 1985-2018)."""
        return [date(y, 1, 1) for y in range(max(1985, start_date.year), min(2018, end_date.year) + 1)]

    @property
    def source_name(self) -> str:
        return "GAIA Impervious Surface"

    @property
    def available_bands(self) -> list[str]:
        return ["change_year_index"]

    @property
    def native_resolution(self) -> float:
        return 30.0


class FIRMSClient(BaseSatelliteClient):
    """Client for MODIS FIRMS active fire data from GEE.

    Provides historical fire archive from 2000-present at 1km resolution.
    Longer history than VIIRS 375m but lower resolution.
    """

    DATASET_ID = "FIRMS"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("FIRMS client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for FIRMS", error=str(e))
            raise

    async def get_active_fires(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
    ) -> SatelliteImagery | None:
        """Get MODIS active fire detections.

        Args:
            geometry: Area of interest
            start_date: Start date
            end_date: End date

        Returns:
            SatelliteImagery with fire confidence values
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            # Use MODIS thermal anomalies
            collection = (
                ee.ImageCollection("MODIS/061/MOD14A1")
                .filterBounds(aoi)
                .filterDate(start_date.isoformat(), end_date.isoformat())
                .select(["MaxFRP"])  # Maximum Fire Radiative Power
            )

            count = collection.size().getInfo()
            if count == 0:
                return None

            # Max composite to capture all fires
            image = collection.max()

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["MaxFRP"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)
            data = np.clip(data, 0, None)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="MODIS FIRMS",
                bands=["MaxFRP"],
                resolution=1000.0,
                metadata={
                    "dataset": "MODIS/061/MOD14A1",
                    "unit": "MW",
                },
            )

        except Exception as e:
            logger.error("Failed to get FIRMS data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get FIRMS imagery."""
        imagery = await self.get_active_fires(geometry, start_date, end_date)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get fire composite."""
        return await self.get_active_fires(geometry, start_date, end_date)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (from 2000)."""
        return [start_date, end_date]

    @property
    def source_name(self) -> str:
        return "MODIS FIRMS"

    @property
    def available_bands(self) -> list[str]:
        return ["MaxFRP", "FireMask"]

    @property
    def native_resolution(self) -> float:
        return 1000.0


class GEDIClient(BaseSatelliteClient):
    """Client for GEDI vegetation structure data from GEE.

    Provides LiDAR-derived canopy height and biomass at 1km resolution.
    Useful for forest structure baseline and carbon estimation.
    """

    DATASET_ID = "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM"

    def __init__(self):
        super().__init__()
        self._ee = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize Earth Engine."""
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
            logger.info("GEDI client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GEE for GEDI", error=str(e))
            raise

    async def get_canopy_height(
        self,
        geometry: Polygon,
    ) -> SatelliteImagery | None:
        """Get canopy height data.

        Args:
            geometry: Area of interest

        Returns:
            SatelliteImagery with canopy height (m)
        """
        if not self._initialized:
            await self.initialize()

        ee = self._ee
        aoi = ee.Geometry.Polygon(list(geometry.exterior.coords))

        try:
            # GEDI gridded vegetation structure
            image = ee.Image(self.DATASET_ID).select(["rh98"])  # 98th percentile height

            bounds_info = aoi.bounds().getInfo()["coordinates"][0]
            west = min(c[0] for c in bounds_info)
            east = max(c[0] for c in bounds_info)
            south = min(c[1] for c in bounds_info)
            north = max(c[1] for c in bounds_info)

            request = {
                "expression": image,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": 512, "height": 512},
                    "affineTransform": {
                        "scaleX": (east - west) / 512,
                        "shearX": 0,
                        "translateX": west,
                        "shearY": 0,
                        "scaleY": -(north - south) / 512,
                        "translateY": north,
                    },
                    "crsCode": "EPSG:4326",
                },
            }

            loop = asyncio.get_event_loop()
            pixels = await loop.run_in_executor(
                None, lambda: ee.data.computePixels(request)
            )

            data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

            if data_array.dtype.names:
                data = data_array["rh98"][np.newaxis, :, :]
            else:
                data = data_array if data_array.ndim == 3 else data_array[np.newaxis, :, :]

            data = data.astype(np.float32)
            data = np.nan_to_num(data, nan=0.0)
            data = np.clip(data, 0, None)

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=date(2020, 1, 1),  # GEDI is a static dataset
                source="GEDI Canopy Height",
                bands=["rh98"],
                resolution=1000.0,
                metadata={
                    "dataset": self.DATASET_ID,
                    "unit": "m",
                },
            )

        except Exception as e:
            logger.error("Failed to get GEDI data", error=str(e), exc_info=True)
            return None

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Get GEDI imagery."""
        imagery = await self.get_canopy_height(geometry)
        return [imagery] if imagery else []

    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """Get canopy height."""
        return await self.get_canopy_height(geometry)

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available dates (static dataset)."""
        return [date(2020, 1, 1)]

    @property
    def source_name(self) -> str:
        return "GEDI Vegetation Structure"

    @property
    def available_bands(self) -> list[str]:
        return ["rh98", "rh50", "cover", "agbd"]

    @property
    def native_resolution(self) -> float:
        return 1000.0
