#!/usr/bin/env python3
"""
Collect data for preset regions that still need data.
Sequential, one region at a time to avoid overwhelming the server.
"""

import asyncio
import httpx
import sys

API_BASE = "http://localhost:8000/api/v1"
METRICS = ["ndvi", "nightlights", "urban_density", "parking"]
TARGET_OBS = 80  # Minimum observations needed


async def get_regions_status():
    """Get all preset regions and their observation counts."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/regions", params={"type": "predefined", "page_size": 50})
        if resp.status_code != 200:
            print(f"Error fetching regions: {resp.status_code}")
            return []

        data = resp.json()
        regions = data.get("regions", [])

        result = []
        for r in regions:
            obs_count = r.get("observation_count", 0)
            result.append({
                "id": r["id"],
                "name": r["name"],
                "obs_count": obs_count,
                "needs_data": obs_count < TARGET_OBS
            })

        return sorted(result, key=lambda x: x["obs_count"])


async def collect_region(region_id: str, name: str, current_obs: int):
    """Collect data for a single region in small chunks."""
    print(f"\n{'='*50}")
    print(f"Collecting: {name} (currently {current_obs} obs)")
    print(f"{'='*50}", flush=True)

    # Smaller date chunks for reliability
    date_ranges = [
        ("2023-01-01", "2023-03-31"),
        ("2023-04-01", "2023-06-30"),
        ("2023-07-01", "2023-09-30"),
        ("2023-10-01", "2023-12-31"),
        ("2024-01-01", "2024-03-31"),
        ("2024-04-01", "2024-06-30"),
        ("2024-07-01", "2024-09-30"),
        ("2024-10-01", "2024-12-31"),
    ]

    total_new = 0
    async with httpx.AsyncClient(timeout=300) as client:
        for start, end in date_ranges:
            try:
                print(f"  Collecting {start} to {end}...", end=" ", flush=True)
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
                    total_new += obs
                    print(f"+{obs} observations", flush=True)
                elif resp.status_code == 202:
                    # Background task started
                    task_id = resp.json().get("task_id", "unknown")
                    print(f"Background task: {task_id[:8]}...", flush=True)
                    # Wait a bit for background task
                    await asyncio.sleep(30)
                else:
                    print(f"Error: {resp.status_code}", flush=True)

            except httpx.TimeoutException:
                print("Timeout (continuing...)", flush=True)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Exception: {str(e)[:40]}", flush=True)
                await asyncio.sleep(5)

    print(f"\n  Total new for {name}: {total_new}", flush=True)
    return total_new


async def main():
    print("="*60)
    print("Preset Region Data Collection (Remaining Regions)")
    print("="*60, flush=True)

    # Get current status
    print("\nChecking region status...", flush=True)
    regions = await get_regions_status()

    need_data = [r for r in regions if r["needs_data"]]
    have_data = [r for r in regions if not r["needs_data"]]

    print(f"\nRegions with sufficient data ({len(have_data)}):")
    for r in have_data:
        print(f"  ✓ {r['name']}: {r['obs_count']} obs")

    print(f"\nRegions needing data ({len(need_data)}):")
    for r in need_data:
        print(f"  ✗ {r['name']}: {r['obs_count']} obs")

    if not need_data:
        print("\nAll regions have sufficient data!")
        return

    print(f"\nStarting collection for {len(need_data)} regions...", flush=True)

    total_collected = 0
    for i, r in enumerate(need_data):
        print(f"\n[{i+1}/{len(need_data)}] ", end="", flush=True)
        try:
            obs = await collect_region(r["id"], r["name"], r["obs_count"])
            total_collected += obs
        except Exception as e:
            print(f"Failed to collect for {r['name']}: {e}", flush=True)

    print(f"\n{'='*60}")
    print(f"Collection complete! Total new observations: {total_collected}")
    print("="*60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
