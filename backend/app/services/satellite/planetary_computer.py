import asyncio
from datetime import date
from typing import Any

import httpx
import numpy as np
from shapely.geometry import Polygon, box, mapping

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.satellite.base import BaseSatelliteClient, SatelliteImagery

logger = get_logger(__name__)


class PlanetaryComputerClient(BaseSatelliteClient):
    """Microsoft Planetary Computer client for satellite data."""

    STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
    SENTINEL2_COLLECTION = "sentinel-2-l2a"

    BAND_MAPPING = {
        "B01": "coastal",
        "B02": "blue",
        "B03": "green",
        "B04": "red",
        "B05": "rededge1",
        "B06": "rededge2",
        "B07": "rededge3",
        "B08": "nir",
        "B8A": "nir08",
        "B09": "nir09",
        "B11": "swir16",
        "B12": "swir22",
        "SCL": "scl",
    }

    def __init__(self):
        super().__init__()
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the Planetary Computer client."""
        if self._initialized:
            return

        try:
            import planetary_computer
            import pystac_client

            self._pc = planetary_computer
            self._catalog = pystac_client.Client.open(
                self.STAC_API_URL,
                modifier=planetary_computer.sign_inplace,
            )
            self._client = httpx.AsyncClient(timeout=60.0)
            self._initialized = True
            logger.info("Planetary Computer client initialized")
        except Exception as e:
            logger.error("Failed to initialize Planetary Computer", error=str(e))
            raise

    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """Retrieve Sentinel-2 imagery from Planetary Computer."""
        if not self._initialized:
            await self.initialize()

        # Search for items
        search = self._catalog.search(
            collections=[self.SENTINEL2_COLLECTION],
            intersects=mapping(geometry),
            datetime=f"{start_date.isoformat()}/{end_date.isoformat()}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        )

        items = list(search.items())
        if not items:
            logger.warning(
                "No imagery found in Planetary Computer",
                geometry=str(geometry.bounds),
                start_date=str(start_date),
                end_date=str(end_date),
            )
            return []

        results = []
        for item in items[:50]:  # Limit to 50 items
            img_data = await self._load_item(item, geometry, bands)
            if img_data is not None:
                results.append(img_data)

        return results

    async def _load_item(
        self,
        item: Any,
        geometry: Polygon,
        bands: list[str] | None = None,
    ) -> SatelliteImagery | None:
        """Load a single STAC item."""
        try:
            import rioxarray
            import stackstac

            # Map band names
            if bands is None:
                bands = ["B04", "B03", "B02", "B08"]

            asset_bands = [self.BAND_MAPPING.get(b, b.lower()) for b in bands]

            # Get bounds
            west, south, east, north = geometry.bounds

            # Use stackstac to load the data
            data_array = stackstac.stack(
                [item],
                assets=asset_bands,
                bounds=(west, south, east, north),
                epsg=4326,
                resolution=10,
            )

            # Load a small preview
            data = data_array.isel(time=0).values

            img_date = date.fromisoformat(item.datetime.strftime("%Y-%m-%d"))
            cloud_cover = item.properties.get("eo:cloud_cover")

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=img_date,
                source="Sentinel-2 (Planetary Computer)",
                bands=bands,
                resolution=10.0,
                cloud_cover=cloud_cover,
                metadata=dict(item.properties),
            )

        except Exception as e:
            logger.error("Failed to load STAC item", error=str(e), item_id=item.id)
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
        """Create a composite from multiple images."""
        if not self._initialized:
            await self.initialize()

        import stackstac

        # Search for items
        search = self._catalog.search(
            collections=[self.SENTINEL2_COLLECTION],
            intersects=mapping(geometry),
            datetime=f"{start_date.isoformat()}/{end_date.isoformat()}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        )

        items = list(search.items())
        if not items:
            return None

        # Map band names
        if bands is None:
            bands = ["B04", "B03", "B02", "B08"]
        asset_bands = [self.BAND_MAPPING.get(b, b.lower()) for b in bands]

        west, south, east, north = geometry.bounds

        try:
            # Stack all items
            data_array = stackstac.stack(
                items,
                assets=asset_bands,
                bounds=(west, south, east, north),
                epsg=4326,
                resolution=10,
            )

            # Apply composite method
            if composite_method == "median":
                composite = data_array.median(dim="time")
            elif composite_method == "mean":
                composite = data_array.mean(dim="time")
            else:
                composite = data_array.isel(time=-1)  # Most recent

            data = composite.values

            return SatelliteImagery(
                data=data,
                bounds=(west, south, east, north),
                crs="EPSG:4326",
                date=start_date,
                source="Sentinel-2 Composite (Planetary Computer)",
                bands=bands,
                resolution=10.0,
                metadata={
                    "composite_method": composite_method,
                    "image_count": len(items),
                },
            )

        except Exception as e:
            logger.error("Failed to create composite", error=str(e))
            return None

    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get available imagery dates."""
        if not self._initialized:
            await self.initialize()

        search = self._catalog.search(
            collections=[self.SENTINEL2_COLLECTION],
            intersects=mapping(geometry),
            datetime=f"{start_date.isoformat()}/{end_date.isoformat()}",
            query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        )

        dates = set()
        for item in search.items():
            if item.datetime:
                dates.add(date.fromisoformat(item.datetime.strftime("%Y-%m-%d")))

        return sorted(dates)

    @property
    def source_name(self) -> str:
        return "Microsoft Planetary Computer"

    @property
    def available_bands(self) -> list[str]:
        return list(self.BAND_MAPPING.keys())

    @property
    def native_resolution(self) -> float:
        return 10.0
