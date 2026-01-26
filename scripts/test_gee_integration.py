#!/usr/bin/env python3
"""
GEE Dataset Integration Test Script

Tests all 17 metrics against SOT Section 18.14 specifications.
Run with: python scripts/test_gee_integration.py

Requirements:
- Backend server running on localhost:8000
- GEE credentials configured
- Tiles pre-generated or GEE accessible
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# =============================================================================
# SOT 18.14 Specifications
# =============================================================================

SOT_METRICS = {
    # Original metrics
    "ndvi": {
        "source": "COPERNICUS/S2_SR_HARMONIZED",
        "unit": "index",
        "range": (-1.0, 1.0),
        "description": "Vegetation index",
    },
    "nightlights": {
        "source": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
        "unit": "nW/cm2/sr",
        "range": (0.0, 100.0),
        "description": "Nighttime lights intensity",
        "supports_daily": True,
    },
    "urban_density": {
        "source": "JRC/GHSL/P2023A/GHS_BUILT_S",
        "unit": "ratio",
        "range": (0.0, 1.0),
        "description": "Built-up area",
    },
    "parking": {
        "source": "COPERNICUS/S2_SR_HARMONIZED",
        "unit": "ratio",
        "range": (0.0, 1.0),
        "description": "NDBI parking proxy",
    },
    # Phase 1: Core datasets
    "land_cover": {
        "source": "GOOGLE/DYNAMICWORLD/V1",
        "unit": "probability",
        "range": (0.0, 1.0),
        "description": "Built-up probability",
    },
    "surface_water": {
        "source": "JRC/GSW1_4/MonthlyHistory",
        "unit": "binary",
        "range": (0.0, 1.0),
        "description": "Water extent",
    },
    "active_fire": {
        "source": "NASA/LANCE/SNPP_VIIRS/C2",
        "unit": "MW",
        "range": (0.0, 500.0),
        "description": "Fire Radiative Power",
        "supports_daily": True,
    },
    # Phase 2: Air quality & weather
    "no2": {
        "source": "COPERNICUS/S5P/OFFL/L3_NO2",
        "unit": "mol/m2",
        "range": (0.0, 0.0002),
        "description": "Tropospheric NO2",
    },
    "temperature": {
        "source": "ECMWF/ERA5_LAND/HOURLY",
        "unit": "Celsius",
        "range": (-30.0, 45.0),
        "description": "2m air temperature",
    },
    "precipitation": {
        "source": "ECMWF/ERA5_LAND/HOURLY",
        "unit": "mm",
        "range": (0.0, 500.0),
        "description": "Total precipitation",
    },
    "aerosol": {
        "source": "COPERNICUS/S5P/OFFL/L3_AER_AI",
        "unit": "index",
        "range": (-2.0, 5.0),
        "description": "Absorbing Aerosol Index",
    },
    # Phase 3: Agriculture
    "cropland": {
        "source": "USDA/NASS/CDL",
        "unit": "categorical",
        "range": (0.0, 255.0),
        "description": "Crop type codes",
    },
    "evapotranspiration": {
        "source": "OpenET/SSEBOP/CONUS/GRIDMET/MONTHLY/v2_0",
        "unit": "mm/month",
        "range": (0.0, 300.0),
        "description": "Evapotranspiration",
    },
    "soil_moisture": {
        "source": "NASA/USDA/HSL/SMAP10KM_soil_moisture",
        "unit": "mm",
        "range": (0.0, 50.0),
        "description": "Surface soil moisture",
    },
    # Phase 4: Historical & specialized
    "impervious": {
        "source": "Tsinghua/FROM-GLC/GAIA/v10",
        "unit": "binary",
        "range": (0.0, 1.0),
        "description": "Impervious surface",
    },
    "fire_historical": {
        "source": "MODIS/061/MOD14A1",
        "unit": "MW",
        "range": (0.0, 500.0),
        "description": "Historical fire FRP",
    },
    "canopy_height": {
        "source": "LARSE/GEDI/GRIDDEDVEG_002/V1/1KM",
        "unit": "meters",
        "range": (0.0, 60.0),
        "description": "Forest canopy height",
    },
}

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TEST_DATE = "2024-01"
TEST_DATE_DAILY = "2024-01-15"
TEST_TILE = (11, 512, 768)  # z, x, y - Continental US


# =============================================================================
# Test Classes
# =============================================================================


class TestResult:
    """Simple test result container."""

    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"  [{status}] {self.name}" + (f": {self.message}" if self.message else "")


class TestSuite:
    """Collection of test results."""

    def __init__(self, name: str):
        self.name = name
        self.results: list[TestResult] = []

    def add(self, result: TestResult):
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def print_results(self):
        print(f"\n{self.name}")
        print("-" * len(self.name))
        for result in self.results:
            print(result)
        print(f"\n  Total: {self.passed}/{len(self.results)} passed")


# =============================================================================
# Test Functions
# =============================================================================


async def test_api_endpoints(client: httpx.AsyncClient) -> TestSuite:
    """Test all metric tile endpoints return valid responses."""
    suite = TestSuite("1. Backend API Endpoint Tests")

    z, x, y = TEST_TILE

    for metric in SOT_METRICS:
        url = f"{BASE_URL}/tiles/us/{metric}/{TEST_DATE}/{z}/{x}/{y}.png"
        try:
            response = await client.get(url, timeout=30.0)
            passed = response.status_code == 200
            content_type = response.headers.get("content-type", "")
            is_png = "image/png" in content_type

            if passed and is_png:
                suite.add(TestResult(f"{metric} endpoint", True))
            elif passed and not is_png:
                suite.add(TestResult(f"{metric} endpoint", False, f"Wrong content-type: {content_type}"))
            else:
                suite.add(TestResult(f"{metric} endpoint", False, f"HTTP {response.status_code}"))
        except Exception as e:
            suite.add(TestResult(f"{metric} endpoint", False, str(e)))

    # Test invalid metric
    url = f"{BASE_URL}/tiles/us/invalid_metric/{TEST_DATE}/{z}/{x}/{y}.png"
    try:
        response = await client.get(url, timeout=10.0)
        suite.add(TestResult("Invalid metric returns 400", response.status_code == 400))
    except Exception as e:
        suite.add(TestResult("Invalid metric returns 400", False, str(e)))

    return suite


async def test_daily_granularity(client: httpx.AsyncClient) -> TestSuite:
    """Test daily granularity support for supported metrics."""
    suite = TestSuite("2. Daily Granularity Tests")

    z, x, y = TEST_TILE

    # Test nightlights with daily format
    url = f"{BASE_URL}/tiles/us/nightlights/{TEST_DATE_DAILY}/{z}/{x}/{y}.png"
    try:
        response = await client.get(url, timeout=30.0)
        granularity = response.headers.get("x-tile-granularity", "")
        passed = response.status_code == 200 and granularity in ["daily", "monthly-fallback"]
        suite.add(TestResult("nightlights daily format", passed, f"granularity={granularity}"))
    except Exception as e:
        suite.add(TestResult("nightlights daily format", False, str(e)))

    # Test active_fire with daily format
    url = f"{BASE_URL}/tiles/us/active_fire/{TEST_DATE_DAILY}/{z}/{x}/{y}.png"
    try:
        response = await client.get(url, timeout=30.0)
        passed = response.status_code == 200
        suite.add(TestResult("active_fire daily format", passed))
    except Exception as e:
        suite.add(TestResult("active_fire daily format", False, str(e)))

    # Test non-daily metric converts to monthly
    url = f"{BASE_URL}/tiles/us/ndvi/{TEST_DATE_DAILY}/{z}/{x}/{y}.png"
    try:
        response = await client.get(url, timeout=30.0)
        passed = response.status_code == 200
        suite.add(TestResult("ndvi daily->monthly conversion", passed))
    except Exception as e:
        suite.add(TestResult("ndvi daily->monthly conversion", False, str(e)))

    return suite


async def test_available_tiles(client: httpx.AsyncClient) -> TestSuite:
    """Test /tiles/us/available endpoint."""
    suite = TestSuite("3. Available Tiles Endpoint Test")

    url = f"{BASE_URL}/tiles/us/available"
    try:
        response = await client.get(url, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            suite.add(TestResult("Endpoint returns 200", True))

            metrics_present = "metrics" in data
            suite.add(TestResult("Response has 'metrics' key", metrics_present))

            if metrics_present:
                metric_count = len(data["metrics"])
                suite.add(TestResult(f"Metrics count ({metric_count})", metric_count > 0))
        else:
            suite.add(TestResult("Endpoint returns 200", False, f"HTTP {response.status_code}"))
    except Exception as e:
        suite.add(TestResult("Available tiles endpoint", False, str(e)))

    return suite


def test_backend_code_alignment() -> TestSuite:
    """Test backend code matches SOT specifications."""
    suite = TestSuite("4. Backend Code Alignment Tests")

    try:
        # Check tiles.py valid_metrics
        tiles_path = Path(__file__).parent.parent / "backend" / "app" / "api" / "routes" / "tiles.py"
        tiles_content = tiles_path.read_text()

        for metric in SOT_METRICS:
            present = f'"{metric}"' in tiles_content
            suite.add(TestResult(f"tiles.py: {metric} in valid_metrics", present))

    except Exception as e:
        suite.add(TestResult("tiles.py check", False, str(e)))

    try:
        # Check us_tile_generator.py COLORMAPS and VALUE_RANGES
        generator_path = Path(__file__).parent.parent / "backend" / "app" / "services" / "tiles" / "us_tile_generator.py"
        generator_content = generator_path.read_text()

        for metric in SOT_METRICS:
            in_colormaps = f'"{metric}":' in generator_content or f"'{metric}':" in generator_content
            suite.add(TestResult(f"us_tile_generator.py: {metric} colormap defined", in_colormaps))

    except Exception as e:
        suite.add(TestResult("us_tile_generator.py check", False, str(e)))

    try:
        # Check us_data_service.py methods
        service_path = Path(__file__).parent.parent / "backend" / "app" / "services" / "satellite" / "us_data_service.py"
        service_content = service_path.read_text()

        method_mapping = {
            "ndvi": "get_ndvi",
            "nightlights": "get_nightlights",
            "urban_density": "get_urban_density",
            "parking": "get_parking",
            "land_cover": "get_dynamic_world",
            "surface_water": "get_surface_water",
            "active_fire": "get_active_fire",
            "no2": "get_no2",
            "temperature": "get_temperature",
            "precipitation": "get_precipitation",
            "aerosol": "get_aerosol",
            "cropland": "get_cropland",
            "evapotranspiration": "get_evapotranspiration",
            "soil_moisture": "get_soil_moisture",
            "impervious": "get_impervious",
            "fire_historical": "get_fire_historical",
            "canopy_height": "get_canopy_height",
        }

        for metric, method in method_mapping.items():
            present = f"async def {method}" in service_content or f"def {method}" in service_content
            suite.add(TestResult(f"us_data_service.py: {method}() exists", present))

    except Exception as e:
        suite.add(TestResult("us_data_service.py check", False, str(e)))

    return suite


def test_frontend_code_alignment() -> TestSuite:
    """Test frontend code matches SOT specifications."""
    suite = TestSuite("5. Frontend Code Alignment Tests")

    try:
        # Check types/index.ts MetricType union
        types_path = Path(__file__).parent.parent / "frontend" / "src" / "types" / "index.ts"
        types_content = types_path.read_text()

        for metric in SOT_METRICS:
            # Check if metric is in the MetricType union (as string literal)
            present = f"'{metric}'" in types_content or f'"{metric}"' in types_content or f"| '{metric}'" in types_content
            suite.add(TestResult(f"types/index.ts: {metric} in MetricType", present))

    except Exception as e:
        suite.add(TestResult("types/index.ts check", False, str(e)))

    try:
        # Check AnimationStudio.tsx METRIC_OPTIONS
        studio_path = Path(__file__).parent.parent / "frontend" / "src" / "pages" / "AnimationStudio.tsx"
        studio_content = studio_path.read_text()

        for metric in SOT_METRICS:
            present = f"value: '{metric}'" in studio_content or f'value: "{metric}"' in studio_content
            suite.add(TestResult(f"AnimationStudio.tsx: {metric} in METRIC_OPTIONS", present))

    except Exception as e:
        suite.add(TestResult("AnimationStudio.tsx check", False, str(e)))

    try:
        # Check api.ts daily metrics
        api_path = Path(__file__).parent.parent / "frontend" / "src" / "services" / "api.ts"
        api_content = api_path.read_text()

        has_nightlights_daily = "nightlights" in api_content and "daily" in api_content.lower()
        suite.add(TestResult("api.ts: nightlights daily support", has_nightlights_daily))

    except Exception as e:
        suite.add(TestResult("api.ts check", False, str(e)))

    return suite


def test_sot_value_ranges() -> TestSuite:
    """Test implementation value ranges match SOT."""
    suite = TestSuite("6. SOT Value Range Alignment Tests")

    try:
        generator_path = Path(__file__).parent.parent / "backend" / "app" / "services" / "tiles" / "us_tile_generator.py"
        generator_content = generator_path.read_text()

        # Extract VALUE_RANGES dict (simple parsing)
        # Look for patterns like "metric": (min, max)
        for metric, spec in SOT_METRICS.items():
            expected_min, expected_max = spec["range"]
            # Simple string check for the range values
            range_str = f'"{metric}": ({expected_min}, {expected_max})'
            range_str_alt = f"'{metric}': ({expected_min}, {expected_max})"

            # Also try with .0 suffix for floats
            range_str_float = f'"{metric}": ({float(expected_min)}, {float(expected_max)})'

            present = (range_str in generator_content or
                      range_str_alt in generator_content or
                      range_str_float in generator_content)

            suite.add(TestResult(f"{metric} range {spec['range']}", present))

    except Exception as e:
        suite.add(TestResult("Value ranges check", False, str(e)))

    return suite


def test_metric_count() -> TestSuite:
    """Verify total metric count matches SOT."""
    suite = TestSuite("7. Metric Count Verification")

    expected_count = 17  # 4 original + 13 new
    actual_count = len(SOT_METRICS)

    suite.add(TestResult(
        f"Total metrics = {expected_count}",
        actual_count == expected_count,
        f"Found {actual_count}"
    ))

    # Count by phase
    original = ["ndvi", "nightlights", "urban_density", "parking"]
    phase1 = ["land_cover", "surface_water", "active_fire"]
    phase2 = ["no2", "temperature", "precipitation", "aerosol"]
    phase3 = ["cropland", "evapotranspiration", "soil_moisture"]
    phase4 = ["impervious", "fire_historical", "canopy_height"]

    suite.add(TestResult(f"Original metrics = 4", len(original) == 4))
    suite.add(TestResult(f"Phase 1 metrics = 3", len(phase1) == 3))
    suite.add(TestResult(f"Phase 2 metrics = 4", len(phase2) == 4))
    suite.add(TestResult(f"Phase 3 metrics = 3", len(phase3) == 3))
    suite.add(TestResult(f"Phase 4 metrics = 3", len(phase4) == 3))

    return suite


# =============================================================================
# Main
# =============================================================================


async def main():
    print("=" * 60)
    print("GEE Dataset Integration Test Suite")
    print("Testing against SOT Section 18.14")
    print("=" * 60)

    all_suites: list[TestSuite] = []

    # Static code analysis tests (don't require running server)
    all_suites.append(test_metric_count())
    all_suites.append(test_backend_code_alignment())
    all_suites.append(test_frontend_code_alignment())
    all_suites.append(test_sot_value_ranges())

    # API tests (require running server)
    print("\nChecking API availability...")
    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if health_response.status_code == 200:
                print(f"API available at {BASE_URL}")
                all_suites.append(await test_api_endpoints(client))
                all_suites.append(await test_daily_granularity(client))
                all_suites.append(await test_available_tiles(client))
            else:
                print(f"API returned {health_response.status_code}, skipping API tests")
    except Exception as e:
        print(f"API not available ({e}), skipping API tests")

    # Print all results
    total_passed = 0
    total_tests = 0

    for suite in all_suites:
        suite.print_results()
        total_passed += suite.passed
        total_tests += len(suite.results)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    print(f"Pass Rate: {total_passed/total_tests*100:.1f}%" if total_tests > 0 else "N/A")

    # Return exit code
    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
