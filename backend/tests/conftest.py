"""
Shared fixtures for satellite-data backend tests.

Provides mock database sessions, GEE client, Redis client,
and sample data for testing without external dependencies.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from shapely.geometry import Polygon

from app.services.satellite.base import SatelliteImagery


# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_region_id() -> str:
    """Sample region UUID."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def sample_region_data() -> dict[str, Any]:
    """Sample region data for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Test City",
        "description": "A test region for unit testing",
        "type": "custom",
        "country": "United States",
        "state_province": "Arizona",
        "category": "major_city",
        "created_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_geometry() -> dict[str, Any]:
    """Sample GeoJSON polygon geometry."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-112.1, 33.4],
                [-112.1, 33.5],
                [-111.9, 33.5],
                [-111.9, 33.4],
                [-112.1, 33.4],
            ]
        ],
    }


@pytest.fixture
def sample_polygon() -> Polygon:
    """Sample Shapely polygon for geometry operations."""
    return Polygon([
        (-112.1, 33.4),
        (-112.1, 33.5),
        (-111.9, 33.5),
        (-111.9, 33.4),
        (-112.1, 33.4),
    ])


@pytest.fixture
def sample_observation_data(sample_region_id: str) -> list[dict[str, Any]]:
    """Sample observation data for testing."""
    base_date = date(2024, 1, 1)
    observations = []

    # Generate 12 months of data for each metric
    metrics = ["ndvi", "nightlights", "urban_density", "parking"]

    for i in range(12):
        month_date = date(2024, i + 1, 15)
        for metric in metrics:
            if metric == "ndvi":
                # NDVI varies seasonally
                value = 0.3 + 0.2 * np.sin(i * np.pi / 6)
            elif metric == "nightlights":
                # Nightlights higher in winter (snowbird effect)
                value = 10.0 + 5.0 * np.cos(i * np.pi / 6)
            elif metric == "urban_density":
                # Urban density relatively stable
                value = 0.45 + 0.02 * np.random.randn()
            else:  # parking
                value = 0.6 + 0.1 * np.random.randn()

            observations.append({
                "id": f"obs-{i}-{metric}",
                "region_id": sample_region_id,
                "date": month_date,
                "metric": metric,
                "value": float(value),
                "raster_path": None,
                "extra_data": {"source": "test"},
            })

    return observations


# ============================================================================
# Mock Satellite Imagery
# ============================================================================


@pytest.fixture
def mock_sentinel2_imagery() -> SatelliteImagery:
    """
    Create mock Sentinel-2 imagery with realistic band structure.

    Bands: B2 (Blue), B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR)
    Shape: (5, 100, 100) - 5 bands, 100x100 pixels
    """
    # Create realistic test data
    np.random.seed(42)

    # Base reflectance values (scaled 0-10000 like real Sentinel-2)
    blue = np.random.randint(500, 2000, (100, 100)).astype(np.float32)
    green = np.random.randint(600, 2500, (100, 100)).astype(np.float32)
    red = np.random.randint(400, 2000, (100, 100)).astype(np.float32)
    nir = np.random.randint(2000, 5000, (100, 100)).astype(np.float32)  # Higher for vegetation
    swir = np.random.randint(1000, 3000, (100, 100)).astype(np.float32)

    data = np.stack([blue, green, red, nir, swir])

    return SatelliteImagery(
        data=data,
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2024, 6, 15),
        source="Sentinel-2",
        bands=["B2", "B3", "B4", "B8", "B11"],
        resolution=10.0,
        cloud_cover=5.0,
        metadata={"scene_id": "test_scene_001"},
    )


@pytest.fixture
def mock_viirs_imagery() -> SatelliteImagery:
    """
    Create mock VIIRS nighttime lights imagery.

    Single band: avg_rad (average radiance)
    Shape: (100, 100) pixels
    Values in nW/cm2/sr (typical range 0-200)
    """
    np.random.seed(42)

    # Create nightlights data with urban pattern
    radiance = np.zeros((100, 100), dtype=np.float32)

    # Urban center (bright)
    radiance[40:60, 40:60] = np.random.uniform(20, 50, (20, 20))

    # Suburban areas (moderate)
    radiance[30:70, 30:70] += np.random.uniform(5, 15, (40, 40))

    # Background (dim)
    radiance += np.random.uniform(0, 2, (100, 100))

    return SatelliteImagery(
        data=radiance,
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2024, 1, 15),
        source="VIIRS",
        bands=["avg_rad"],
        resolution=500.0,
        cloud_cover=None,
        metadata={"composite": "monthly"},
    )


