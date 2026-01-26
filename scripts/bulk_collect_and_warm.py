#!/usr/bin/env python3
"""
Bulk Data Collection and Tile Warming Script

Collects satellite data for all preset regions and pre-generates tiles for fast loading.
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import httpx

# Configuration
API_BASE = "http://localhost:8000/api/v1"
START_DATE = "2023-01-01"
END_DATE = "2024-12-31"
METRICS = ["ndvi", "nightlights", "urban_density", "parking"]

# Tile pre-warming config
ZOOM_LEVELS = [10, 11, 12]  # Zoom levels to pre-warm


async def get_preset_regions() -> list[dict]:
    """Fetch all predefined regions."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/regions", params={"type": "predefined", "page_size": 50})
        resp.raise_for_status()
        return resp.json()["regions"]


async def get_region_observation_count(region_id: str) -> int:
    """Check how many observations a region has."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{API_BASE}/metrics/{region_id}",
                params={
                    "start_date": START_DATE,
                    "end_date": END_DATE,
                    "granularity": "monthly"
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                # Count total data points across all metrics
                count = 0
                for metric_data in data.get("metrics", {}).values():
                    count += len(metric_data.get("data", []))
                return count
        except Exception:
            pass
    return 0


async def collect_data_for_region(region_id: str, region_name: str) -> dict:
    """Collect data for a single region."""
    print(f"  Collecting data for {region_name}...")

    async with httpx.AsyncClient(timeout=600) as client:  # 10 minute timeout
        try:
            # Collect 6 months at a time due to API limit
            results = []
            date_ranges = [
                ("2023-01-01", "2023-06-30"),
                ("2023-07-01", "2023-12-31"),
                ("2024-01-01", "2024-06-30"),
                ("2024-07-01", "2024-12-31"),
            ]

            for start, end in date_ranges:
                resp = await client.post(
                    f"{API_BASE}/collect/{region_id}",
                    json={
                        "start_date": start,
                        "end_date": end,
                        "metrics": METRICS,
                        "granularity": "monthly"
                    }
                )
                if resp.status_code == 200:
                    result = resp.json()
                    results.append(result)
                    print(f"    {start} to {end}: {result.get('observations_created', 0)} observations")
                else:
                    print(f"    {start} to {end}: Error - {resp.status_code}")

            total_obs = sum(r.get("observations_created", 0) for r in results)
            return {
                "region_id": region_id,
                "region_name": region_name,
                "total_observations": total_obs,
                "status": "success"
            }

        except Exception as e:
            print(f"    Error: {str(e)}")
            return {
                "region_id": region_id,
                "region_name": region_name,
                "error": str(e),
                "status": "failed"
            }


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to tile coordinates."""
    import math
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return x, y


async def warm_tiles_for_region(region: dict) -> int:
    """Pre-generate tiles for a region."""
    region_id = region["id"]
    region_name = region["name"]

    # Get region bounds from geometry
    if not region.get("geometry"):
        print(f"  No geometry for {region_name}")
        return 0

    coords = region["geometry"]["coordinates"][0]
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    tiles_warmed = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for zoom in ZOOM_LEVELS:
            # Get tile range
            x_min, y_max = lat_lon_to_tile(max_lat, min_lon, zoom)
            x_max, y_min = lat_lon_to_tile(min_lat, max_lon, zoom)

            # Generate list of tiles
            tiles = []
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    tiles.append((x, y))

            print(f"  Warming {len(tiles)} tiles at zoom {zoom} for {region_name}...")

            for metric in METRICS:
                for x, y in tiles:
                    # Request tile (this generates and caches it)
                    url = f"{API_BASE}/tiles/{region_id}/{metric}/{zoom}/{x}/{y}.png"
                    try:
                        resp = await client.get(url, params={"date": "2024-01-01"})
                        if resp.status_code == 200:
                            tiles_warmed += 1
                    except Exception:
                        pass

    return tiles_warmed


async def main():
    print("=" * 60)
    print("Bulk Data Collection and Tile Warming")
    print("=" * 60)

    # Get all preset regions
    print("\nFetching preset regions...")
    regions = await get_preset_regions()
    print(f"Found {len(regions)} preset regions")

    # Check which regions need data
    print("\nChecking existing data...")
    regions_to_collect = []
    for region in regions:
        count = await get_region_observation_count(region["id"])
        if count < 80:  # Less than 80 observations (24 months * 4 metrics = 96 expected)
            regions_to_collect.append(region)
            print(f"  {region['name']}: {count} observations (needs collection)")
        else:
            print(f"  {region['name']}: {count} observations (OK)")

    # Collect data for regions that need it
    if regions_to_collect:
        print(f"\n{'=' * 60}")
        print(f"Collecting data for {len(regions_to_collect)} regions...")
        print("=" * 60)

        results = []
        for region in regions_to_collect:
            result = await collect_data_for_region(region["id"], region["name"])
            results.append(result)

        # Summary
        successful = [r for r in results if r.get("status") == "success"]
        failed = [r for r in results if r.get("status") == "failed"]
        total_obs = sum(r.get("total_observations", 0) for r in successful)

        print(f"\nCollection complete:")
        print(f"  Successful: {len(successful)} regions")
        print(f"  Failed: {len(failed)} regions")
        print(f"  Total observations: {total_obs}")
    else:
        print("\nAll regions have sufficient data!")

    # Warm tiles for all regions
    print(f"\n{'=' * 60}")
    print("Pre-warming tiles for all regions...")
    print("=" * 60)

    total_tiles = 0
    for region in regions:
        tiles = await warm_tiles_for_region(region)
        total_tiles += tiles

    print(f"\nTile warming complete: {total_tiles} tiles generated")

    print(f"\n{'=' * 60}")
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
