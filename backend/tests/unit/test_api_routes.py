"""
Unit tests for API routes.

Tests cover:
- Region CRUD endpoints
- Metrics endpoint
- Exports endpoints
- Tiles endpoint

All tests use TestClient with mocked dependencies.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_db, PaginationParams
from app.core.redis import get_redis_client


# ============================================================================
# Test Setup Helpers
# ============================================================================


def create_mock_region(
    region_id: str = "550e8400-e29b-41d4-a716-446655440000",
    name: str = "Test City",
    region_type: str = "custom",
    **kwargs,
) -> MagicMock:
    """Create a mock Region model instance."""
    region = MagicMock()
    region.id = region_id
    region.name = name
    region.description = kwargs.get("description", "Test description")
    region.type = region_type
    region.country = kwargs.get("country", "United States")
    region.state_province = kwargs.get("state_province", "Arizona")
    region.category = kwargs.get("category", "major_city")
    region.created_at = kwargs.get("created_at", datetime(2024, 1, 1, tzinfo=timezone.utc))
    region.updated_at = kwargs.get("updated_at", datetime(2024, 1, 1, tzinfo=timezone.utc))
    return region


def create_mock_observation(
    region_id: str,
    observation_date: date,
    metric: str,
    value: float,
) -> MagicMock:
    """Create a mock Observation model instance."""
    obs = MagicMock()
    obs.id = f"obs-{metric}-{observation_date}"
    obs.region_id = region_id
    obs.date = observation_date
    obs.metric = metric
    obs.value = value
    obs.raster_path = None
    obs.extra_data = {}
    return obs


# ============================================================================
# Regions API Tests
# ============================================================================


class TestRegionsAPI:
    """Tests for the regions API endpoints."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def client(self, mock_db: AsyncMock) -> TestClient:
        """Create a test client with mocked database."""
        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_list_regions_empty(self, client: TestClient, mock_db: AsyncMock):
        """Test listing regions when database is empty."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=0)

        response = client.get("/api/v1/regions")

        assert response.status_code == 200
        data = response.json()
        assert data["regions"] == []
        assert data["total"] == 0

    def test_list_regions_with_data(self, client: TestClient, mock_db: AsyncMock):
        """Test listing regions with data."""
        mock_region = create_mock_region()
        mock_geojson = '{"type": "Polygon", "coordinates": [[[-112.1, 33.4], [-112.1, 33.5], [-111.9, 33.5], [-111.9, 33.4], [-112.1, 33.4]]]}'

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[(mock_region, mock_geojson)])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        response = client.get("/api/v1/regions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["regions"]) == 1
        assert data["regions"][0]["name"] == "Test City"
        assert data["total"] == 1

    def test_list_regions_with_filters(self, client: TestClient, mock_db: AsyncMock):
        """Test listing regions with filters."""
        mock_region = create_mock_region()
        mock_geojson = '{"type": "Polygon", "coordinates": [[[-112.1, 33.4], [-112.1, 33.5], [-111.9, 33.5], [-111.9, 33.4], [-112.1, 33.4]]]}'

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[(mock_region, mock_geojson)])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        response = client.get(
            "/api/v1/regions",
            params={
                "type": "custom",
                "country": "United States",
                "category": "major_city",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["regions"]) == 1

    def test_list_regions_search(self, client: TestClient, mock_db: AsyncMock):
        """Test searching regions by name."""
        mock_region = create_mock_region(name="Phoenix Metro")
        mock_geojson = '{"type": "Polygon", "coordinates": [[[-112.1, 33.4], [-112.1, 33.5], [-111.9, 33.5], [-111.9, 33.4], [-112.1, 33.4]]]}'

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[(mock_region, mock_geojson)])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=1)

        response = client.get("/api/v1/regions", params={"search": "Phoenix"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["regions"]) == 1
        assert "Phoenix" in data["regions"][0]["name"]

    def test_get_region_success(self, client: TestClient, mock_db: AsyncMock):
        """Test getting a specific region by ID."""
        mock_region = create_mock_region()
        mock_geojson = '{"type": "Polygon", "coordinates": [[[-112.1, 33.4], [-112.1, 33.5], [-111.9, 33.5], [-111.9, 33.4], [-112.1, 33.4]]]}'

        mock_result = MagicMock()
        mock_result.one_or_none = MagicMock(return_value=(mock_region, mock_geojson))
        mock_db.execute = AsyncMock(return_value=mock_result)

        region_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/regions/{region_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == region_id
        assert data["name"] == "Test City"
        assert data["geometry"]["type"] == "Polygon"

    def test_get_region_not_found(self, client: TestClient, mock_db: AsyncMock):
        """Test getting a non-existent region."""
        mock_result = MagicMock()
        mock_result.one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v1/regions/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_region_success(self, client: TestClient, mock_db: AsyncMock):
        """Test creating a new region."""
        mock_region = create_mock_region()
        mock_geojson = '{"type": "Polygon", "coordinates": [[[-112.1, 33.4], [-112.1, 33.5], [-111.9, 33.5], [-111.9, 33.4], [-112.1, 33.4]]]}'

        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=(mock_region, mock_geojson))
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        region_data = {
            "name": "New Region",
            "description": "A new test region",
            "geometry": {
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
            },
            "country": "United States",
            "state_province": "Arizona",
            "category": "major_city",
        }

        response = client.post("/api/v1/regions", json=region_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test City"  # From mock

    def test_create_region_invalid_geometry(self, client: TestClient, mock_db: AsyncMock):
        """Test creating a region with invalid geometry."""
        region_data = {
            "name": "Invalid Region",
            "geometry": {
                "type": "Point",  # Invalid - should be Polygon
                "coordinates": [-112.1, 33.4],
            },
        }

        response = client.post("/api/v1/regions", json=region_data)

        assert response.status_code == 422  # Validation error

    def test_create_region_unclosed_polygon(self, client: TestClient, mock_db: AsyncMock):
        """Test creating a region with unclosed polygon ring."""
        region_data = {
            "name": "Unclosed Polygon",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.1, 33.4],
                        [-112.1, 33.5],
                        [-111.9, 33.5],
                        [-111.9, 33.4],
                        # Missing closing point
                    ]
                ],
            },
        }

        response = client.post("/api/v1/regions", json=region_data)

        assert response.status_code == 422

    def test_delete_region_success(self, client: TestClient, mock_db: AsyncMock):
        """Test deleting a custom region."""
        mock_region = create_mock_region(region_type="custom")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock()

        region_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.delete(f"/api/v1/regions/{region_id}")

        assert response.status_code == 204

    def test_delete_predefined_region_forbidden(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ):
        """Test that deleting predefined regions is forbidden."""
        mock_region = create_mock_region(region_type="predefined")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        region_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.delete(f"/api/v1/regions/{region_id}")

        assert response.status_code == 403
        assert "predefined" in response.json()["detail"].lower()

    def test_delete_region_not_found(self, client: TestClient, mock_db: AsyncMock):
        """Test deleting a non-existent region."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.delete("/api/v1/regions/nonexistent-id")

        assert response.status_code == 404