@pytest.fixture
def mock_ghsl_imagery() -> SatelliteImagery:
    """
    Create mock GHSL (Global Human Settlement Layer) built-up surface data.

    Values represent built-up surface area in m2 per pixel.
    GHSL pixels are 100m x 100m = 10,000 m2 max.
    """
    np.random.seed(42)

    # Create built-up surface data
    built_surface = np.zeros((50, 50), dtype=np.float32)

    # Urban core (high built-up)
    built_surface[20:30, 20:30] = np.random.uniform(7000, 9500, (10, 10))

    # Suburban (moderate built-up)
    built_surface[15:35, 15:35] += np.random.uniform(2000, 5000, (20, 20))

    # Rural fringe
    built_surface[10:40, 10:40] = np.where(
        built_surface[10:40, 10:40] == 0,
        np.random.uniform(0, 1000, (30, 30)),
        built_surface[10:40, 10:40],
    )

    return SatelliteImagery(
        data=built_surface.reshape(1, 50, 50),
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2020, 1, 1),
        source="GHSL",
        bands=["built_surface"],
        resolution=100.0,
        cloud_cover=None,
        metadata={"epoch": 2020, "dataset": "JRC/GHSL/P2023A/GHS_BUILT_S"},
    )


# ============================================================================
# Mock Database Session
# ============================================================================


@pytest.fixture
def mock_observation_model():
    """Create a mock Observation model class."""
    class MockObservation:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    return MockObservation


@pytest_asyncio.fixture
async def mock_db_session(
    sample_region_id: str,
    sample_region_data: dict,
    sample_observation_data: list,
) -> AsyncMock:
    """
    Create a mock async database session.

    Returns an AsyncMock that simulates SQLAlchemy AsyncSession behavior
    for common operations like execute, scalar, scalars, etc.
    """
    session = AsyncMock()

    # Mock Region model
    mock_region = MagicMock()
    mock_region.id = sample_region_data["id"]
    mock_region.name = sample_region_data["name"]
    mock_region.description = sample_region_data["description"]
    mock_region.type = sample_region_data["type"]
    mock_region.country = sample_region_data["country"]
    mock_region.state_province = sample_region_data["state_province"]
    mock_region.category = sample_region_data["category"]
    mock_region.created_at = sample_region_data["created_at"]
    mock_region.updated_at = sample_region_data["updated_at"]

    # Mock Observation models
    mock_observations = []
    for obs_data in sample_observation_data:
        mock_obs = MagicMock()
        for key, value in obs_data.items():
            setattr(mock_obs, key, value)
        mock_observations.append(mock_obs)

    # Setup execute to return different results based on query
    async def mock_execute(query):
        result = MagicMock()

        # Return region for region queries
        result.scalar_one_or_none = MagicMock(return_value=mock_region)
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_observations)))
        result.all = MagicMock(return_value=[
            (obs.date, obs.value) for obs in mock_observations[:5]
        ])
        result.one_or_none = MagicMock(return_value=(mock_region, '{"type": "Polygon"}'))

        return result

    session.execute = mock_execute
    session.scalar = AsyncMock(return_value=100)  # For count queries
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session


# ============================================================================
# Mock GEE Client
# ============================================================================


@pytest_asyncio.fixture
async def mock_gee_client(mock_ghsl_imagery: SatelliteImagery) -> AsyncMock:
    """
    Create a mock Google Earth Engine client.

    Simulates GHSLClient behavior for GHSL data retrieval.
    """
    client = AsyncMock()

    # Mock initialization
    client.initialize = AsyncMock()
    client._initialized = True

    # Mock GHSL built surface retrieval
    client.get_ghsl_built_surface = AsyncMock(return_value=mock_ghsl_imagery)

    # Mock GHSL settlement model
    mock_smod_data = np.full((50, 50), 22, dtype=np.float32)  # Semi-dense urban
    mock_smod_imagery = SatelliteImagery(
        data=mock_smod_data.reshape(1, 50, 50),
        bounds=mock_ghsl_imagery.bounds,
        crs="EPSG:4326",
        date=date(2020, 1, 1),
        source="GHSL_SMOD",
        bands=["smod"],
        resolution=1000.0,
        metadata={"epoch": 2020},
    )
    client.get_ghsl_settlement_model = AsyncMock(return_value=mock_smod_imagery)

    # Available epochs
    client.AVAILABLE_EPOCHS = [1975, 1990, 2000, 2005, 2010, 2015, 2020]

    return client


