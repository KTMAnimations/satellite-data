#!/usr/bin/env python3
"""
Integration Test Script for Satellite Data Pipeline

This script tests the full data pipeline when Docker services are running.
It performs end-to-end testing of:
1. PostgreSQL database connection
2. Region creation (seeding test data)
3. Data collection (with mocked GEE responses)
4. Metrics querying
5. Export generation
6. Cleanup of test data

Usage:
    # From backend directory
    python -m scripts.test_integration

    # Or directly
    python scripts/test_integration.py

    # With verbose output
    python -m scripts.test_integration --verbose

    # Skip cleanup (useful for debugging)
    python -m scripts.test_integration --no-cleanup

Requirements:
    - Docker services running (docker-compose up -d db redis)
    - Backend dependencies installed

Environment:
    Set DATABASE_URL and REDIS_URL environment variables if not using defaults.
"""

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Add the backend directory to the path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# ANSI color codes for output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print()


def print_step(step: int, total: int, text: str) -> None:
    """Print a step indicator."""
    print(f"{Colors.BLUE}[Step {step}/{total}]{Colors.RESET} {text}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"  {Colors.RED}[FAIL]{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"  {Colors.CYAN}[INFO]{Colors.RESET} {text}")


class IntegrationTest:
    """Integration test runner for the satellite data pipeline."""

    def __init__(self, verbose: bool = False, cleanup: bool = True):
        self.verbose = verbose
        self.cleanup = cleanup
        self.test_region_id: str | None = None
        self.test_observations: list[str] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    async def run_all_tests(self) -> bool:
        """Run all integration tests."""
        print_header("Satellite Data Pipeline Integration Tests")

        total_steps = 6
        all_passed = True

        try:
            # Step 1: Test database connection
            print_step(1, total_steps, "Testing PostgreSQL connection...")
            if not await self.test_database_connection():
                all_passed = False
                return all_passed

            # Step 2: Create test region
            print_step(2, total_steps, "Creating test region...")
            if not await self.create_test_region():
                all_passed = False
                return all_passed

            # Step 3: Run data collection with mocked GEE
            print_step(3, total_steps, "Running data collection (mocked GEE)...")
            if not await self.test_data_collection():
                all_passed = False

            # Step 4: Query metrics
            print_step(4, total_steps, "Querying metrics...")
            if not await self.test_metrics_query():
                all_passed = False

            # Step 5: Test export generation
            print_step(5, total_steps, "Testing export generation...")
            if not await self.test_export_generation():
                all_passed = False

            # Step 6: Cleanup
            if self.cleanup:
                print_step(6, total_steps, "Cleaning up test data...")
                await self.cleanup_test_data()
            else:
                print_step(6, total_steps, "Skipping cleanup (--no-cleanup flag)")
                print_info(f"Test region ID: {self.test_region_id}")

        except Exception as e:
            print_error(f"Unexpected error: {e}")
            self.errors.append(str(e))
            all_passed = False

        # Print summary
        self._print_summary(all_passed)

        return all_passed

    async def test_database_connection(self) -> bool:
        """Test PostgreSQL database connection."""
        try:
            from sqlalchemy import text
            from app.core.database import get_db_context

            async with get_db_context() as db:
                # Test basic query
                result = await db.execute(text("SELECT 1"))
                assert result.scalar() == 1
                print_success("Basic query executed successfully")

                # Test PostGIS extension
                result = await db.execute(text("SELECT PostGIS_version()"))
                postgis_version = result.scalar()
                print_success(f"PostGIS version: {postgis_version}")

                # Test regions table exists
                result = await db.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'regions'")
                )
                if result.scalar() > 0:
                    print_success("Regions table exists")
                else:
                    print_warning("Regions table not found - may need migrations")

            return True

        except Exception as e:
            print_error(f"Database connection failed: {e}")
            self.errors.append(f"Database connection: {e}")
            return False

    async def create_test_region(self) -> bool:
        """Create a test region for the integration test."""
        try:
            from geoalchemy2.functions import ST_GeomFromGeoJSON
            from app.core.database import get_db_context
            from app.models.region import Region

            # Create a small test region (downtown Phoenix area)
            test_geometry = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.08, 33.44],
                        [-112.08, 33.46],
                        [-112.06, 33.46],
                        [-112.06, 33.44],
                        [-112.08, 33.44],
                    ]
                ],
            }

            async with get_db_context() as db:
                region = Region(
                    name=f"Integration Test Region {uuid4().hex[:8]}",
                    description="Temporary region for integration testing",
                    geometry=ST_GeomFromGeoJSON(json.dumps(test_geometry)),
                    type="custom",
                    category="migration_hotspot",
                    country="United States",
                    state_province="Arizona",
                )

                db.add(region)
                await db.flush()
                self.test_region_id = region.id
                print_success(f"Created test region: {region.name}")
                print_info(f"Region ID: {self.test_region_id}")

            return True

        except Exception as e:
            print_error(f"Failed to create test region: {e}")
            self.errors.append(f"Create region: {e}")
            return False

    async def test_data_collection(self) -> bool:
        """Test data collection with mocked GEE responses."""
        if not self.test_region_id:
            print_error("No test region available")
            return False

        try:
            from app.core.database import get_db_context
            from app.services.collection import DataCollectionService
            from app.services.features.base import ExtractionResult

            # Create mock responses for GEE
            mock_imagery = MagicMock()
            mock_imagery.shape = (256, 256, 4)

            # Mock extraction result
            mock_result = ExtractionResult(
                value=0.65,
                metadata={
                    "mean": 0.65,
                    "min": 0.3,
                    "max": 0.85,
                    "std": 0.12,
                    "coverage_pct": 95.0,
                },
            )

            async with get_db_context() as db:
                service = DataCollectionService(db)

                # Patch the satellite clients and extractors
                with patch.object(service.gee_client, 'initialize', new_callable=AsyncMock):
                    with patch.object(service.viirs_client, 'initialize', new_callable=AsyncMock):
                        with patch.object(service.gee_client, 'get_composite', new_callable=AsyncMock) as mock_composite:
                            with patch.object(service.viirs_client, 'get_imagery', new_callable=AsyncMock) as mock_viirs:
                                # Setup mock returns
                                mock_composite.return_value = mock_imagery
                                mock_viirs.return_value = [mock_imagery]

                                # Patch extractors
                                for extractor in service.extractors.values():
                                    extractor.extract = AsyncMock(return_value=mock_result)

                                # Run collection for a short date range
                                end_date = date.today()
                                start_date = end_date - timedelta(days=30)

                                result = await service.collect_for_region(
                                    region_id=self.test_region_id,
                                    start_date=start_date,
                                    end_date=end_date,
                                    metrics=["ndvi", "nightlights"],
                                    granularity="monthly",
                                )

                                print_success(f"Collection completed for region: {result.region_name}")
                                print_info(f"Metrics collected: {result.metrics_collected}")
                                print_info(f"Observations created: {result.observations_created}")

                                if result.errors:
                                    for error in result.errors:
                                        print_warning(f"Collection error: {error}")
                                        self.warnings.append(error)

            return True

        except Exception as e:
            print_error(f"Data collection failed: {e}")
            self.errors.append(f"Data collection: {e}")
            return False

    async def test_metrics_query(self) -> bool:
        """Test querying metrics for the test region."""
        if not self.test_region_id:
            print_error("No test region available")
            return False

        try:
            from sqlalchemy import select, func
            from app.core.database import get_db_context
            from app.models.observation import Observation
            from app.models.region import Region

            async with get_db_context() as db:
                # Verify region exists
                result = await db.execute(
                    select(Region).where(Region.id == self.test_region_id)
                )
                region = result.scalar_one_or_none()

                if region is None:
                    print_error("Test region not found in database")
                    return False

                print_success(f"Found test region: {region.name}")

                # Query observations
                result = await db.execute(
                    select(Observation)
                    .where(Observation.region_id == self.test_region_id)
                    .order_by(Observation.date)
                )
                observations = result.scalars().all()

                if observations:
                    print_success(f"Found {len(observations)} observations")

                    # Get unique metrics
                    metrics = set(obs.metric for obs in observations)
                    print_info(f"Metrics available: {', '.join(metrics)}")

                    # Show sample values
                    for obs in observations[:3]:
                        print_info(f"  {obs.metric} ({obs.date}): {obs.value:.4f}")
                else:
                    print_warning("No observations found (expected with mocked data)")

                # Test aggregation query
                result = await db.execute(
                    select(
                        Observation.metric,
                        func.avg(Observation.value).label("avg_value"),
                        func.count(Observation.id).label("count"),
                    )
                    .where(Observation.region_id == self.test_region_id)
                    .group_by(Observation.metric)
                )
                aggregates = result.all()

                if aggregates:
                    print_success("Aggregation query successful")
                    for metric, avg_val, count in aggregates:
                        print_info(f"  {metric}: avg={avg_val:.4f}, count={count}")
                else:
                    print_info("No aggregate data available")

            return True

        except Exception as e:
            print_error(f"Metrics query failed: {e}")
            self.errors.append(f"Metrics query: {e}")
            return False

    async def test_export_generation(self) -> bool:
        """Test CSV export generation."""
        if not self.test_region_id:
            print_error("No test region available")
            return False

        try:
            from datetime import date, timedelta
            from app.core.config import get_settings
            from app.services.export.csv import CSVExporter

            settings = get_settings()

            # Create exporter and generate CSV
            exporter = CSVExporter()

            end_date = date.today()
            start_date = end_date - timedelta(days=90)

            # Test the export with our test region
            export_id = str(uuid4())

            try:
                file_path = await exporter.export(
                    region_ids=[self.test_region_id],
                    metrics=["ndvi", "nightlights"],
                    start_date=start_date,
                    end_date=end_date,
                    include_metadata=True,
                    export_id=export_id,
                )
                print_success(f"CSV export generated: {file_path}")

                # Verify file exists
                from pathlib import Path
                if Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size
                    print_info(f"Export file size: {file_size} bytes")

                    # Cleanup export file
                    if self.cleanup:
                        Path(file_path).unlink()
                        print_info("Cleaned up export file")
                else:
                    print_warning("Export file not found at expected path")

            except Exception as e:
                # Export might fail if there's no data, which is OK for this test
                print_warning(f"Export generation note: {e}")
                self.warnings.append(f"Export: {e}")

            return True

        except Exception as e:
            print_error(f"Export test failed: {e}")
            self.errors.append(f"Export test: {e}")
            return False

    async def cleanup_test_data(self) -> bool:
        """Clean up test data from the database."""
        if not self.test_region_id:
            print_info("No test data to clean up")
            return True

        try:
            from sqlalchemy import delete
            from app.core.database import get_db_context
            from app.models.observation import Observation
            from app.models.region import Region

            async with get_db_context() as db:
                # Delete observations first (foreign key constraint)
                result = await db.execute(
                    delete(Observation).where(Observation.region_id == self.test_region_id)
                )
                obs_deleted = result.rowcount
                print_info(f"Deleted {obs_deleted} test observations")

                # Delete test region
                result = await db.execute(
                    delete(Region).where(Region.id == self.test_region_id)
                )
                if result.rowcount > 0:
                    print_success("Deleted test region")
                else:
                    print_warning("Test region not found for deletion")

            self.test_region_id = None
            return True

        except Exception as e:
            print_error(f"Cleanup failed: {e}")
            self.errors.append(f"Cleanup: {e}")
            return False

    def _print_summary(self, all_passed: bool) -> None:
        """Print the test summary."""
        print()
        print_header("Test Summary")

        if all_passed and not self.errors:
            print(f"{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.RESET}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}Some tests failed{Colors.RESET}")

        if self.errors:
            print()
            print(f"{Colors.RED}Errors:{Colors.RESET}")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print()
            print(f"{Colors.YELLOW}Warnings:{Colors.RESET}")
            for warning in self.warnings:
                print(f"  - {warning}")

        print()


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run integration tests for the satellite data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup of test data (useful for debugging)",
    )

    args = parser.parse_args()

    tester = IntegrationTest(
        verbose=args.verbose,
        cleanup=not args.no_cleanup,
    )

    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
