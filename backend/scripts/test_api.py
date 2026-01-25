#!/usr/bin/env python3
"""
API Test Script for Satellite Data Platform

This script tests live API endpoints against a running server.
Designed to run against http://localhost:8000 (or custom URL).

Tests covered:
1. Health endpoint
2. Root endpoint
3. Regions CRUD (list, create, get, delete)
4. Metrics endpoints
5. Analysis endpoints
6. Export endpoints
7. Collection endpoints (if applicable)

Usage:
    # From backend directory
    python -m scripts.test_api

    # Or directly
    python scripts/test_api.py

    # Custom API URL
    python -m scripts.test_api --url http://localhost:8000

    # Verbose output
    python -m scripts.test_api --verbose

    # Run specific test groups
    python -m scripts.test_api --tests health,regions

    # Skip cleanup (keep created test data)
    python -m scripts.test_api --no-cleanup

Requirements:
    - Backend API server running
    - httpx package installed

Environment:
    API_URL - Base URL for the API (default: http://localhost:8000)
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

try:
    import httpx
except ImportError:
    print("Error: httpx package required. Install with: pip install httpx")
    sys.exit(1)


# ANSI color codes
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    duration_ms: float
    response_status: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuite:
    """Collection of test results."""
    name: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


class APITester:
    """API endpoint tester."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        verbose: bool = False,
        cleanup: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.cleanup = cleanup
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self.suites: list[TestSuite] = []

        # Track created resources for cleanup
        self.created_region_ids: list[str] = []
        self.test_region_id: str | None = None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    def _print_test_result(self, result: TestResult) -> None:
        """Print a single test result."""
        if result.passed:
            icon = f"{Colors.GREEN}[PASS]{Colors.RESET}"
        else:
            icon = f"{Colors.RED}[FAIL]{Colors.RESET}"

        print(f"  {icon} {result.name} ({result.duration_ms:.0f}ms)")

        if not result.passed or self.verbose:
            print(f"       {Colors.DIM}{result.message}{Colors.RESET}")
            if result.response_status:
                print(f"       Status: {result.response_status}")

    def _print_suite_header(self, name: str) -> None:
        """Print a test suite header."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}>> {name}{Colors.RESET}")

    def _print_suite_summary(self, suite: TestSuite) -> None:
        """Print a test suite summary."""
        if suite.failed == 0:
            color = Colors.GREEN
        else:
            color = Colors.RED

        print(f"   {color}{suite.passed}/{suite.total} passed{Colors.RESET}")

    async def _run_test(
        self,
        name: str,
        test_func: Callable,
        *args,
        **kwargs,
    ) -> TestResult:
        """Run a single test and record the result."""
        start_time = time.time()
        try:
            result = await test_func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000

            if isinstance(result, TestResult):
                result.duration_ms = duration
                return result

            # If test_func returned True/False
            return TestResult(
                name=name,
                passed=bool(result),
                message="Test completed" if result else "Test failed",
                duration_ms=duration,
            )

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return TestResult(
                name=name,
                passed=False,
                message=f"Exception: {type(e).__name__}: {e}",
                duration_ms=duration,
            )

    # =========================================================================
    # Health Tests
    # =========================================================================

    async def test_health_endpoint(self) -> TestResult:
        """Test the /health endpoint."""
        try:
            response = await self.client.get("/health")
            data = response.json()

            if response.status_code == 200 and data.get("status") == "healthy":
                return TestResult(
                    name="GET /health",
                    passed=True,
                    message=f"Status: {data.get('status')}, Version: {data.get('version')}",
                    duration_ms=0,
                    response_status=response.status_code,
                    details=data,
                )
            else:
                return TestResult(
                    name="GET /health",
                    passed=False,
                    message=f"Unexpected response: {data}",
                    duration_ms=0,
                    response_status=response.status_code,
                )
        except httpx.ConnectError:
            return TestResult(
                name="GET /health",
                passed=False,
                message=f"Cannot connect to {self.base_url}. Is the server running?",
                duration_ms=0,
            )

    async def test_root_endpoint(self) -> TestResult:
        """Test the / endpoint."""
        response = await self.client.get("/")
        data = response.json()

        if response.status_code == 200 and "name" in data:
            return TestResult(
                name="GET /",
                passed=True,
                message=f"API: {data.get('name')}, Version: {data.get('version')}",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="GET /",
                passed=False,
                message=f"Unexpected response: {data}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def run_health_tests(self) -> TestSuite:
        """Run all health-related tests."""
        suite = TestSuite(name="Health Endpoints")
        self._print_suite_header(suite.name)

        # Test health endpoint first to check connectivity
        result = await self._run_test("Health", self.test_health_endpoint)
        suite.results.append(result)
        self._print_test_result(result)

        if not result.passed:
            print(f"\n{Colors.RED}Server not reachable. Skipping remaining tests.{Colors.RESET}")
            self.suites.append(suite)
            return suite

        result = await self._run_test("Root", self.test_root_endpoint)
        suite.results.append(result)
        self._print_test_result(result)

        self._print_suite_summary(suite)
        self.suites.append(suite)
        return suite

    # =========================================================================
    # Regions Tests
    # =========================================================================

    async def test_list_regions(self) -> TestResult:
        """Test GET /api/v1/regions."""
        response = await self.client.get("/api/v1/regions")

        if response.status_code == 200:
            data = response.json()
            return TestResult(
                name="GET /api/v1/regions",
                passed=True,
                message=f"Found {data.get('total', 0)} regions",
                duration_ms=0,
                response_status=response.status_code,
                details={"total": data.get("total"), "page": data.get("page")},
            )
        else:
            return TestResult(
                name="GET /api/v1/regions",
                passed=False,
                message=f"Failed with status {response.status_code}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_create_region(self) -> TestResult:
        """Test POST /api/v1/regions."""
        test_geometry = {
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

        payload = {
            "name": f"API Test Region {uuid4().hex[:8]}",
            "description": "Temporary region for API testing",
            "geometry": test_geometry,
            "country": "United States",
            "state_province": "Arizona",
            "category": "migration_hotspot",
        }

        response = await self.client.post("/api/v1/regions", json=payload)

        if response.status_code == 201:
            data = response.json()
            region_id = data.get("id")
            self.created_region_ids.append(region_id)
            self.test_region_id = region_id

            return TestResult(
                name="POST /api/v1/regions",
                passed=True,
                message=f"Created region: {data.get('name')} (ID: {region_id})",
                duration_ms=0,
                response_status=response.status_code,
                details={"region_id": region_id},
            )
        else:
            return TestResult(
                name="POST /api/v1/regions",
                passed=False,
                message=f"Failed with status {response.status_code}: {response.text}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_get_region(self) -> TestResult:
        """Test GET /api/v1/regions/{id}."""
        if not self.test_region_id:
            return TestResult(
                name="GET /api/v1/regions/{id}",
                passed=False,
                message="No test region available (create test may have failed)",
                duration_ms=0,
            )

        response = await self.client.get(f"/api/v1/regions/{self.test_region_id}")

        if response.status_code == 200:
            data = response.json()
            return TestResult(
                name="GET /api/v1/regions/{id}",
                passed=True,
                message=f"Retrieved region: {data.get('name')}",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="GET /api/v1/regions/{id}",
                passed=False,
                message=f"Failed with status {response.status_code}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_get_nonexistent_region(self) -> TestResult:
        """Test GET /api/v1/regions/{id} with invalid ID."""
        fake_id = str(uuid4())
        response = await self.client.get(f"/api/v1/regions/{fake_id}")

        if response.status_code == 404:
            return TestResult(
                name="GET /api/v1/regions/{invalid_id}",
                passed=True,
                message="Correctly returned 404 for nonexistent region",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="GET /api/v1/regions/{invalid_id}",
                passed=False,
                message=f"Expected 404, got {response.status_code}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_delete_region(self, region_id: str | None = None) -> TestResult:
        """Test DELETE /api/v1/regions/{id}."""
        target_id = region_id or self.test_region_id

        if not target_id:
            return TestResult(
                name="DELETE /api/v1/regions/{id}",
                passed=False,
                message="No test region available for deletion",
                duration_ms=0,
            )

        response = await self.client.delete(f"/api/v1/regions/{target_id}")

        if response.status_code == 204:
            # Remove from cleanup list since we already deleted it
            if target_id in self.created_region_ids:
                self.created_region_ids.remove(target_id)
            if target_id == self.test_region_id:
                self.test_region_id = None

            return TestResult(
                name="DELETE /api/v1/regions/{id}",
                passed=True,
                message=f"Successfully deleted region {target_id}",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="DELETE /api/v1/regions/{id}",
                passed=False,
                message=f"Failed with status {response.status_code}: {response.text}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def run_regions_tests(self) -> TestSuite:
        """Run all region-related tests."""
        suite = TestSuite(name="Regions Endpoints")
        self._print_suite_header(suite.name)

        tests = [
            ("List Regions", self.test_list_regions),
            ("Create Region", self.test_create_region),
            ("Get Region", self.test_get_region),
            ("Get Nonexistent Region", self.test_get_nonexistent_region),
        ]

        for name, test_func in tests:
            result = await self._run_test(name, test_func)
            suite.results.append(result)
            self._print_test_result(result)

        # Only test delete if we're doing cleanup or explicitly testing
        if self.cleanup:
            result = await self._run_test("Delete Region", self.test_delete_region)
            suite.results.append(result)
            self._print_test_result(result)

        self._print_suite_summary(suite)
        self.suites.append(suite)
        return suite

    # =========================================================================
    # Metrics Tests
    # =========================================================================

    async def test_get_metrics(self) -> TestResult:
        """Test GET /api/v1/metrics/{region_id}."""
        # First, ensure we have a test region
        if not self.test_region_id:
            # Try to create one
            await self.test_create_region()

        if not self.test_region_id:
            return TestResult(
                name="GET /api/v1/metrics/{region_id}",
                passed=False,
                message="No test region available",
                duration_ms=0,
            )

        response = await self.client.get(f"/api/v1/metrics/{self.test_region_id}")

        if response.status_code == 200:
            data = response.json()
            metrics_count = len(data.get("metrics", {}))
            return TestResult(
                name="GET /api/v1/metrics/{region_id}",
                passed=True,
                message=f"Retrieved metrics for region (metrics: {metrics_count})",
                duration_ms=0,
                response_status=response.status_code,
                details={
                    "region_name": data.get("region_name"),
                    "metrics": list(data.get("metrics", {}).keys()),
                },
            )
        else:
            return TestResult(
                name="GET /api/v1/metrics/{region_id}",
                passed=False,
                message=f"Failed with status {response.status_code}: {response.text}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_get_metrics_with_filters(self) -> TestResult:
        """Test GET /api/v1/metrics/{region_id} with query filters."""
        if not self.test_region_id:
            return TestResult(
                name="GET /api/v1/metrics with filters",
                passed=False,
                message="No test region available",
                duration_ms=0,
            )

        today = date.today()
        start_date = today - timedelta(days=365)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
            "metrics": ["ndvi", "nightlights"],
            "granularity": "monthly",
        }

        response = await self.client.get(
            f"/api/v1/metrics/{self.test_region_id}",
            params=params,
        )

        if response.status_code == 200:
            return TestResult(
                name="GET /api/v1/metrics with filters",
                passed=True,
                message="Filters applied successfully",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="GET /api/v1/metrics with filters",
                passed=False,
                message=f"Failed with status {response.status_code}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def run_metrics_tests(self) -> TestSuite:
        """Run all metrics-related tests."""
        suite = TestSuite(name="Metrics Endpoints")
        self._print_suite_header(suite.name)

        tests = [
            ("Get Metrics", self.test_get_metrics),
            ("Get Metrics with Filters", self.test_get_metrics_with_filters),
        ]

        for name, test_func in tests:
            result = await self._run_test(name, test_func)
            suite.results.append(result)
            self._print_test_result(result)

        self._print_suite_summary(suite)
        self.suites.append(suite)
        return suite

    # =========================================================================
    # Analysis Tests
    # =========================================================================

    async def test_compare_periods(self) -> TestResult:
        """Test POST /api/v1/analysis/compare."""
        if not self.test_region_id:
            return TestResult(
                name="POST /api/v1/analysis/compare",
                passed=False,
                message="No test region available",
                duration_ms=0,
            )

        today = date.today()
        payload = {
            "region_id": self.test_region_id,
            "period_a_start": (today - timedelta(days=180)).isoformat(),
            "period_a_end": (today - timedelta(days=90)).isoformat(),
            "period_b_start": (today - timedelta(days=90)).isoformat(),
            "period_b_end": today.isoformat(),
            "metrics": ["ndvi", "nightlights"],
        }

        response = await self.client.post("/api/v1/analysis/compare", json=payload)

        if response.status_code == 200:
            data = response.json()
            return TestResult(
                name="POST /api/v1/analysis/compare",
                passed=True,
                message=f"Comparison completed for {data.get('region_name')}",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="POST /api/v1/analysis/compare",
                passed=False,
                message=f"Failed with status {response.status_code}: {response.text}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def run_analysis_tests(self) -> TestSuite:
        """Run all analysis-related tests."""
        suite = TestSuite(name="Analysis Endpoints")
        self._print_suite_header(suite.name)

        tests = [
            ("Compare Periods", self.test_compare_periods),
        ]

        for name, test_func in tests:
            result = await self._run_test(name, test_func)
            suite.results.append(result)
            self._print_test_result(result)

        self._print_suite_summary(suite)
        self.suites.append(suite)
        return suite

    # =========================================================================
    # Export Tests
    # =========================================================================

    async def test_export_csv(self) -> TestResult:
        """Test POST /api/v1/exports/csv."""
        if not self.test_region_id:
            return TestResult(
                name="POST /api/v1/exports/csv",
                passed=False,
                message="No test region available",
                duration_ms=0,
            )

        today = date.today()
        payload = {
            "region_ids": [self.test_region_id],
            "metrics": ["ndvi"],
            "start_date": (today - timedelta(days=90)).isoformat(),
            "end_date": today.isoformat(),
            "include_metadata": True,
        }

        response = await self.client.post("/api/v1/exports/csv", json=payload)

        # Expect 202 Accepted for async job
        if response.status_code == 202:
            data = response.json()
            return TestResult(
                name="POST /api/v1/exports/csv",
                passed=True,
                message=f"Export job created: {data.get('id')}",
                duration_ms=0,
                response_status=response.status_code,
                details={"export_id": data.get("id"), "status": data.get("status")},
            )
        else:
            return TestResult(
                name="POST /api/v1/exports/csv",
                passed=False,
                message=f"Failed with status {response.status_code}: {response.text}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def test_export_status(self) -> TestResult:
        """Test GET /api/v1/exports/{id}/status."""
        # Use a fake ID - should return 404
        fake_id = str(uuid4())
        response = await self.client.get(f"/api/v1/exports/{fake_id}/status")

        if response.status_code == 404:
            return TestResult(
                name="GET /api/v1/exports/{id}/status (404)",
                passed=True,
                message="Correctly returned 404 for nonexistent export",
                duration_ms=0,
                response_status=response.status_code,
            )
        else:
            return TestResult(
                name="GET /api/v1/exports/{id}/status (404)",
                passed=False,
                message=f"Expected 404, got {response.status_code}",
                duration_ms=0,
                response_status=response.status_code,
            )

    async def run_export_tests(self) -> TestSuite:
        """Run all export-related tests."""
        suite = TestSuite(name="Export Endpoints")
        self._print_suite_header(suite.name)

        tests = [
            ("Export CSV", self.test_export_csv),
            ("Export Status (404)", self.test_export_status),
        ]

        for name, test_func in tests:
            result = await self._run_test(name, test_func)
            suite.results.append(result)
            self._print_test_result(result)

        self._print_suite_summary(suite)
        self.suites.append(suite)
        return suite

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_test_data(self) -> None:
        """Clean up any created test resources."""
        if not self.cleanup:
            return

        if self.created_region_ids:
            print(f"\n{Colors.CYAN}Cleaning up test data...{Colors.RESET}")
            for region_id in self.created_region_ids:
                try:
                    response = await self.client.delete(f"/api/v1/regions/{region_id}")
                    if response.status_code == 204:
                        print(f"  Deleted region: {region_id}")
                    else:
                        print(f"  Failed to delete region {region_id}: {response.status_code}")
                except Exception as e:
                    print(f"  Error deleting region {region_id}: {e}")

    # =========================================================================
    # Main Test Runner
    # =========================================================================

    async def run_all_tests(
        self,
        test_groups: list[str] | None = None,
    ) -> tuple[int, int]:
        """
        Run all tests or specified test groups.

        Returns:
            Tuple of (passed, failed) counts
        """
        print(f"\n{'=' * 60}")
        print(f"{'SATELLITE DATA API TESTS'.center(60)}")
        print(f"{'=' * 60}")
        print(f"\nTarget: {Colors.CYAN}{self.base_url}{Colors.RESET}")

        # Default to all test groups
        if test_groups is None:
            test_groups = ["health", "regions", "metrics", "analysis", "exports"]

        # Always run health tests first to check connectivity
        health_suite = await self.run_health_tests()

        # If health tests failed, don't run other tests
        if health_suite.failed > 0:
            return (health_suite.passed, health_suite.failed)

        # Run requested test suites
        if "regions" in test_groups:
            await self.run_regions_tests()

        if "metrics" in test_groups:
            await self.run_metrics_tests()

        if "analysis" in test_groups:
            await self.run_analysis_tests()

        if "exports" in test_groups:
            await self.run_export_tests()

        # Cleanup
        await self.cleanup_test_data()

        # Calculate totals
        total_passed = sum(s.passed for s in self.suites)
        total_failed = sum(s.failed for s in self.suites)

        # Print final summary
        self._print_final_summary(total_passed, total_failed)

        return (total_passed, total_failed)

    def _print_final_summary(self, passed: int, failed: int) -> None:
        """Print the final test summary."""
        total = passed + failed

        print(f"\n{'=' * 60}")
        print(f"{'TEST SUMMARY'.center(60)}")
        print(f"{'=' * 60}")

        if failed == 0:
            color = Colors.GREEN
            status = "ALL TESTS PASSED"
        else:
            color = Colors.RED
            status = "SOME TESTS FAILED"

        print(f"\n{color}{Colors.BOLD}{status}{Colors.RESET}")
        print(f"\n  Total:  {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {failed}{Colors.RESET}")

        # Per-suite breakdown
        print(f"\n  By Suite:")
        for suite in self.suites:
            if suite.failed == 0:
                color = Colors.GREEN
            else:
                color = Colors.RED
            print(f"    {suite.name}: {color}{suite.passed}/{suite.total}{Colors.RESET}")

        print()


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test live API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--tests", "-t",
        default="health,regions,metrics,analysis,exports",
        help="Comma-separated list of test groups to run (default: all)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of test data",
    )

    args = parser.parse_args()

    test_groups = [t.strip() for t in args.tests.split(",")]

    tester = APITester(
        base_url=args.url,
        verbose=args.verbose,
        cleanup=not args.no_cleanup,
    )

    try:
        passed, failed = await tester.run_all_tests(test_groups=test_groups)
        return 0 if failed == 0 else 1
    finally:
        await tester.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