# ============================================================================
# Mock Redis Client
# ============================================================================


@pytest_asyncio.fixture
async def mock_redis_client() -> AsyncMock:
    """
    Create a mock Redis client for status tracking.

    Simulates the RedisClient class behavior.
    """
    client = AsyncMock()

    # In-memory storage for testing
    storage: dict[str, dict] = {}

    async def mock_get_status(key_id: str, prefix: str = "export_status") -> dict | None:
        key = f"{prefix}:{key_id}"
        return storage.get(key)

    async def mock_set_status(
        key_id: str,
        data: dict,
        prefix: str = "export_status",
        ttl: int = 86400,
    ) -> None:
        key = f"{prefix}:{key_id}"
        storage[key] = data

    async def mock_delete_status(key_id: str, prefix: str = "export_status") -> bool:
        key = f"{prefix}:{key_id}"
        if key in storage:
            del storage[key]
            return True
        return False

    async def mock_update_status(
        key_id: str,
        updates: dict,
        prefix: str = "export_status",
        ttl: int = 86400,
    ) -> dict | None:
        key = f"{prefix}:{key_id}"
        if key not in storage:
            return None
        storage[key].update(updates)
        return storage[key]

    async def mock_exists(key_id: str, prefix: str = "export_status") -> bool:
        key = f"{prefix}:{key_id}"
        return key in storage

    client.get_status = mock_get_status
    client.set_status = mock_set_status
    client.delete_status = mock_delete_status
    client.update_status = mock_update_status
    client.exists = mock_exists
    client.connect = AsyncMock()
    client.close = AsyncMock()

    # Expose storage for test inspection
    client._storage = storage

    return client


# ============================================================================
# Edge Case Data Fixtures
# ============================================================================


@pytest.fixture
def empty_imagery() -> SatelliteImagery:
    """Create imagery with empty (all NaN) data."""
    data = np.full((5, 100, 100), np.nan, dtype=np.float32)

    return SatelliteImagery(
        data=data,
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2024, 1, 15),
        source="Sentinel-2",
        bands=["B2", "B3", "B4", "B8", "B11"],
        resolution=10.0,
        cloud_cover=100.0,
        metadata={"note": "All NaN test data"},
    )


@pytest.fixture
def zero_denominator_imagery() -> SatelliteImagery:
    """Create imagery where NDVI denominator would be zero."""
    # Both NIR (B8) and Red (B4) are zero
    data = np.zeros((5, 100, 100), dtype=np.float32)

    return SatelliteImagery(
        data=data,
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2024, 1, 15),
        source="Sentinel-2",
        bands=["B2", "B3", "B4", "B8", "B11"],
        resolution=10.0,
        cloud_cover=0.0,
        metadata={"note": "Zero denominator test"},
    )


@pytest.fixture
def negative_radiance_imagery() -> SatelliteImagery:
    """Create VIIRS imagery with negative values (noise)."""
    np.random.seed(42)

    # Radiance with some negative values
    radiance = np.random.uniform(-5, 50, (100, 100)).astype(np.float32)

    return SatelliteImagery(
        data=radiance,
        bounds=(-112.1, 33.4, -111.9, 33.5),
        crs="EPSG:4326",
        date=date(2024, 1, 15),
        source="VIIRS",
        bands=["avg_rad"],
        resolution=500.0,
        metadata={"note": "Negative radiance test"},
    )


# ============================================================================
# Test Client Fixture for API Tests
# ============================================================================


@pytest.fixture
def mock_test_client():
    """
    Fixture factory for creating a TestClient with mocked dependencies.

    Usage:
        def test_endpoint(mock_test_client, mock_db_session, mock_redis_client):
            client = mock_test_client(db=mock_db_session, redis=mock_redis_client)
            response = client.get("/api/v1/regions")
    """
    def _create_client(db: AsyncMock = None, redis: AsyncMock = None):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.dependencies import get_db
        from app.core.redis import get_redis_client

        if db:
            async def override_get_db():
                yield db
            app.dependency_overrides[get_db] = override_get_db

        if redis:
            def override_get_redis():
                return redis
            app.dependency_overrides[get_redis_client] = override_get_redis

        client = TestClient(app)

        return client

    return _create_client


# ============================================================================
# Cleanup
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_dependency_overrides():
    """Clean up FastAPI dependency overrides after each test."""
    yield

    # Import here to avoid circular imports during collection
    try:
        from app.main import app
        app.dependency_overrides.clear()
    except ImportError:
        pass
