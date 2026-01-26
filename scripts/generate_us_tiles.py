#!/usr/bin/env python3
"""
Generate pre-computed US tiles for all metrics.

This script fetches satellite data from Google Earth Engine for the entire
continental US and generates map tiles at zoom levels 8-10.

Usage:
    python scripts/generate_us_tiles.py --year 2024 --month 1
    python scripts/generate_us_tiles.py --all  # Generate 2023-2024
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.tiles.us_tile_generator import USTileGenerator, METRICS, ZOOM_LEVELS


async def generate_month(year: int, month: int, metrics: list[str] | None = None, zoom_levels: list[int] | None = None):
    """Generate tiles for a single month."""
    generator = USTileGenerator()
    zooms = zoom_levels or ZOOM_LEVELS

    print(f"\n{'='*60}")
    print(f"Generating US tiles for {year}-{month:02d}")
    print(f"Metrics: {metrics or METRICS}")
    print(f"Zoom levels: {zooms}")
    print(f"{'='*60}\n")

    stats = await generator.generate_month(year, month, metrics, zooms)

    print(f"\nResults for {year}-{month:02d}:")
    print(f"  Generated: {stats['generated']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")

    return stats


async def generate_all(start_year: int = 2023, end_year: int = 2024):
    """Generate tiles for all months in the date range."""
    print(f"\n{'#'*60}")
    print(f"Generating US tiles for {start_year} to {end_year}")
    print(f"{'#'*60}\n")

    total_stats = {"generated": 0, "skipped": 0, "failed": 0}
    months_processed = 0

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # Skip future months in 2024
            if year == 2024 and month > 12:
                continue

            try:
                stats = await generate_month(year, month)
                for key in total_stats:
                    total_stats[key] += stats.get(key, 0)
                months_processed += 1
            except Exception as e:
                print(f"ERROR: Failed to generate {year}-{month:02d}: {e}")

    print(f"\n{'#'*60}")
    print(f"COMPLETE: Processed {months_processed} months")
    print(f"Total generated: {total_stats['generated']}")
    print(f"Total skipped: {total_stats['skipped']}")
    print(f"Total failed: {total_stats['failed']}")
    print(f"{'#'*60}\n")


async def main():
    parser = argparse.ArgumentParser(description="Generate US tiles for satellite metrics")
    parser.add_argument("--year", type=int, help="Year to generate")
    parser.add_argument("--month", type=int, help="Month to generate (1-12)")
    parser.add_argument("--metrics", nargs="+", choices=METRICS, help="Metrics to generate")
    parser.add_argument("--zoom", nargs="+", type=int, help="Zoom levels to generate (e.g., --zoom 11)")
    parser.add_argument("--all", action="store_true", help="Generate all 2023-2024")

    args = parser.parse_args()

    if args.all:
        await generate_all()
    elif args.year and args.month:
        await generate_month(args.year, args.month, args.metrics, args.zoom)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/generate_us_tiles.py --year 2024 --month 1")
        print("  python scripts/generate_us_tiles.py --year 2024 --month 6 --metrics ndvi nightlights")
        print("  python scripts/generate_us_tiles.py --year 2024 --month 1 --zoom 11")
        print("  python scripts/generate_us_tiles.py --all")


if __name__ == "__main__":
    asyncio.run(main())
