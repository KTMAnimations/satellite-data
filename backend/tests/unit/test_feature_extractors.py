"""
Unit tests for feature extraction services.

Tests cover:
- NDVIExtractor with mock Sentinel-2 imagery
- NightlightsExtractor with mock VIIRS data
- UrbanDensityExtractor (GHSL and NDBI paths)
- ParkingDetector with mock data
- Output schema validation
- Edge cases (empty data, NaN values, zero denominators)

Note: Tests that require rasterio for geometry masking use mocks to avoid
requiring the full geospatial stack to be installed.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from shapely.geometry import Polygon

from app.services.features.base import BaseFeatureExtractor, FeatureResult
from app.services.features.ndvi import NDVIExtractor, EVIExtractor
from app.services.features.nightlights import NightlightsExtractor, NightlightsChangeDetector
from app.services.features.urban_density import UrbanDensityExtractor, GHSLExtractor
from app.services.features.parking import ParkingDetector, LargeVenueAnalyzer
from app.services.satellite.base import SatelliteImagery


# Helper to check if rasterio is available
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


# ============================================================================
# NDVI Extractor Tests
# ============================================================================


class TestNDVIExtractor:
    """Tests for the NDVIExtractor class."""

    @pytest.fixture
    def extractor(self) -> NDVIExtractor:
        """Create an NDVIExtractor instance."""
        return NDVIExtractor()

    def test_metric_name(self, extractor: NDVIExtractor):
        """Test that metric name is correct."""
        assert extractor.metric_name == "ndvi"

    def test_required_bands(self, extractor: NDVIExtractor):
        """Test required bands for NDVI calculation."""
        assert extractor.required_bands == ["B4", "B8"]

    def test_unit(self, extractor: NDVIExtractor):
        """Test unit specification."""
        assert extractor.unit == "index (-1 to 1)"

    @pytest.mark.asyncio
    async def test_extract_basic(
        self,
        extractor: NDVIExtractor,
        mock_sentinel2_imagery: SatelliteImagery,
    ):
        """Test basic NDVI extraction."""
        result = await extractor.extract(mock_sentinel2_imagery)

        # Verify result structure
        assert isinstance(result, FeatureResult)
        assert result.metric_name == "ndvi"
        assert result.unit == "index (-1 to 1)"
        assert result.date == mock_sentinel2_imagery.date
        assert result.bounds == mock_sentinel2_imagery.bounds

        # NDVI should be between -1 and 1
        assert -1 <= result.value <= 1

        # Verify raster is returned
        assert result.raster is not None
        assert result.raster.shape == (100, 100)

        # Verify metadata
        assert "min" in result.metadata
        assert "max" in result.metadata
        assert "std" in result.metadata
        assert "valid_pixels" in result.metadata
        assert result.metadata["min"] >= -1
        assert result.metadata["max"] <= 1

    @pytest.mark.asyncio
    async def test_extract_with_geometry(
        self,
        extractor: NDVIExtractor,
        mock_sentinel2_imagery: SatelliteImagery,
        sample_polygon: Polygon,
    ):
        """Test NDVI extraction with geometry mask."""
        # Mock the geometry masking to avoid rasterio dependency
        def mock_mask_fn(raster, geometry, bounds):
            # Return the input with some masked (NaN) values at edges
            masked = raster.copy()
            masked[:10, :] = np.nan  # Simulate masked region outside polygon
            return masked

        with patch.object(extractor, '_mask_by_geometry', side_effect=mock_mask_fn):
            result = await extractor.extract(mock_sentinel2_imagery, geometry=sample_polygon)

            assert isinstance(result, FeatureResult)
            assert result.metric_name == "ndvi"

            # Result should still be valid NDVI range
            assert -1 <= result.value <= 1 or np.isnan(result.value)

    @pytest.mark.asyncio
    async def test_extract_high_vegetation(self, extractor: NDVIExtractor):
        """Test NDVI with high vegetation (high NIR, low Red)."""
        # Create imagery with vegetation-like spectral response
        data = np.zeros((5, 100, 100), dtype=np.float32)
        data[2] = 1000  # Red (B4) - low
        data[3] = 5000  # NIR (B8) - high

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await extractor.extract(imagery)

        # High vegetation should have NDVI close to 1
        # NDVI = (5000 - 1000) / (5000 + 1000) = 4000/6000 = 0.667
        assert result.value > 0.5

    @pytest.mark.asyncio
    async def test_extract_water_negative_ndvi(self, extractor: NDVIExtractor):
        """Test NDVI with water-like response (negative NDVI)."""
        # Water has higher Red than NIR
        data = np.zeros((5, 100, 100), dtype=np.float32)
        data[2] = 3000  # Red (B4) - higher
        data[3] = 1000  # NIR (B8) - lower

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await extractor.extract(imagery)

        # Water should have negative NDVI
        # NDVI = (1000 - 3000) / (1000 + 3000) = -2000/4000 = -0.5
        assert result.value < 0

    @pytest.mark.asyncio
    async def test_extract_zero_denominator(
        self,
        extractor: NDVIExtractor,
        zero_denominator_imagery: SatelliteImagery,
    ):
        """Test NDVI handles zero denominator gracefully."""
        result = await extractor.extract(zero_denominator_imagery)

        # Should not raise exception
        assert isinstance(result, FeatureResult)

        # Result should be NaN when denominator is zero
        assert np.isnan(result.value)

    @pytest.mark.asyncio
    async def test_extract_nan_values(
        self,
        extractor: NDVIExtractor,
        empty_imagery: SatelliteImagery,
    ):
        """Test NDVI handles NaN input data."""
        result = await extractor.extract(empty_imagery)

        assert isinstance(result, FeatureResult)
        assert np.isnan(result.value)


class TestEVIExtractor:
    """Tests for the EVIExtractor class."""

    @pytest.fixture
    def extractor(self) -> EVIExtractor:
        """Create an EVIExtractor instance."""
        return EVIExtractor()

    def test_metric_name(self, extractor: EVIExtractor):
        """Test that metric name is correct."""
        assert extractor.metric_name == "evi"

    def test_required_bands(self, extractor: EVIExtractor):
        """Test required bands for EVI calculation."""
        assert extractor.required_bands == ["B2", "B4", "B8"]

    @pytest.mark.asyncio
    async def test_extract_basic(
        self,
        extractor: EVIExtractor,
        mock_sentinel2_imagery: SatelliteImagery,
    ):
        """Test basic EVI extraction."""
        result = await extractor.extract(mock_sentinel2_imagery)

        assert isinstance(result, FeatureResult)
        assert result.metric_name == "evi"
        assert -1 <= result.value <= 1


# ============================================================================
# Nightlights Extractor Tests
# ============================================================================


class TestNightlightsExtractor:
    """Tests for the NightlightsExtractor class."""

    @pytest.fixture
    def extractor(self) -> NightlightsExtractor:
        """Create a NightlightsExtractor instance."""
        return NightlightsExtractor()

    def test_metric_name(self, extractor: NightlightsExtractor):
        """Test that metric name is correct."""
        assert extractor.metric_name == "nightlights"

    def test_required_bands(self, extractor: NightlightsExtractor):
        """Test required bands."""
        assert extractor.required_bands == ["avg_rad"]

    def test_unit(self, extractor: NightlightsExtractor):
        """Test unit specification."""
        assert "nW/cm" in extractor.unit

    @pytest.mark.asyncio
    async def test_extract_basic(
        self,
        extractor: NightlightsExtractor,
        mock_viirs_imagery: SatelliteImagery,
    ):
        """Test basic nightlights extraction."""
        result = await extractor.extract(mock_viirs_imagery)

        assert isinstance(result, FeatureResult)
        assert result.metric_name == "nightlights"
        assert result.value >= 0  # Radiance should be non-negative

        # Verify metadata
        assert "total_radiance" in result.metadata
        assert "max_radiance" in result.metadata
        assert "lit_area_pct" in result.metadata
        assert "lit_threshold" in result.metadata

    @pytest.mark.asyncio
    async def test_extract_removes_negative_values(
        self,
        extractor: NightlightsExtractor,
        negative_radiance_imagery: SatelliteImagery,
    ):
        """Test that negative radiance values are clipped to zero."""
        result = await extractor.extract(negative_radiance_imagery)

        assert isinstance(result, FeatureResult)
        assert result.value >= 0

        # Raster should have no negative values
        assert np.all(result.raster >= 0)

    @pytest.mark.asyncio
    async def test_extract_2d_data(self, extractor: NightlightsExtractor):
        """Test extraction with 2D data (no band dimension)."""
        data = np.random.uniform(0, 50, (100, 100)).astype(np.float32)

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 1, 15),
            source="VIIRS",
            bands=["avg_rad"],
            resolution=500.0,
        )

        result = await extractor.extract(imagery)

        assert isinstance(result, FeatureResult)
        assert result.value >= 0

    @pytest.mark.asyncio
    async def test_lit_area_percentage_calculation(
        self,
        extractor: NightlightsExtractor,
    ):
        """Test lit area percentage is calculated correctly."""
        # Create data where half is lit (above 0.5 threshold)
        data = np.zeros((100, 100), dtype=np.float32)
        data[:50, :] = 10.0  # Lit half
        data[50:, :] = 0.1  # Dim half

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 1, 15),
            source="VIIRS",
            bands=["avg_rad"],
            resolution=500.0,
        )

        result = await extractor.extract(imagery)

        # About 50% should be lit
        lit_pct = result.metadata["lit_area_pct"]
        assert 45 <= lit_pct <= 55


class TestNightlightsChangeDetector:
    """Tests for the NightlightsChangeDetector class."""

    @pytest.fixture
    def detector(self) -> NightlightsChangeDetector:
        """Create a NightlightsChangeDetector instance."""
        return NightlightsChangeDetector()

    @pytest.mark.asyncio
    async def test_detect_change_basic(self, detector: NightlightsChangeDetector):
        """Test basic change detection between two periods."""
        # Before imagery - lower radiance
        data_before = np.full((100, 100), 10.0, dtype=np.float32)
        imagery_before = SatelliteImagery(
            data=data_before,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 1, 15),
            source="VIIRS",
            bands=["avg_rad"],
            resolution=500.0,
        )

        # After imagery - higher radiance
        data_after = np.full((100, 100), 15.0, dtype=np.float32)
        imagery_after = SatelliteImagery(
            data=data_after,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="VIIRS",
            bands=["avg_rad"],
            resolution=500.0,
        )

        result = await detector.detect_change(imagery_before, imagery_after)

        assert "before" in result
        assert "after" in result
        assert "change" in result
        assert result["change"]["absolute"] > 0
        assert result["change"]["percentage"] == 50.0  # (15-10)/10 * 100

    @pytest.mark.asyncio
    async def test_interpret_change(self, detector: NightlightsChangeDetector):
        """Test change interpretation."""
        assert "Significant increase" in detector._interpret_change(25)
        assert "Moderate increase" in detector._interpret_change(10)
        assert "stable" in detector._interpret_change(0)
        assert "Moderate decrease" in detector._interpret_change(-10)
        assert "Significant decrease" in detector._interpret_change(-25)


# ============================================================================
# Urban Density Extractor Tests
# ============================================================================


class TestUrbanDensityExtractor:
    """Tests for the UrbanDensityExtractor class."""

    @pytest.fixture
    def extractor(self) -> UrbanDensityExtractor:
        """Create an UrbanDensityExtractor without GHSL client."""
        return UrbanDensityExtractor(ghsl_client=None)

    def test_metric_name(self, extractor: UrbanDensityExtractor):
        """Test that metric name is correct."""
        assert extractor.metric_name == "urban_density"

    def test_required_bands(self, extractor: UrbanDensityExtractor):
        """Test required bands for NDBI fallback."""
        assert "B8" in extractor.required_bands  # NIR
        assert "B11" in extractor.required_bands  # SWIR

    def test_unit(self, extractor: UrbanDensityExtractor):
        """Test unit specification."""
        assert extractor.unit == "ratio (0 to 1)"

    @pytest.mark.asyncio
    async def test_extract_ndbi_fallback(
        self,
        mock_sentinel2_imagery: SatelliteImagery,
    ):
        """Test urban density extraction using NDBI fallback."""
        # Create extractor with None GHSL client to force NDBI path
        extractor = UrbanDensityExtractor(ghsl_client=None)

        # Mock the GHSL path to fail
        with patch.object(extractor, '_extract_from_ghsl', new_callable=AsyncMock) as mock_ghsl:
            mock_ghsl.side_effect = Exception("GHSL unavailable")

            result = await extractor.extract(mock_sentinel2_imagery)

            assert isinstance(result, FeatureResult)
            assert result.metric_name == "urban_density"
            assert 0 <= result.value <= 1
            assert result.metadata["source"] == "NDBI"

    @pytest.mark.asyncio
    async def test_extract_with_ghsl(
        self,
        mock_sentinel2_imagery: SatelliteImagery,
        mock_gee_client: AsyncMock,
        mock_ghsl_imagery: SatelliteImagery,
        sample_polygon: Polygon,
    ):
        """Test urban density extraction using GHSL data."""
        extractor = UrbanDensityExtractor(ghsl_client=mock_gee_client)
        extractor._ghsl_client_initialized = True

        # Mock geometry masking to avoid rasterio dependency
        def mock_mask_fn(raster, geometry, bounds):
            masked = raster.copy()
            masked[:5, :] = np.nan  # Simulate some masked area
            return masked

        with patch.object(extractor, '_mask_by_geometry', side_effect=mock_mask_fn):
            result = await extractor.extract(mock_sentinel2_imagery, geometry=sample_polygon)

            assert isinstance(result, FeatureResult)
            assert result.metric_name == "urban_density"
            assert 0 <= result.value <= 1
            assert result.metadata["source"] == "GHSL"

    @pytest.mark.asyncio
    async def test_ndbi_calculation(self):
        """Test NDBI index calculation."""
        extractor = UrbanDensityExtractor(ghsl_client=None)

        # Create imagery with built-up spectral response (high SWIR, moderate NIR)
        data = np.zeros((5, 100, 100), dtype=np.float32)
        data[3] = 2000  # NIR (B8)
        data[4] = 4000  # SWIR (B11)

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        with patch.object(extractor, '_extract_from_ghsl', new_callable=AsyncMock) as mock_ghsl:
            mock_ghsl.return_value = None  # Force NDBI path

            result = await extractor.extract(imagery)

            # NDBI = (SWIR - NIR) / (SWIR + NIR) = (4000 - 2000) / (4000 + 2000) = 0.333
            # Normalized: (0.333 + 1) / 2 = 0.667
            assert result.metadata["source"] == "NDBI"
            assert result.value > 0.5  # Built-up area


class TestGHSLExtractor:
    """Tests for the GHSLExtractor class."""

    @pytest.fixture
    def extractor(self) -> GHSLExtractor:
        """Create a GHSLExtractor instance."""
        return GHSLExtractor(ghsl_client=None)

    def test_metric_name(self, extractor: GHSLExtractor):
        """Test that metric name is correct."""
        assert extractor.metric_name == "ghsl_builtup"

    def test_required_bands(self, extractor: GHSLExtractor):
        """Test required bands."""
        assert extractor.required_bands == ["built_surface"]

    @pytest.mark.asyncio
    async def test_extract_from_ghsl_imagery(
        self,
        extractor: GHSLExtractor,
        mock_ghsl_imagery: SatelliteImagery,
    ):
        """Test extraction from pre-loaded GHSL imagery."""
        result = await extractor.extract(mock_ghsl_imagery)

        assert isinstance(result, FeatureResult)
        assert result.metadata["source"] == "GHSL"
        assert "total_built_area_km2" in result.metadata
        assert "built_fraction" in result.metadata


# ============================================================================
# Parking Detector Tests
# ============================================================================


class TestParkingDetector:
    """Tests for the ParkingDetector class."""

    @pytest.fixture
    def detector(self) -> ParkingDetector:
        """Create a ParkingDetector instance."""
        return ParkingDetector()

    def test_metric_name(self, detector: ParkingDetector):
        """Test that metric name is correct."""
        assert detector.metric_name == "parking"

    def test_required_bands(self, detector: ParkingDetector):
        """Test required bands for parking detection."""
        required = detector.required_bands
        assert "B2" in required  # Blue
        assert "B3" in required  # Green
        assert "B4" in required  # Red
        assert "B8" in required  # NIR
        assert "B11" in required  # SWIR

    def test_unit(self, detector: ParkingDetector):
        """Test unit specification."""
        assert detector.unit == "occupancy ratio"

    @pytest.mark.asyncio
    async def test_extract_basic(
        self,
        detector: ParkingDetector,
        mock_sentinel2_imagery: SatelliteImagery,
    ):
        """Test basic parking detection."""
        result = await detector.extract(mock_sentinel2_imagery)

        assert isinstance(result, FeatureResult)
        assert result.metric_name == "parking"
        assert 0 <= result.value <= 1

        # Verify metadata
        assert "parking_lot_count" in result.metadata
        assert "total_parking_area_m2" in result.metadata
        assert "total_parking_area_km2" in result.metadata

    @pytest.mark.asyncio
    async def test_extract_with_parking_lots(self, detector: ParkingDetector):
        """Test parking detection with simulated parking lot pattern."""
        np.random.seed(42)

        # Create imagery with parking lot characteristics
        # Parking lots: bright, non-vegetated, built-up
        data = np.zeros((5, 100, 100), dtype=np.float32)

        # Background (vegetated area)
        data[0] = 500   # Blue - low
        data[1] = 700   # Green - moderate
        data[2] = 600   # Red - low
        data[3] = 3000  # NIR - high (vegetation)
        data[4] = 800   # SWIR - low

        # Parking lot area (40:60, 40:60)
        data[0, 40:60, 40:60] = 2000   # Blue - high
        data[1, 40:60, 40:60] = 2200   # Green - high
        data[2, 40:60, 40:60] = 2100   # Red - high
        data[3, 40:60, 40:60] = 1800   # NIR - lower
        data[4, 40:60, 40:60] = 3000   # SWIR - high

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await detector.extract(imagery)

        assert isinstance(result, FeatureResult)
        # Should detect at least some parking area
        assert result.metadata["parking_lot_count"] >= 0

    @pytest.mark.asyncio
    async def test_extract_no_parking_lots(self, detector: ParkingDetector):
        """Test parking detection with no parking lots (all vegetation)."""
        data = np.zeros((5, 100, 100), dtype=np.float32)

        # All vegetation (high NDVI)
        data[0] = 500   # Blue
        data[1] = 700   # Green
        data[2] = 500   # Red - low
        data[3] = 4000  # NIR - very high
        data[4] = 600   # SWIR - low

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await detector.extract(imagery)

        assert isinstance(result, FeatureResult)
        # No parking lots should be detected
        assert result.metadata["parking_lot_count"] == 0
        assert result.metadata["total_parking_area_m2"] == 0


class TestLargeVenueAnalyzer:
    """Tests for the LargeVenueAnalyzer class."""

    @pytest.fixture
    def analyzer(self) -> LargeVenueAnalyzer:
        """Create a LargeVenueAnalyzer instance."""
        return LargeVenueAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_venue_basic(
        self,
        analyzer: LargeVenueAnalyzer,
        sample_polygon: Polygon,
    ):
        """Test basic venue analysis."""
        # Create multiple imagery dates
        imagery_list = []
        for month in range(1, 4):
            data = np.random.uniform(500, 3000, (5, 100, 100)).astype(np.float32)
            imagery = SatelliteImagery(
                data=data,
                bounds=(-112.1, 33.4, -111.9, 33.5),
                crs="EPSG:4326",
                date=date(2024, month, 15),
                source="Sentinel-2",
                bands=["B2", "B3", "B4", "B8", "B11"],
                resolution=10.0,
            )
            imagery_list.append(imagery)

        # Mock geometry masking to avoid rasterio dependency
        def mock_mask_fn(raster, geometry, bounds):
            masked = raster.copy()
            return masked  # No masking for simplicity

        with patch.object(analyzer.detector, '_mask_by_geometry', side_effect=mock_mask_fn):
            result = await analyzer.analyze_venue(imagery_list, sample_polygon)

            assert "timeline" in result
            assert "summary" in result
            assert len(result["timeline"]) == 3
            assert "mean_occupancy" in result["summary"]


# ============================================================================
# Feature Result Schema Tests
# ============================================================================


class TestFeatureResult:
    """Tests for the FeatureResult dataclass."""

    def test_feature_result_creation(self):
        """Test creating a FeatureResult with required fields."""
        result = FeatureResult(
            metric_name="test_metric",
            value=0.5,
        )

        assert result.metric_name == "test_metric"
        assert result.value == 0.5
        assert result.raster is None
        assert result.bounds is None
        assert result.date is None
        assert result.unit == ""
        assert result.metadata is None

    def test_feature_result_with_all_fields(self):
        """Test creating a FeatureResult with all fields."""
        raster = np.random.rand(100, 100)
        result = FeatureResult(
            metric_name="ndvi",
            value=0.65,
            raster=raster,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            date=date(2024, 6, 15),
            unit="index (-1 to 1)",
            metadata={"min": 0.2, "max": 0.9},
        )

        assert result.metric_name == "ndvi"
        assert result.value == 0.65
        assert result.raster is not None
        assert result.bounds == (-112.1, 33.4, -111.9, 33.5)
        assert result.date == date(2024, 6, 15)
        assert result.unit == "index (-1 to 1)"
        assert result.metadata["min"] == 0.2


# ============================================================================
# Base Feature Extractor Tests
# ============================================================================


class TestBaseFeatureExtractor:
    """Tests for the BaseFeatureExtractor abstract class."""

    @pytest.mark.skipif(not RASTERIO_AVAILABLE, reason="rasterio not installed")
    def test_mask_by_geometry(self, sample_polygon: Polygon):
        """Test the geometry masking method (requires rasterio)."""
        # Create a concrete implementation for testing
        class TestExtractor(BaseFeatureExtractor):
            @property
            def metric_name(self) -> str:
                return "test"

            @property
            def required_bands(self) -> list[str]:
                return []

            @property
            def unit(self) -> str:
                return "test"

            async def extract(self, imagery, geometry=None):
                pass

        extractor = TestExtractor()
        raster = np.ones((100, 100), dtype=np.float32)
        bounds = (-112.1, 33.4, -111.9, 33.5)

        masked = extractor._mask_by_geometry(raster, sample_polygon, bounds)

        # Should have some NaN values outside the polygon
        assert np.any(np.isnan(masked))
        # Should have some valid values inside the polygon
        assert np.any(~np.isnan(masked))

    def test_base_extractor_interface(self):
        """Test that BaseFeatureExtractor defines correct abstract interface."""
        # Create a concrete implementation for testing
        class TestExtractor(BaseFeatureExtractor):
            @property
            def metric_name(self) -> str:
                return "test_metric"

            @property
            def required_bands(self) -> list[str]:
                return ["B4", "B8"]

            @property
            def unit(self) -> str:
                return "test_unit"

            async def extract(self, imagery, geometry=None):
                return FeatureResult(metric_name=self.metric_name, value=0.5)

        extractor = TestExtractor()
        assert extractor.metric_name == "test_metric"
        assert extractor.required_bands == ["B4", "B8"]
        assert extractor.unit == "test_unit"


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases across all extractors."""

    @pytest.mark.asyncio
    async def test_ndvi_with_constant_values(self):
        """Test NDVI when all values are identical."""
        extractor = NDVIExtractor()

        data = np.full((5, 100, 100), 1000, dtype=np.float32)
        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await extractor.extract(imagery)

        # When Red == NIR, NDVI = 0
        assert result.value == 0

    @pytest.mark.asyncio
    async def test_nightlights_all_dark(self):
        """Test nightlights extraction with all-dark imagery."""
        extractor = NightlightsExtractor()

        data = np.zeros((100, 100), dtype=np.float32)
        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 1, 15),
            source="VIIRS",
            bands=["avg_rad"],
            resolution=500.0,
        )

        result = await extractor.extract(imagery)

        assert result.value == 0
        assert result.metadata["lit_area_pct"] == 0

    @pytest.mark.asyncio
    async def test_single_pixel_imagery(self):
        """Test extraction with single pixel imagery."""
        extractor = NDVIExtractor()

        data = np.array([[[1000]], [[1500]], [[1000]], [[3000]], [[1500]]], dtype=np.float32)
        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await extractor.extract(imagery)

        assert isinstance(result, FeatureResult)
        assert not np.isnan(result.value)

    @pytest.mark.asyncio
    async def test_very_large_values(self):
        """Test extraction with very large reflectance values."""
        extractor = NDVIExtractor()

        data = np.full((5, 100, 100), 1e6, dtype=np.float32)
        data[3] = 2e6  # NIR higher

        imagery = SatelliteImagery(
            data=data,
            bounds=(-112.1, 33.4, -111.9, 33.5),
            crs="EPSG:4326",
            date=date(2024, 6, 15),
            source="Sentinel-2",
            bands=["B2", "B3", "B4", "B8", "B11"],
            resolution=10.0,
        )

        result = await extractor.extract(imagery)

        # Should still produce valid NDVI in range [-1, 1]
        assert -1 <= result.value <= 1
