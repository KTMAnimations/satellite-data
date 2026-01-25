#!/usr/bin/env python3
"""
Health Check Script for Satellite Data Platform

This script checks the health status of all system components:
1. PostgreSQL database connection and PostGIS extension
2. Redis connection and basic operations
3. Google Earth Engine authentication (if configured)
4. File system paths and permissions

Usage:
    # From backend directory
    python -m scripts.healthcheck

    # Or directly
    python scripts/healthcheck.py

    # JSON output for automation
    python -m scripts.healthcheck --json

    # Check specific services only
    python -m scripts.healthcheck --check db
    python -m scripts.healthcheck --check redis
    python -m scripts.healthcheck --check gee
    python -m scripts.healthcheck --check filesystem

Requirements:
    - Backend dependencies installed
    - Environment variables configured (or .env file)

Environment Variables:
    DATABASE_URL - PostgreSQL connection string
    REDIS_URL - Redis connection string
    GEE_PROJECT_ID - Google Earth Engine project ID
    GEE_SERVICE_ACCOUNT_KEY - Path to GEE service account JSON
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Add the backend directory to the path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# ANSI color codes
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


@dataclass
class ServiceStatus:
    """Status of a single service."""
    name: str
    status: Literal["healthy", "degraded", "unhealthy", "unconfigured"]
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None


@dataclass
class HealthReport:
    """Overall health report."""
    timestamp: str
    overall_status: Literal["healthy", "degraded", "unhealthy"]
    services: list[ServiceStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "services": [asdict(s) for s in self.services],
        }


class HealthChecker:
    """Health checker for all system components."""

    def __init__(self, output_json: bool = False):
        self.output_json = output_json
        self.report = HealthReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            overall_status="healthy",
        )

    async def check_all(self) -> HealthReport:
        """Run all health checks."""
        await self.check_database()
        await self.check_redis()
        await self.check_gee()
        self.check_filesystem()

        # Determine overall status
        statuses = [s.status for s in self.report.services]
        if "unhealthy" in statuses:
            self.report.overall_status = "unhealthy"
        elif "degraded" in statuses:
            self.report.overall_status = "degraded"
        else:
            self.report.overall_status = "healthy"

        return self.report

    async def check_database(self) -> ServiceStatus:
        """Check PostgreSQL database connection."""
        import time
        start_time = time.time()

        try:
            from sqlalchemy import text
            from app.core.database import get_db_context
            from app.core.config import get_settings

            settings = get_settings()

            async with get_db_context() as db:
                # Basic connectivity test
                result = await db.execute(text("SELECT 1"))
                assert result.scalar() == 1

                # Check PostGIS
                result = await db.execute(text("SELECT PostGIS_version()"))
                postgis_version = result.scalar()

                # Check database version
                result = await db.execute(text("SELECT version()"))
                db_version = result.scalar()

                # Get table counts
                result = await db.execute(text("""
                    SELECT
                        (SELECT COUNT(*) FROM regions) as regions,
                        (SELECT COUNT(*) FROM observations) as observations
                """))
                row = result.one()
                regions_count = row[0]
                observations_count = row[1]

            latency = (time.time() - start_time) * 1000

            status = ServiceStatus(
                name="PostgreSQL",
                status="healthy",
                message="Database connection successful",
                details={
                    "postgis_version": postgis_version,
                    "database_version": db_version.split(",")[0] if db_version else "unknown",
                    "regions_count": regions_count,
                    "observations_count": observations_count,
                    "connection_url": self._mask_url(settings.database_url),
                },
                latency_ms=round(latency, 2),
            )

        except ImportError as e:
            status = ServiceStatus(
                name="PostgreSQL",
                status="unhealthy",
                message=f"Missing dependency: {e}",
                details={"error": str(e)},
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            status = ServiceStatus(
                name="PostgreSQL",
                status="unhealthy",
                message=f"Connection failed: {type(e).__name__}",
                details={"error": str(e)},
                latency_ms=round(latency, 2),
            )

        self.report.services.append(status)
        self._print_status(status)
        return status

    async def check_redis(self) -> ServiceStatus:
        """Check Redis connection."""
        import time
        start_time = time.time()

        try:
            import redis.asyncio as redis
            from app.core.config import get_settings

            settings = get_settings()

            client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # Test basic operations
            test_key = "healthcheck:test"
            test_value = "ok"

            await client.set(test_key, test_value, ex=10)
            result = await client.get(test_key)
            await client.delete(test_key)

            assert result == test_value

            # Get Redis info
            info = await client.info()

            await client.close()

            latency = (time.time() - start_time) * 1000

            status = ServiceStatus(
                name="Redis",
                status="healthy",
                message="Redis connection successful",
                details={
                    "redis_version": info.get("redis_version", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connection_url": self._mask_url(settings.redis_url),
                },
                latency_ms=round(latency, 2),
            )

        except ImportError as e:
            status = ServiceStatus(
                name="Redis",
                status="unhealthy",
                message=f"Missing dependency: {e}",
                details={"error": str(e)},
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            status = ServiceStatus(
                name="Redis",
                status="unhealthy",
                message=f"Connection failed: {type(e).__name__}",
                details={"error": str(e)},
                latency_ms=round(latency, 2),
            )

        self.report.services.append(status)
        self._print_status(status)
        return status

    async def check_gee(self) -> ServiceStatus:
        """Check Google Earth Engine authentication."""
        import time
        start_time = time.time()

        try:
            from app.core.config import get_settings

            settings = get_settings()

            # Check if GEE is configured
            if not settings.gee_project_id:
                status = ServiceStatus(
                    name="Google Earth Engine",
                    status="unconfigured",
                    message="GEE_PROJECT_ID not set",
                    details={
                        "configured": False,
                        "project_id": None,
                        "service_account_key": None,
                    },
                )
                self.report.services.append(status)
                self._print_status(status)
                return status

            # Check if service account key file exists
            key_path = settings.gee_service_account_key
            key_exists = key_path and Path(key_path).exists() if key_path else False

            if not key_exists:
                status = ServiceStatus(
                    name="Google Earth Engine",
                    status="degraded",
                    message="Service account key file not found",
                    details={
                        "configured": True,
                        "project_id": settings.gee_project_id,
                        "service_account_key": key_path,
                        "key_file_exists": False,
                    },
                )
                self.report.services.append(status)
                self._print_status(status)
                return status

            # Try to initialize GEE
            try:
                import ee

                credentials = ee.ServiceAccountCredentials(
                    email=None,  # Will be read from the key file
                    key_file=key_path,
                )
                ee.Initialize(
                    credentials=credentials,
                    project=settings.gee_project_id,
                )

                # Test a simple operation
                image = ee.Image("COPERNICUS/S2_SR/20200101T100319_20200101T100321_T33UUP")
                _ = image.bandNames().getInfo()

                latency = (time.time() - start_time) * 1000

                status = ServiceStatus(
                    name="Google Earth Engine",
                    status="healthy",
                    message="GEE authentication successful",
                    details={
                        "configured": True,
                        "project_id": settings.gee_project_id,
                        "authenticated": True,
                    },
                    latency_ms=round(latency, 2),
                )

            except Exception as e:
                latency = (time.time() - start_time) * 1000
                status = ServiceStatus(
                    name="Google Earth Engine",
                    status="degraded",
                    message=f"Authentication failed: {type(e).__name__}",
                    details={
                        "configured": True,
                        "project_id": settings.gee_project_id,
                        "error": str(e),
                    },
                    latency_ms=round(latency, 2),
                )

        except ImportError as e:
            status = ServiceStatus(
                name="Google Earth Engine",
                status="unhealthy",
                message=f"Missing dependency: {e}",
                details={"error": str(e)},
            )

        except Exception as e:
            status = ServiceStatus(
                name="Google Earth Engine",
                status="unhealthy",
                message=f"Check failed: {type(e).__name__}",
                details={"error": str(e)},
            )

        self.report.services.append(status)
        self._print_status(status)
        return status

    def check_filesystem(self) -> ServiceStatus:
        """Check filesystem paths and permissions."""
        try:
            from app.core.config import get_settings

            settings = get_settings()

            paths_to_check = {
                "data_dir": settings.data_dir,
                "cache_dir": settings.cache_dir,
                "exports_dir": settings.exports_dir,
                "regions_dir": settings.regions_dir,
            }

            path_status = {}
            all_ok = True

            for name, path_str in paths_to_check.items():
                path = Path(path_str)
                exists = path.exists()
                writable = os.access(path_str, os.W_OK) if exists else False

                path_status[name] = {
                    "path": path_str,
                    "exists": exists,
                    "writable": writable,
                }

                if not exists:
                    # Try to create the directory
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        path_status[name]["exists"] = True
                        path_status[name]["writable"] = True
                        path_status[name]["created"] = True
                    except Exception:
                        all_ok = False
                elif not writable:
                    all_ok = False

            if all_ok:
                status = ServiceStatus(
                    name="Filesystem",
                    status="healthy",
                    message="All paths accessible",
                    details={"paths": path_status},
                )
            else:
                status = ServiceStatus(
                    name="Filesystem",
                    status="degraded",
                    message="Some paths not accessible or writable",
                    details={"paths": path_status},
                )

        except Exception as e:
            status = ServiceStatus(
                name="Filesystem",
                status="unhealthy",
                message=f"Check failed: {type(e).__name__}",
                details={"error": str(e)},
            )

        self.report.services.append(status)
        self._print_status(status)
        return status

    def _mask_url(self, url: str) -> str:
        """Mask sensitive parts of a URL."""
        if "@" in url:
            # Mask password in connection string
            parts = url.split("@")
            creds = parts[0].split(":")
            if len(creds) >= 3:
                creds[-1] = "****"
            parts[0] = ":".join(creds)
            return "@".join(parts)
        return url

    def _print_status(self, status: ServiceStatus) -> None:
        """Print status to console unless JSON output is enabled."""
        if self.output_json:
            return

        status_colors = {
            "healthy": Colors.GREEN,
            "degraded": Colors.YELLOW,
            "unhealthy": Colors.RED,
            "unconfigured": Colors.BLUE,
        }

        color = status_colors.get(status.status, Colors.RESET)
        icon = {
            "healthy": "[OK]",
            "degraded": "[WARN]",
            "unhealthy": "[FAIL]",
            "unconfigured": "[SKIP]",
        }.get(status.status, "[?]")

        print(f"{color}{icon}{Colors.RESET} {Colors.BOLD}{status.name}{Colors.RESET}")
        print(f"    Status: {color}{status.status}{Colors.RESET}")
        print(f"    Message: {status.message}")

        if status.latency_ms is not None:
            print(f"    Latency: {status.latency_ms}ms")

        if status.details and not self.output_json:
            for key, value in status.details.items():
                if key != "error":
                    if isinstance(value, dict):
                        print(f"    {key}:")
                        for k, v in value.items():
                            print(f"      {k}: {v}")
                    else:
                        print(f"    {key}: {value}")

        print()

    def print_report(self) -> None:
        """Print the final report."""
        if self.output_json:
            print(json.dumps(self.report.to_dict(), indent=2))
        else:
            print(f"\n{'=' * 60}")
            print(f"{'HEALTH CHECK SUMMARY'.center(60)}")
            print(f"{'=' * 60}")

            status_color = {
                "healthy": Colors.GREEN,
                "degraded": Colors.YELLOW,
                "unhealthy": Colors.RED,
            }.get(self.report.overall_status, Colors.RESET)

            print(f"\nTimestamp: {self.report.timestamp}")
            print(f"Overall Status: {status_color}{Colors.BOLD}{self.report.overall_status.upper()}{Colors.RESET}")

            # Service summary
            print(f"\nServices:")
            for service in self.report.services:
                status_colors = {
                    "healthy": Colors.GREEN,
                    "degraded": Colors.YELLOW,
                    "unhealthy": Colors.RED,
                    "unconfigured": Colors.BLUE,
                }
                color = status_colors.get(service.status, Colors.RESET)
                print(f"  {service.name}: {color}{service.status}{Colors.RESET}")

            print()


async def run_checks(
    output_json: bool = False,
    checks: list[str] | None = None,
) -> int:
    """Run health checks and return exit code."""
    checker = HealthChecker(output_json=output_json)

    if not output_json:
        print(f"\n{'=' * 60}")
        print(f"{'SATELLITE DATA PLATFORM HEALTH CHECK'.center(60)}")
        print(f"{'=' * 60}\n")

    if checks is None or "all" in checks:
        await checker.check_all()
    else:
        if "db" in checks or "database" in checks:
            await checker.check_database()
        if "redis" in checks:
            await checker.check_redis()
        if "gee" in checks:
            await checker.check_gee()
        if "filesystem" in checks or "fs" in checks:
            checker.check_filesystem()

        # Determine overall status
        statuses = [s.status for s in checker.report.services]
        if "unhealthy" in statuses:
            checker.report.overall_status = "unhealthy"
        elif "degraded" in statuses:
            checker.report.overall_status = "degraded"
        else:
            checker.report.overall_status = "healthy"

    checker.print_report()

    # Return appropriate exit code
    if checker.report.overall_status == "unhealthy":
        return 2
    elif checker.report.overall_status == "degraded":
        return 1
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check health status of all system components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--check", "-c",
        action="append",
        choices=["all", "db", "database", "redis", "gee", "filesystem", "fs"],
        help="Specific service(s) to check (can be used multiple times)",
    )

    args = parser.parse_args()

    checks = args.check if args.check else ["all"]

    return asyncio.run(run_checks(
        output_json=args.json,
        checks=checks,
    ))


if __name__ == "__main__":
    sys.exit(main())
