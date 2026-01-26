#!/usr/bin/env python3
"""
Collect data for all preset regions that need it.
Simpler script that processes one region at a time with good error handling.
"""

import asyncio
import sys
import httpx

API_BASE = "http://localhost:8000/api/v1"
METRICS = ["ndvi", "nightlights", "urban_density", "parking"]


async def get_regions_needing_data():
    """Get preset regions with less than 80 observations."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/regions", params={"type": "predefined", "page_size": 50})
        regions = resp.json()["regions"]

        needs_data = []
        for region in regions:
            # Check observation count via metrics endpoint
            try:
                metrics_resp = await client.get(
                    f"{API_BASE}/metrics/{region['id']}",
                    params={"start_date": "2023-01-01", "end_date": "2024-12-31", "granularity": "monthly"}
                )
                if metrics_resp.status_code == 200:
                    data = metrics_resp.json()
                    count = sum(len(m.get("data", [])) for m in data.get("metrics", {}).values())
                    if count < 80:
                        needs_data.append((region, count))
                        print(f"  {region['name']}: {count} observations (needs collection)", flush=True)
                    else:
                        print(f"  {region['name']}: {count} observations (OK)", flush=True)
            except Exception as e:
                needs_data.append((region, 0))
                print(f"  {region['name']}: error checking - {e}", flush=True)

        return needs_data


async def collect_for_region(region_id: str, region_name: str):
    """Collect data for a single region in 6-month chunks."""
    print(f"\nCollecting for {region_name}...", flush=True)

    date_ranges = [
        ("2023-01-01", "2023-06-30"),
        ("2023-07-01", "2023-12-31"),
        ("2024-01-01", "2024-06-30"),
        ("2024-07-01", "2024-12-31"),
    ]

    total_obs = 0
    async with httpx.AsyncClient(timeout=600) as client:
        for start, end in date_ranges:
            try:
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
                    obs = result.get("observations_created", 0)
                    total_obs += obs
                    print(f"  {start} to {end}: {obs} observations", flush=True)
                else:
                    print(f"  {start} to {end}: Error {resp.status_code}", flush=True)
            except Exception as e:
                print(f"  {start} to {end}: Exception - {str(e)[:50]}", flush=True)

    print(f"  Total for {region_name}: {total_obs} observations", flush=True)
    return total_obs


async def main():
    print("=" * 60, flush=True)
    print("Preset Region Data Collection", flush=True)
    print("=" * 60, flush=True)

    print("\nChecking regions...", flush=True)
    regions_to_collect = await get_regions_needing_data()

    print(f"\n{len(regions_to_collect)} regions need data collection", flush=True)

    total_collected = 0
    for region, current_count in regions_to_collect:
        obs = await collect_for_region(region["id"], region["name"])
        total_collected += obs

    print(f"\n{'=' * 60}", flush=True)
    print(f"Done! Total observations collected: {total_collected}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
