#!/usr/bin/env python3
"""
Script to trigger full archive data collection for all predefined regions.

Usage:
    python scripts/collect_archive.py --region "Phoenix, AZ" --start 2020-01-01 --end 2024-12-31
    python scripts/collect_archive.py --all --start 2015-01-01 --end 2024-12-31
"""

import argparse
import asyncio
from datetime import date, timedelta
import httpx

API_BASE = "http://localhost:8000"


async def collect_for_region(
    region_id: str,
    region_name: str,
    start_date: date,
    end_date: date,
    metrics: list[str] | None = None,
):
    """Collect data for a region, chunked by 6 months."""
    if metrics is None:
        metrics = ["nightlights"]  # NDVI needs debugging, use nightlights for now

    async with httpx.AsyncClient(timeout=300.0) as client:
        current = start_date
        total_observations = 0

        while current < end_date:
            # Chunk by 6 months
            chunk_end = min(current + timedelta(days=180), end_date)

            print(f"  Collecting {current} to {chunk_end}...", end=" ", flush=True)

            response = await client.post(
                f"{API_BASE}/api/v1/collect/{region_id}",
                json={
                    "start_date": current.isoformat(),
                    "end_date": chunk_end.isoformat(),
                    "metrics": metrics,
                    "granularity": "monthly",
                }
            )

            if response.status_code == 200:
                data = response.json()
                observations = data.get("observations_created", 0)
                total_observations += observations
                print(f"{observations} observations")
            else:
                print(f"ERROR: {response.status_code}")
                try:
                    print(f"  {response.json()}")
                except:
                    print(f"  {response.text}")

            current = chunk_end + timedelta(days=1)

        return total_observations


async def get_regions(search: str | None = None):
    """Get list of regions from API."""
    async with httpx.AsyncClient() as client:
        params = {"page_size": 100}
        if search:
            params["search"] = search
        response = await client.get(f"{API_BASE}/api/v1/regions", params=params)
        return response.json()["regions"]


async def main():
    parser = argparse.ArgumentParser(description="Collect archive data for regions")
    parser.add_argument("--region", help="Region name to collect (e.g., 'Phoenix, AZ')")
    parser.add_argument("--all", action="store_true", help="Collect for all predefined regions")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--metrics", nargs="+", default=["nightlights"],
                       help="Metrics to collect (default: nightlights)")

    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    print(f"Archive Collection: {start_date} to {end_date}")
    print(f"Metrics: {args.metrics}")
    print("-" * 60)

    if args.region:
        # Collect for specific region
        regions = await get_regions(args.region)
        if not regions:
            print(f"Region '{args.region}' not found")
            return
    elif args.all:
        # Collect for all regions
        regions = await get_regions()
    else:
        print("Please specify --region or --all")
        return

    total = 0
    for region in regions:
        print(f"\n{region['name']} ({region['type']}):")
        observations = await collect_for_region(
            region["id"],
            region["name"],
            start_date,
            end_date,
            args.metrics,
        )
        total += observations

    print("\n" + "=" * 60)
    print(f"Total observations created: {total}")


if __name__ == "__main__":
    asyncio.run(main())
