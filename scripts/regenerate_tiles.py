#!/usr/bin/env python3
"""
Regenerate US tiles with fixed chunk blending.

Run with: docker exec -it satellite-api python scripts/regenerate_tiles.py

Options:
  --metric METRIC  Specific metric to regenerate (default: all)
  --month YYYY-MM  Specific month to regenerate (default: 2024-01)
  --force          Force regeneration even if tiles exist
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tiles.us_tile_generator import USTileGenerator


# All available metrics
ALL_METRICS = [
    "nightlights",
    "ndvi",
    "urban_density",
    "parking",
    "land_cover",
    "surface_water",
    "active_fire",
    "no2",
    "temperature",
    "precipitation",
    "aerosol",
    "cropland",
    "evapotranspiration",
    "soil_moisture",
    "impervious",
    "fire_historical",
    "canopy_height",
]


async def main():
    """Regenerate tiles with the chunk blending fix."""
    parser = argparse.ArgumentParser(description="Regenerate US tiles with fixed chunk blending")
    parser.add_argument("--metric", type=str, help="Specific metric to regenerate (default: all)")
    parser.add_argument("--month", type=str, default="2024-01", help="Month to regenerate (YYYY-MM)")
    parser.add_argument("--force", action="store_true", help="Force regeneration")
    args = parser.parse_args()

    # Parse month
    try:
        year, month = map(int, args.month.split("-"))
    except ValueError:
        print(f"Invalid month format: {args.month}. Use YYYY-MM")
        return

    # Determine metrics to regenerate
    if args.metric:
        if args.metric not in ALL_METRICS:
            print(f"Unknown metric: {args.metric}")
            print(f"Available metrics: {', '.join(ALL_METRICS)}")
            return
        metrics = [args.metric]
    else:
        metrics = ALL_METRICS

    print(f"Starting tile regeneration with chunk blending fix...")
    print(f"  Month: {year}-{month:02d}")
    print(f"  Metrics: {', '.join(metrics)}")
    print(f"  Force: {args.force}")

    generator = USTileGenerator()

    # Clear existing tiles if force
    if args.force:
        import shutil
        for metric in metrics:
            tiles_path = generator.tiles_dir / metric / f"{year}-{month:02d}"
            if tiles_path.exists():
                print(f"Removing old tiles at {tiles_path}")
                shutil.rmtree(tiles_path)

    # Regenerate tiles
    print(f"Generating tiles at zoom level 11...")
    stats = await generator.generate_month(
        year=year,
        month=month,
        metrics=metrics,
        zoom_levels=[11],
        force=args.force,
    )

    print(f"Tile generation complete: {stats}")
    return stats


if __name__ == "__main__":
    asyncio.run(main())