# ============================================================================
# Metrics API Tests
# ============================================================================


class TestMetricsAPI:
    """Tests for the metrics API endpoints."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def client(self, mock_db: AsyncMock) -> TestClient:
        """Create a test client with mocked database."""
        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_get_region_metrics_success(self, client: TestClient, mock_db: AsyncMock):
        """Test getting metrics for a region."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        # Mock observations
        mock_observations = [
            create_mock_observation(region_id, date(2024, 1, 15), "ndvi", 0.45),
            create_mock_observation(region_id, date(2024, 2, 15), "ndvi", 0.50),
            create_mock_observation(region_id, date(2024, 1, 15), "nightlights", 12.5),
        ]

        # First call returns region
        region_result = MagicMock()
        region_result.scalar_one_or_none = MagicMock(return_value=mock_region)

        # Second call returns observations
        obs_result = MagicMock()
        obs_scalars = MagicMock()
        obs_scalars.all = MagicMock(return_value=mock_observations)
        obs_result.scalars = MagicMock(return_value=obs_scalars)

        # Winter/Summer averages
        winter_result = MagicMock()
        winter_result.all = MagicMock(return_value=[("ndvi", 0.35), ("nightlights", 15.0)])

        summer_result = MagicMock()
        summer_result.all = MagicMock(return_value=[("ndvi", 0.55), ("nightlights", 10.0)])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return region_result
            elif call_count[0] == 2:
                return obs_result
            elif call_count[0] == 3:
                return winter_result
            else:
                return summer_result

        mock_db.execute = mock_execute

        response = client.get(f"/api/v1/metrics/{region_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["region_id"] == region_id
        assert data["region_name"] == "Test City"
        assert "metrics" in data
        assert "ndvi" in data["metrics"]
        assert "nightlights" in data["metrics"]

    def test_get_region_metrics_not_found(self, client: TestClient, mock_db: AsyncMock):
        """Test getting metrics for non-existent region."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v1/metrics/nonexistent-id")

        assert response.status_code == 404

    def test_get_region_metrics_with_date_filter(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ):
        """Test getting metrics with date filters."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        # Setup mock returns
        region_result = MagicMock()
        region_result.scalar_one_or_none = MagicMock(return_value=mock_region)

        obs_result = MagicMock()
        obs_scalars = MagicMock()
        obs_scalars.all = MagicMock(return_value=[])
        obs_result.scalars = MagicMock(return_value=obs_scalars)

        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return region_result
            elif call_count[0] == 2:
                return obs_result
            return empty_result

        mock_db.execute = mock_execute

        response = client.get(
            f"/api/v1/metrics/{region_id}",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
                "granularity": "monthly",
            },
        )

        assert response.status_code == 200

    def test_get_region_metrics_with_metric_filter(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ):
        """Test getting specific metrics only."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        region_result = MagicMock()
        region_result.scalar_one_or_none = MagicMock(return_value=mock_region)

        obs_result = MagicMock()
        obs_scalars = MagicMock()
        obs_scalars.all = MagicMock(return_value=[])
        obs_result.scalars = MagicMock(return_value=obs_scalars)

        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return region_result
            elif call_count[0] == 2:
                return obs_result
            return empty_result

        mock_db.execute = mock_execute

        response = client.get(
            f"/api/v1/metrics/{region_id}",
            params={"metrics": ["ndvi", "nightlights"]},
        )

        assert response.status_code == 200

    def test_get_region_metrics_weekly_aggregates_and_formats_dates(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ):
        """Weekly granularity should bucket by week and return ISO dates (YYYY-MM-DD)."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        # Multiple observations within the same week should be averaged.
        mock_observations = [
            create_mock_observation(region_id, date(2024, 1, 2), "ndvi", 0.4),
            create_mock_observation(region_id, date(2024, 1, 5), "ndvi", 0.6),
            create_mock_observation(region_id, date(2024, 1, 10), "ndvi", 0.5),
        ]

        region_result = MagicMock()
        region_result.scalar_one_or_none = MagicMock(return_value=mock_region)

        obs_result = MagicMock()
        obs_scalars = MagicMock()
        obs_scalars.all = MagicMock(return_value=mock_observations)
        obs_result.scalars = MagicMock(return_value=obs_scalars)

        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return region_result
            if call_count[0] == 2:
                return obs_result
            return empty_result

        mock_db.execute = mock_execute

        response = client.get(
            f"/api/v1/metrics/{region_id}",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "granularity": "weekly",
                "metrics": ["ndvi"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        ndvi_points = payload["metrics"]["ndvi"]["data"]

        assert [p["date"] for p in ndvi_points] == ["2024-01-01", "2024-01-08"]
        assert ndvi_points[0]["value"] == pytest.approx(0.5)
        assert ndvi_points[1]["value"] == pytest.approx(0.5)


# ============================================================================
# Exports API Tests
# ============================================================================


class TestExportsAPI:
    """Tests for the exports API endpoints."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        storage = {}

        async def mock_set_status(key_id, data, prefix="export_status", ttl=86400):
            storage[f"{prefix}:{key_id}"] = data

        async def mock_get_status(key_id, prefix="export_status"):
            return storage.get(f"{prefix}:{key_id}")

        async def mock_update_status(key_id, updates, prefix="export_status", ttl=86400):
            key = f"{prefix}:{key_id}"
            if key in storage:
                storage[key].update(updates)
                return storage[key]
            return None

        redis.set_status = mock_set_status
        redis.get_status = mock_get_status
        redis.update_status = mock_update_status
        redis._storage = storage

        return redis

    @pytest.fixture
    def client(self, mock_db: AsyncMock, mock_redis: AsyncMock) -> TestClient:
        """Create a test client with mocked dependencies."""
        async def override_get_db():
            yield mock_db

        def override_get_redis():
            return mock_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis_client] = override_get_redis

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_export_pdf_success(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ):
        """Test initiating a PDF export."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        export_request = {
            "region_id": region_id,
            "format": "pdf",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "include_charts": True,
            "include_maps": True,
        }

        response = client.post("/api/v1/exports/pdf", json=export_request)

        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["format"] == "pdf"

    def test_export_pdf_region_not_found(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ):
        """Test PDF export with non-existent region."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        export_request = {
            "region_id": "nonexistent-id",
            "format": "pdf",
        }

        response = client.post("/api/v1/exports/pdf", json=export_request)

        assert response.status_code == 404

    def test_export_csv_success(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ):
        """Test initiating a CSV export."""
        export_request = {
            "region_ids": ["region-1", "region-2"],
            "metrics": ["ndvi", "nightlights"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "include_metadata": True,
        }

        response = client.post("/api/v1/exports/csv", json=export_request)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["format"] == "csv"

    def test_export_animation_success(
        self,
        client: TestClient,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ):
        """Test initiating an animation export."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        animation_request = {
            "region_id": region_id,
            "metric": "ndvi",
            "format": "gif",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "frame_duration_ms": 500,
            "width": 800,
            "height": 600,
        }

        response = client.post("/api/v1/exports/animation", json=animation_request)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["format"] == "gif"

    def test_get_export_status_success(
        self,
        client: TestClient,
        mock_redis: AsyncMock,
    ):
        """Test getting export status."""
        export_id = "test-export-id"

        # Mock the redis client's get_status method directly
        with patch("app.api.routes.exports.get_redis_client") as mock_get_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.get_status = AsyncMock(return_value={
                "id": export_id,
                "status": "completed",
                "format": "pdf",
                "download_url": f"/api/v1/exports/download/{export_id}",
                "file_size": 12345,
                "created_at": "2024-01-01T00:00:00Z",
                "completed_at": "2024-01-01T00:05:00Z",
            })
            mock_get_redis.return_value = mock_redis_instance

            response = client.get(f"/api/v1/exports/{export_id}/status")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == export_id
            assert data["status"] == "completed"

    def test_get_export_status_not_found(
        self,
        client: TestClient,
        mock_redis: AsyncMock,
    ):
        """Test getting status for non-existent export."""
        with patch("app.api.routes.exports.get_redis_client") as mock_get_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.get_status = AsyncMock(return_value=None)
            mock_get_redis.return_value = mock_redis_instance

            response = client.get("/api/v1/exports/nonexistent-id/status")

            assert response.status_code == 404

    def test_download_export_not_complete(
        self,
        client: TestClient,
        mock_redis: AsyncMock,
    ):
        """Test downloading an incomplete export."""
        export_id = "pending-export"

        with patch("app.api.routes.exports.get_redis_client") as mock_get_redis:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.get_status = AsyncMock(return_value={
                "id": export_id,
                "status": "processing",
                "format": "pdf",
                "download_url": None,
                "created_at": "2024-01-01T00:00:00Z",
            })
            mock_get_redis.return_value = mock_redis_instance

            response = client.get(f"/api/v1/exports/download/{export_id}")

            assert response.status_code == 400
            assert "not yet complete" in response.json()["detail"].lower()


