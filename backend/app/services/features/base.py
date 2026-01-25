from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
from shapely.geometry import Polygon

from app.services.satellite.base import SatelliteImagery


@dataclass
class FeatureResult:
    """Container for extracted feature data."""

    metric_name: str
    value: float  # Aggregate value for the region
    raster: np.ndarray | None = field(default=None)  # Optional spatial raster
    bounds: tuple[float, float, float, float] | None = field(default=None)
    date: date | None = field(default=None)
    unit: str = field(default="")
    metadata: dict[str, Any] | None = field(default=None)


class BaseFeatureExtractor(ABC):
    """Abstract base class for feature extractors."""

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Name of the metric this extractor produces."""
        pass

    @property
    @abstractmethod
    def required_bands(self) -> list[str]:
        """List of band names required for this feature."""
        pass

    @property
    @abstractmethod
    def unit(self) -> str:
        """Unit of measurement for this metric."""
        pass

    @abstractmethod
    async def extract(
        self,
        imagery: SatelliteImagery,
        geometry: Polygon | None = None,
    ) -> FeatureResult:
        """
        Extract the feature from satellite imagery.

        Args:
            imagery: Input satellite imagery
            geometry: Optional polygon to mask the result

        Returns:
            FeatureResult with the extracted metric
        """
        pass

    def _mask_by_geometry(
        self,
        raster: np.ndarray,
        geometry: Polygon,
        bounds: tuple[float, float, float, float],
    ) -> np.ndarray:
        """Mask a raster by a polygon geometry."""
        from rasterio.features import geometry_mask
        from rasterio.transform import from_bounds

        height, width = raster.shape[-2:]
        transform = from_bounds(*bounds, width, height)

        mask = geometry_mask(
            [geometry],
            out_shape=(height, width),
            transform=transform,
            invert=True,
        )

        masked = raster.copy()
        if masked.ndim == 2:
            masked[~mask] = np.nan
        else:
            masked[:, ~mask] = np.nan

        return masked
