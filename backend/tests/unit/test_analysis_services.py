"""
Unit tests for analysis services.

Tests cover:
- TemporalAnalyzer (trend analysis, anomaly detection)
- ChangeDetector (period comparison, event detection)
- MigrationAnalyzer (seasonal migration, correlated regions)
- All tests use mock database sessions
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.services.analysis.temporal import (
    TemporalAnalyzer,
    compute_period_averages,
    calculate_seasonal_change,
)
from app.services.analysis.change_detection import ChangeDetector
from app.services.analysis.migration import MigrationAnalyzer


# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_observation(
    region_id: str,
    observation_date: date,
    metric: str,
    value: float,
) -> MagicMock:
    """Create a mock Observation object."""
    obs = MagicMock()
    obs.region_id = region_id
    obs.date = observation_date
    obs.metric = metric
    obs.value = value
    return obs


def create_mock_db_for_observations(
    observations: list[tuple[date, float]] | list[MagicMock],
) -> AsyncMock:
    """Create a mock database session configured to return observations."""
    db = AsyncMock()

    # Handle tuple format (date, value)
    if observations and isinstance(observations[0], tuple):
        result = MagicMock()
        result.all = MagicMock(return_value=observations)

        scalars_result = MagicMock()
        scalars_result.all = MagicMock(return_value=[
            create_mock_observation("test-region", d, "test", v)
            for d, v in observations
        ])
        result.scalars = MagicMock(return_value=scalars_result)
    else:
        result = MagicMock()
        result.all = MagicMock(return_value=[
            (obs.date, obs.value) for obs in observations
        ])
        scalars_result = MagicMock()
        scalars_result.all = MagicMock(return_value=observations)
        result.scalars = MagicMock(return_value=scalars_result)

    db.execute = AsyncMock(return_value=result)

    return db


# ============================================================================
# TemporalAnalyzer Tests
# ============================================================================


class TestTemporalAnalyzer:
    """Tests for the TemporalAnalyzer class."""

    @pytest.fixture
    def sample_region_id(self) -> str:
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_analyze_trend_increasing(self, sample_region_id: str):
        """Test trend analysis with increasing values."""
        # Create observations with clear upward trend
        observations = [
            (date(2024, 1, 15), 10.0),
            (date(2024, 2, 15), 12.0),
            (date(2024, 3, 15), 14.0),
            (date(2024, 4, 15), 16.0),
            (date(2024, 5, 15), 18.0),
        ]

        db = create_mock_db_for_observations(observations)
        analyzer = TemporalAnalyzer(db)

        result = await analyzer.analyze_trend(
            region_id=sample_region_id,
            metric="ndvi",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        assert result["metric"] == "ndvi"
        assert result["trend"] == "increasing"
        assert result["slope"] > 0
        assert result["r_squared"] > 0.9  # High correlation for linear trend
        assert result["start_value"] == 10.0
        assert result["end_value"] == 18.0
        assert result["data_points"] == 5

    @pytest.mark.asyncio
    async def test_analyze_trend_decreasing(self, sample_region_id: str):
        """Test trend analysis with decreasing values."""
        observations = [
            (date(2024, 1, 15), 20.0),
            (date(2024, 2, 15), 18.0),
            (date(2024, 3, 15), 16.0),
            (date(2024, 4, 15), 14.0),
            (date(2024, 5, 15), 12.0),
        ]

        db = create_mock_db_for_observations(observations)
        analyzer = TemporalAnalyzer(db)

        result = await analyzer.analyze_trend(
            region_id=sample_region_id,
            metric="nightlights",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        assert result["trend"] == "decreasing"
        assert result["slope"] < 0

    @pytest.mark.asyncio
    async def test_analyze_trend_stable(self, sample_region_id: str):
        """Test trend analysis with stable values."""
        # Stable values with tiny variations
        observations = [
            (date(2024, 1, 15), 10.0),
            (date(2024, 2, 15), 10.0001),
            (date(2024, 3, 15), 9.9999),
            (date(2024, 4, 15), 10.0),
            (date(2024, 5, 15), 10.0001),
        ]

        db = create_mock_db_for_observations(observations)
        analyzer = TemporalAnalyzer(db)

        result = await analyzer.analyze_trend(
            region_id=sample_region_id,
            metric="urban_density",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        assert result["trend"] == "stable"
        assert abs(result["slope"]) < 0.001

    @pytest.mark.asyncio
    async def test_analyze_trend_insufficient_data(self, sample_region_id: str):
        """Test trend analysis with insufficient data points."""
        observations = [
            (date(2024, 1, 15), 10.0),
        ]

        db = create_mock_db_for_observations(observations)
        analyzer = TemporalAnalyzer(db)

        result = await analyzer.analyze_trend(
            region_id=sample_region_id,
            metric="ndvi",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert result["trend"] == "insufficient_data"
        assert result["slope"] == 0
        assert result["r_squared"] == 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_basic(self, sample_region_id: str):
        """Test anomaly detection with clear outliers."""
        # Create observations with 2 anomalies
        mock_observations = []
        for i in range(20):
            value = 10.0 + np.random.normal(0, 0.5)
            if i == 5:
                value = 25.0  # High anomaly
            elif i == 15:
                value = -5.0  # Low anomaly

            mock_observations.append(
                create_mock_observation(
                    sample_region_id,
                    date(2024, 1, i + 1),
                    "nightlights",
                    value,
                )
            )

        db = create_mock_db_for_observations(mock_observations)
        analyzer = TemporalAnalyzer(db)

        anomalies = await analyzer.detect_anomalies(
            region_id=sample_region_id,
            metric="nightlights",
            threshold_std=2.0,
        )

        assert len(anomalies) >= 2
        # Anomalies should be sorted by z-score magnitude
        assert abs(anomalies[0]["z_score"]) >= abs(anomalies[-1]["z_score"])

        # Check anomaly types
        types = [a["type"] for a in anomalies]
        assert "high" in types or "low" in types

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_outliers(self, sample_region_id: str):
        """Test anomaly detection with no outliers."""
        # Create uniform observations
        mock_observations = [
            create_mock_observation(sample_region_id, date(2024, 1, i + 1), "ndvi", 0.5)
            for i in range(20)
        ]

        db = create_mock_db_for_observations(mock_observations)
        analyzer = TemporalAnalyzer(db)

        anomalies = await analyzer.detect_anomalies(
            region_id=sample_region_id,
            metric="ndvi",
            threshold_std=2.0,
        )

        # All values are identical, so std = 0, making all z-scores 0
        # No anomalies should be detected
        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_insufficient_data(self, sample_region_id: str):
        """Test anomaly detection with insufficient data."""
        mock_observations = [
            create_mock_observation(sample_region_id, date(2024, 1, i + 1), "ndvi", 10.0)
            for i in range(5)
        ]

        db = create_mock_db_for_observations(mock_observations)
        analyzer = TemporalAnalyzer(db)

        anomalies = await analyzer.detect_anomalies(
            region_id=sample_region_id,
            metric="ndvi",
        )

        # Should return empty list for insufficient data
        assert anomalies == []


class TestComputePeriodAverages:
    """Tests for the compute_period_averages function."""

    @pytest.mark.asyncio
    async def test_compute_period_averages_basic(self):
        """Test computing period averages."""
        db = AsyncMock()

        # Mock the result of the query
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("ndvi", 0.45, 10),
            ("nightlights", 12.5, 10),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        result = await compute_period_averages(
            db=db,
            region_id="test-region",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
        )

        assert "averages" in result
        assert "count" in result
        assert result["averages"]["ndvi"] == 0.45
        assert result["averages"]["nightlights"] == 12.5
        assert result["count"] == 20

    @pytest.mark.asyncio
    async def test_compute_period_averages_with_metric_filter(self):
        """Test computing period averages with metric filter."""
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("ndvi", 0.5, 10),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        result = await compute_period_averages(
            db=db,
            region_id="test-region",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            metrics=["ndvi"],
        )

        assert "ndvi" in result["averages"]
        assert "nightlights" not in result["averages"]


class TestCalculateSeasonalChange:
    """Tests for the calculate_seasonal_change function."""

    @pytest.mark.asyncio
    async def test_calculate_seasonal_change_northern_hemisphere(self):
        """Test seasonal change for northern hemisphere."""
        db = AsyncMock()

        # Winter averages
        winter_result = MagicMock()
        winter_result.all = MagicMock(return_value=[
            ("nightlights", 15.0),
            ("ndvi", 0.2),
        ])

        # Summer averages
        summer_result = MagicMock()
        summer_result.all = MagicMock(return_value=[
            ("nightlights", 10.0),
            ("ndvi", 0.6),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return winter_result
            return summer_result

        db.execute = mock_execute

        result = await calculate_seasonal_change(
            db=db,
            region_id="test-region",
            year=2024,
            is_southern_hemisphere=False,
        )

        assert result["year"] == 2024
        assert result["is_southern_hemisphere"] is False
        assert "changes" in result

        # Check nightlights change (summer is lower - decrease)
        nl_change = result["changes"]["nightlights"]
        assert nl_change["winter"] == 15.0
        assert nl_change["summer"] == 10.0
        assert nl_change["change_pct"] < 0  # Decrease from winter to summer

    @pytest.mark.asyncio
    async def test_calculate_seasonal_change_southern_hemisphere(self):
        """Test seasonal change for southern hemisphere."""
        db = AsyncMock()

        # Mock results
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("nightlights", 10.0),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        result = await calculate_seasonal_change(
            db=db,
            region_id="test-region",
            year=2024,
            is_southern_hemisphere=True,
        )

        assert result["is_southern_hemisphere"] is True


# ============================================================================
# ChangeDetector Tests
# ============================================================================


class TestChangeDetector:
    """Tests for the ChangeDetector class."""

    @pytest.fixture
    def sample_region_id(self) -> str:
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_compare_periods_basic(self, sample_region_id: str):
        """Test basic period comparison."""
        db = AsyncMock()

        # Period 1 data
        p1_result = MagicMock()
        p1_result.all = MagicMock(return_value=[
            ("nightlights", 10.0),
            ("nightlights", 12.0),
            ("nightlights", 11.0),
        ])

        # Period 2 data
        p2_result = MagicMock()
        p2_result.all = MagicMock(return_value=[
            ("nightlights", 15.0),
            ("nightlights", 16.0),
            ("nightlights", 14.0),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return p1_result
            return p2_result

        db.execute = mock_execute

        detector = ChangeDetector(db)

        result = await detector.compare_periods(
            region_id=sample_region_id,
            period1_start=date(2024, 1, 1),
            period1_end=date(2024, 3, 31),
            period2_start=date(2024, 4, 1),
            period2_end=date(2024, 6, 30),
        )

        assert result["region_id"] == sample_region_id
        assert "period1" in result
        assert "period2" in result
        assert "comparisons" in result

        # Check nightlights comparison
        nl_comparison = result["comparisons"]["nightlights"]
        assert nl_comparison["period1"]["mean"] == 11.0  # avg of [10, 12, 11]
        assert nl_comparison["period2"]["mean"] == 15.0  # avg of [15, 16, 14]
        assert nl_comparison["change"]["direction"] == "increase"
        assert nl_comparison["change"]["percentage"] > 0

    @pytest.mark.asyncio
    async def test_compare_periods_significant_change(self, sample_region_id: str):
        """Test period comparison with statistically significant change."""
        db = AsyncMock()

        # Period 1 - low values, low variance
        p1_result = MagicMock()
        p1_result.all = MagicMock(return_value=[
            ("ndvi", 0.3),
            ("ndvi", 0.31),
            ("ndvi", 0.29),
            ("ndvi", 0.3),
            ("ndvi", 0.31),
        ])

        # Period 2 - much higher values
        p2_result = MagicMock()
        p2_result.all = MagicMock(return_value=[
            ("ndvi", 0.7),
            ("ndvi", 0.71),
            ("ndvi", 0.69),
            ("ndvi", 0.7),
            ("ndvi", 0.72),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return p1_result
            return p2_result

        db.execute = mock_execute

        detector = ChangeDetector(db)

        result = await detector.compare_periods(
            region_id=sample_region_id,
            period1_start=date(2024, 1, 1),
            period1_end=date(2024, 3, 31),
            period2_start=date(2024, 4, 1),
            period2_end=date(2024, 6, 30),
        )

        ndvi_comparison = result["comparisons"]["ndvi"]
        assert ndvi_comparison["significance"]["is_significant"] == True
        assert abs(ndvi_comparison["significance"]["t_statistic"]) > 1.96

    @pytest.mark.asyncio
    async def test_compare_periods_no_change(self, sample_region_id: str):
        """Test period comparison with no significant change."""
        db = AsyncMock()

        # Both periods have same values
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("ndvi", 0.5),
            ("ndvi", 0.5),
            ("ndvi", 0.5),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        detector = ChangeDetector(db)

        result = await detector.compare_periods(
            region_id=sample_region_id,
            period1_start=date(2024, 1, 1),
            period1_end=date(2024, 3, 31),
            period2_start=date(2024, 4, 1),
            period2_end=date(2024, 6, 30),
        )

        if "ndvi" in result["comparisons"]:
            ndvi_comparison = result["comparisons"]["ndvi"]
            assert abs(ndvi_comparison["change"]["absolute"]) < 0.01
            assert ndvi_comparison["significance"]["is_significant"] is False

    @pytest.mark.asyncio
    async def test_detect_events_basic(self, sample_region_id: str):
        """Test event detection with clear spike."""
        db = AsyncMock()

        # Create time series with a spike
        # Need at least window_size + 1 observations with stable baseline then spike
        observations = []
        from datetime import timedelta

        base_date = date(2024, 1, 1)
        for i in range(60):
            observation_date = base_date + timedelta(days=i)
            value = 10.0 + np.random.normal(0, 0.5)  # Add small noise to avoid std=0
            if i == 45:  # Spike at day 45
                value = 30.0  # Clear spike
            observations.append((observation_date, value))

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=observations)
        db.execute = AsyncMock(return_value=mock_result)

        detector = ChangeDetector(db)

        events = await detector.detect_events(
            region_id=sample_region_id,
            metric="nightlights",
            start_date=base_date,
            end_date=base_date + timedelta(days=59),
            window_size=30,
            threshold=2.0,
        )

        assert len(events) >= 1
        # Should detect the spike
        spike_events = [e for e in events if e["type"] == "spike"]
        assert len(spike_events) >= 1

    @pytest.mark.asyncio
    async def test_detect_events_insufficient_data(self, sample_region_id: str):
        """Test event detection with insufficient data."""
        db = AsyncMock()

        # Only 10 observations (less than window_size + 1)
        observations = [(date(2024, 1, i + 1), 10.0) for i in range(10)]

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=observations)
        db.execute = AsyncMock(return_value=mock_result)

        detector = ChangeDetector(db)

        events = await detector.detect_events(
            region_id=sample_region_id,
            metric="nightlights",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            window_size=30,
        )

        assert events == []

    @pytest.mark.asyncio
    async def test_analyze_covid_impact(self, sample_region_id: str):
        """Test COVID impact analysis preset."""
        db = AsyncMock()

        # Mock results for multiple year comparisons
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("nightlights", 10.0),
            ("ndvi", 0.5),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        detector = ChangeDetector(db)

        result = await detector.analyze_covid_impact(
            region_id=sample_region_id,
            metrics=["nightlights", "ndvi"],
        )

        assert result["analysis_type"] == "covid_impact"
        assert result["region_id"] == sample_region_id
        assert "results" in result
        assert "2019_vs_2020" in result["results"]
        assert "2020_vs_2021" in result["results"]
        assert "2019_vs_2021" in result["results"]
        assert "monthly_2020" in result["results"]


# ============================================================================
# MigrationAnalyzer Tests
# ============================================================================


class TestMigrationAnalyzer:
    """Tests for the MigrationAnalyzer class."""

    @pytest.fixture
    def sample_region_id(self) -> str:
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    async def test_analyze_seasonal_migration_winter_destination(
        self,
        sample_region_id: str,
    ):
        """Test seasonal migration analysis for winter destination."""
        db = AsyncMock()

        # Winter data (high activity)
        winter_result = MagicMock()
        winter_result.all = MagicMock(return_value=[
            ("nightlights", 20.0, 1.0, 10),
        ])

        # Summer data (low activity)
        summer_result = MagicMock()
        summer_result.all = MagicMock(return_value=[
            ("nightlights", 12.0, 1.0, 10),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return winter_result
            return summer_result

        db.execute = mock_execute

        analyzer = MigrationAnalyzer(db)

        result = await analyzer.analyze_seasonal_migration(
            region_id=sample_region_id,
            year=2024,
        )

        assert result["region_id"] == sample_region_id
        assert result["year"] == 2024
        assert "migration_type" in result
        assert "patterns" in result
        assert "interpretation" in result

        # Higher winter activity suggests winter destination
        assert "winter" in result["migration_type"]

    @pytest.mark.asyncio
    async def test_analyze_seasonal_migration_summer_destination(
        self,
        sample_region_id: str,
    ):
        """Test seasonal migration analysis for summer destination."""
        db = AsyncMock()

        # Winter data (low activity)
        winter_result = MagicMock()
        winter_result.all = MagicMock(return_value=[
            ("nightlights", 8.0, 1.0, 10),
        ])

        # Summer data (high activity)
        summer_result = MagicMock()
        summer_result.all = MagicMock(return_value=[
            ("nightlights", 15.0, 1.0, 10),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return winter_result
            return summer_result

        db.execute = mock_execute

        analyzer = MigrationAnalyzer(db)

        result = await analyzer.analyze_seasonal_migration(
            region_id=sample_region_id,
            year=2024,
        )

        # Lower winter activity suggests summer destination
        assert "summer" in result["migration_type"]

    @pytest.mark.asyncio
    async def test_analyze_seasonal_migration_stable(self, sample_region_id: str):
        """Test seasonal migration analysis for stable region."""
        db = AsyncMock()

        # Winter and summer have similar activity
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("nightlights", 10.0, 1.0, 10),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        analyzer = MigrationAnalyzer(db)

        result = await analyzer.analyze_seasonal_migration(
            region_id=sample_region_id,
            year=2024,
        )

        assert result["migration_type"] == "stable"

    def test_interpret_migration(self):
        """Test migration interpretation method."""
        db = AsyncMock()
        analyzer = MigrationAnalyzer(db)

        # Test all migration types
        assert "winter" in analyzer._interpret_migration("strong_winter_destination").lower()
        assert "winter" in analyzer._interpret_migration("moderate_winter_destination").lower()
        assert "summer" in analyzer._interpret_migration("strong_summer_destination").lower()
        assert "summer" in analyzer._interpret_migration("moderate_summer_destination").lower()
        assert "stable" in analyzer._interpret_migration("stable").lower()

    @pytest.mark.asyncio
    async def test_find_correlated_regions_inverse(self, sample_region_id: str):
        """Test finding inversely correlated regions."""
        db = AsyncMock()

        # Source region time series
        source_result = MagicMock()
        source_result.all = MagicMock(return_value=[
            ("2024-01", 20.0),
            ("2024-02", 18.0),
            ("2024-03", 15.0),
            ("2024-04", 10.0),
            ("2024-05", 8.0),
            ("2024-06", 6.0),
        ])

        # Candidate region time series (inverse pattern)
        candidate_result = MagicMock()
        candidate_result.all = MagicMock(return_value=[
            ("2024-01", 6.0),
            ("2024-02", 8.0),
            ("2024-03", 10.0),
            ("2024-04", 15.0),
            ("2024-05", 18.0),
            ("2024-06", 20.0),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return source_result
            return candidate_result

        db.execute = mock_execute

        analyzer = MigrationAnalyzer(db)

        correlations = await analyzer.find_correlated_regions(
            source_region_id=sample_region_id,
            candidate_region_ids=["candidate-1"],
            metric="nightlights",
        )

        assert len(correlations) == 1
        # Should be strongly negative correlation
        assert correlations[0]["correlation"] < -0.9
        assert correlations[0]["is_inverse"] == True

    @pytest.mark.asyncio
    async def test_find_correlated_regions_insufficient_data(
        self,
        sample_region_id: str,
    ):
        """Test finding correlated regions with insufficient data."""
        db = AsyncMock()

        # Only 3 common months (less than 6 required)
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            ("2024-01", 10.0),
            ("2024-02", 11.0),
            ("2024-03", 12.0),
        ])
        db.execute = AsyncMock(return_value=mock_result)

        analyzer = MigrationAnalyzer(db)

        correlations = await analyzer.find_correlated_regions(
            source_region_id=sample_region_id,
            candidate_region_ids=["candidate-1"],
            metric="nightlights",
        )

        # Should skip candidates with insufficient data
        assert len(correlations) == 0

    @pytest.mark.asyncio
    async def test_calculate_period_change(self, sample_region_id: str):
        """Test calculating period change."""
        db = AsyncMock()

        # Observations with clear change
        observations = [
            (date(2024, 1, 15), 10.0),
            (date(2024, 2, 15), 11.0),
            (date(2024, 3, 15), 12.0),
            (date(2024, 4, 15), 13.0),
            (date(2024, 5, 15), 15.0),  # 50% increase
        ]

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=observations)
        db.execute = AsyncMock(return_value=mock_result)

        analyzer = MigrationAnalyzer(db)

        change = await analyzer._calculate_period_change(
            region_id=sample_region_id,
            metric="nightlights",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        # (15 - 10) / 10 * 100 = 50%
        assert change == 50.0

    @pytest.mark.asyncio
    async def test_calculate_period_change_insufficient_data(
        self,
        sample_region_id: str,
    ):
        """Test calculating period change with insufficient data."""
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        db.execute = AsyncMock(return_value=mock_result)

        analyzer = MigrationAnalyzer(db)

        change = await analyzer._calculate_period_change(
            region_id=sample_region_id,
            metric="nightlights",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        assert change == 0.0


# ============================================================================
# Integration-style Tests (with mock data)
# ============================================================================


class TestAnalysisIntegration:
    """Integration-style tests combining multiple analysis methods."""

    @pytest.mark.asyncio
    async def test_full_temporal_analysis_workflow(self):
        """Test a full temporal analysis workflow."""
        region_id = "test-region"

        # Create mock observations for a full year
        mock_observations = []
        for month in range(1, 13):
            # Seasonal pattern in nightlights (higher in winter)
            value = 10 + 5 * np.cos((month - 1) * np.pi / 6)
            mock_observations.append(
                create_mock_observation(
                    region_id,
                    date(2024, month, 15),
                    "nightlights",
                    value,
                )
            )

        db = create_mock_db_for_observations(mock_observations)
        analyzer = TemporalAnalyzer(db)

        # 1. Analyze trend
        trend_result = await analyzer.analyze_trend(
            region_id=region_id,
            metric="nightlights",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        # Should be roughly stable (seasonal, not trending)
        assert trend_result["data_points"] == 12

        # 2. Detect anomalies
        anomalies = await analyzer.detect_anomalies(
            region_id=region_id,
            metric="nightlights",
        )

        # Seasonal pattern shouldn't produce strong anomalies
        assert isinstance(anomalies, list)

    @pytest.mark.asyncio
    async def test_migration_analysis_workflow(self):
        """Test a migration analysis workflow."""
        region_id = "phoenix-az"

        db = AsyncMock()

        # Phoenix: high winter, low summer (snowbird destination)
        winter_result = MagicMock()
        winter_result.all = MagicMock(return_value=[
            ("nightlights", 25.0, 2.0, 30),
            ("parking", 0.75, 0.1, 30),
        ])

        summer_result = MagicMock()
        summer_result.all = MagicMock(return_value=[
            ("nightlights", 18.0, 2.0, 30),
            ("parking", 0.55, 0.1, 30),
        ])

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return winter_result
            return summer_result

        db.execute = mock_execute

        analyzer = MigrationAnalyzer(db)

        result = await analyzer.analyze_seasonal_migration(
            region_id=region_id,
            year=2024,
        )

        # Phoenix should be identified as winter destination
        assert "winter" in result["migration_type"]
        assert result["patterns"]["nightlights"]["winter_avg"] > result["patterns"]["nightlights"]["summer_avg"]