# ============================================================================
# Tiles API Tests
# ============================================================================


class TestTilesAPI:
    """Tests for the tiles API endpoints."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def client(self, mock_db: AsyncMock) -> TestClient:
        """Create a test client with mocked database."""
        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_get_tile_region_not_found(self, client: TestClient, mock_db: AsyncMock):
        """Test getting a tile for non-existent region."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v1/tiles/nonexistent-id/ndvi/10/512/512.png")

        assert response.status_code == 404

    def test_get_tile_invalid_metric(self, client: TestClient, mock_db: AsyncMock):
        """Test getting a tile with invalid metric."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/v1/tiles/{region_id}/invalid_metric/10/512/512.png")

        assert response.status_code == 400
        assert "Invalid metric" in response.json()["detail"]

    def test_get_tile_valid_metrics(self, client: TestClient, mock_db: AsyncMock):
        """Test that valid metrics are accepted."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_region = create_mock_region(region_id=region_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        valid_metrics = ["ndvi", "nightlights", "urban_density", "parking"]

        for metric in valid_metrics:
            # The tile generation will fail, but we should get past validation
            with patch("app.services.tiles.generator.TileGenerator") as mock_generator:
                mock_gen_instance = MagicMock()
                mock_gen_instance.generate_tile = AsyncMock(side_effect=FileNotFoundError())
                mock_generator.return_value = mock_gen_instance

                # Also mock create_empty_tile
                with patch("app.services.tiles.generator.create_empty_tile", return_value=b"PNG"):
                    response = client.get(f"/api/v1/tiles/{region_id}/{metric}/10/512/512.png")

                    # Should return 200 with empty tile on FileNotFoundError
                    assert response.status_code == 200

    def test_get_region_bounds_success(self, client: TestClient, mock_db: AsyncMock):
        """Test getting region bounds."""
        region_id = "550e8400-e29b-41d4-a716-446655440000"

        bounds_geojson = json.dumps({
            "type": "Polygon",
            "coordinates": [
                [
                    [-112.1, 33.4],
                    [-111.9, 33.4],
                    [-111.9, 33.5],
                    [-112.1, 33.5],
                    [-112.1, 33.4],
                ]
            ],
        })

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=bounds_geojson)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/v1/tiles/{region_id}/bounds")

        assert response.status_code == 200
        data = response.json()
        assert data["region_id"] == region_id
        assert "bounds" in data
        assert "center" in data
        assert data["bounds"]["west"] == -112.1
        assert data["bounds"]["east"] == -111.9
        assert data["bounds"]["south"] == 33.4
        assert data["bounds"]["north"] == 33.5

    def test_get_region_bounds_not_found(self, client: TestClient, mock_db: AsyncMock):
        """Test getting bounds for non-existent region."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/v1/tiles/nonexistent-id/bounds")

        assert response.status_code == 404


# ============================================================================
# Health Check and Root Endpoint Tests
# ============================================================================


class TestHealthAndRoot:
    """Tests for health check and root endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        with TestClient(app) as client:
            yield client

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        # Status can be "healthy" or "degraded" depending on database availability
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data


