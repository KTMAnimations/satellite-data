from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
from shapely.geometry import Polygon


@dataclass
class SatelliteImagery:
    """Container for satellite imagery data."""

    data: np.ndarray
    bounds: tuple[float, float, float, float]  # west, south, east, north
    crs: str
    date: date
    source: str
    bands: list[str]
    resolution: float  # meters
    cloud_cover: float | None = None
    metadata: dict[str, Any] | None = None

    @property
    def width(self) -> int:
        return self.data.shape[-1]

    @property
    def height(self) -> int:
        return self.data.shape[-2]

    @property
    def num_bands(self) -> int:
        if self.data.ndim == 2:
            return 1
        return self.data.shape[0]


class BaseSatelliteClient(ABC):
    """Abstract base class for satellite data providers."""

    def __init__(self):
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the client and authenticate if needed."""
        pass

    @abstractmethod
    async def get_imagery(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
    ) -> list[SatelliteImagery]:
        """
        Retrieve satellite imagery for a given geometry and time range.

        Args:
            geometry: Polygon defining the area of interest
            start_date: Start of the time range
            end_date: End of the time range
            bands: Specific bands to retrieve (None for all available)
            max_cloud_cover: Maximum acceptable cloud cover percentage

        Returns:
            List of SatelliteImagery objects
        """
        pass

    @abstractmethod
    async def get_composite(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        bands: list[str] | None = None,
        max_cloud_cover: float = 20.0,
        composite_method: str = "median",
    ) -> SatelliteImagery | None:
        """
        Create a cloud-free composite for a time period.

        Args:
            geometry: Polygon defining the area of interest
            start_date: Start of the time range
            end_date: End of the time range
            bands: Specific bands to retrieve
            max_cloud_cover: Maximum acceptable cloud cover percentage
            composite_method: Method for combining images ('median', 'mean', 'mosaic')

        Returns:
            Composite SatelliteImagery or None if no valid data
        """
        pass

    @abstractmethod
    async def get_available_dates(
        self,
        geometry: Polygon,
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
    ) -> list[date]:
        """Get dates with available imagery for a region."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source."""
        pass

    @property
    @abstractmethod
    def available_bands(self) -> list[str]:
        """Return list of available band names."""
        pass

    @property
    @abstractmethod
    def native_resolution(self) -> float:
        """Return the native resolution in meters."""
        pass
