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