# ============================================================================
# Pagination Tests
# ============================================================================


class TestPagination:
    """Tests for pagination functionality."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def client(self, mock_db: AsyncMock) -> TestClient:
        """Create a test client with mocked database."""
        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_pagination_default_values(self, client: TestClient, mock_db: AsyncMock):
        """Test default pagination values."""
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=0)

        response = client.get("/api/v1/regions")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_pagination_custom_values(self, client: TestClient, mock_db: AsyncMock):
        """Test custom pagination values."""
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.scalar = AsyncMock(return_value=0)

        response = client.get("/api/v1/regions", params={"page": 2, "page_size": 25})

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 25

    def test_pagination_max_page_size(self, client: TestClient, mock_db: AsyncMock):
        """Test pagination respects max page size."""
        # Request page_size > 100 should be rejected by validation
        response = client.get("/api/v1/regions", params={"page_size": 500})

        assert response.status_code == 422  # Validation error


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def client(self, mock_db: AsyncMock) -> TestClient:
        """Create a test client with mocked database."""
        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_invalid_json_body(self, client: TestClient):
        """Test handling of invalid JSON in request body."""
        response = client.post(
            "/api/v1/regions",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_required_field(self, client: TestClient):
        """Test handling of missing required fields."""
        # Missing 'name' field
        response = client.post(
            "/api/v1/regions",
            json={
                "geometry": {
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
                },
            },
        )

        assert response.status_code == 422
        assert "name" in response.text.lower()

    def test_invalid_date_format(self, client: TestClient, mock_db: AsyncMock):
        """Test handling of invalid date format."""
        mock_region = create_mock_region()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_region)
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(
            "/api/v1/metrics/test-region",
            params={"start_date": "not-a-date"},
        )

        assert response.status_code == 422
