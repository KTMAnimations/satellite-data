#!/usr/bin/env python3
"""
Fix MVP data completeness (non-duplicate).

What it does:
1) Collects missing monthly observations (2023-01..2024-12) for MVP regions
2) Backfills missing raster GeoTIFFs for existing observations so tiles/animations are real

Designed to be safe to re-run:
- Observation collection skips existing rows (no duplicates)
- Raster backfill only touches rows with raster_path IS NULL

Run inside the API container:
  docker exec -it satellite-api python /app/scripts/fix_mvp_data.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Allow `import app.*` when run from /app/scripts
sys.path.insert(0, str(Path(__file__).parent.parent))


MVP_REGION_NAMES = [
    "Phoenix, AZ",
    "Miami, FL",
    "Las Vegas, NV",
    "New York, NY",
    "Los Angeles, CA",
]

START = date(2023, 1, 1)
END = date(2024, 12, 31)


def month_start_dates(start: date, end: date) -> list[date]:
    dates: list[date] = []
    current = start.replace(day=1)
    end_month = end.replace(day=1)
    while current <= end_month:
        dates.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return dates


def month_end(d: date) -> date:
    if d.month == 12:
        return date(d.year, 12, 31)
    next_month = date(d.year, d.month + 1, 1)
    return next_month - timedelta(days=1)


@dataclass(frozen=True)
class RegionInfo:
    id: str
    name: str
    geojson: dict


async def fetch_mvp_regions() -> dict[str, RegionInfo]:
    """Return mapping of region name -> RegionInfo for MVP regions."""
    from sqlalchemy import select
    from geoalchemy2.functions import ST_AsGeoJSON

    from app.core.database import get_db_context
    from app.models.region import Region

    async with get_db_context() as db:
        result = await db.execute(
            select(Region, ST_AsGeoJSON(Region.geometry).label("geojson")).where(
                Region.name.in_(MVP_REGION_NAMES)
            )
        )
        rows = result.all()

    import json

    regions: dict[str, RegionInfo] = {}
    for region, geojson_str in rows:
        regions[region.name] = RegionInfo(
            id=region.id,
            name=region.name,
            geojson=json.loads(geojson_str) if geojson_str else None,
        )

    missing = [n for n in MVP_REGION_NAMES if n not in regions]
    if missing:
        raise RuntimeError(f"Missing expected MVP regions in DB: {missing}")

    return regions


async def get_monthly_counts(region_id: str, start: date, end: date) -> dict[str, set[date]]:
    """Return metric -> set(month_start_date) for monthly observations within [start,end]."""
    from sqlalchemy import select

    from app.core.database import get_db_context
    from app.models.observation import Observation

    async with get_db_context() as db:
        result = await db.execute(
            select(Observation.metric, Observation.date)
            .where(Observation.region_id == region_id)
            .where(Observation.date >= start)
            .where(Observation.date <= end)
        )
        rows = result.all()

    by_metric: dict[str, set[date]] = {}
    for metric, obs_date in rows:
        by_metric.setdefault(metric, set()).add(obs_date)
    return by_metric


async def collect_missing_observations(regions: dict[str, RegionInfo]) -> None:
    """
    Fill missing monthly observations for Miami + Las Vegas (no duplicates).
    """
    from app.core.database import get_db_context
    from app.services.collection import DataCollectionService

    expected_months = set(month_start_dates(START, END))

    targets = {
        "Miami, FL": ["ndvi", "urban_density", "parking"],
        "Las Vegas, NV": ["ndvi", "urban_density", "parking"],
    }

    async with get_db_context() as db:
        service = DataCollectionService(db)

        for region_name, metrics in targets.items():
            region = regions[region_name]
            counts = await get_monthly_counts(region.id, START, END)

            missing_any = False
            for metric in metrics:
                have = counts.get(metric, set())
                missing = expected_months - have
                if missing:
                    missing_any = True
                    print(f"[collect] {region_name} {metric}: missing {len(missing)} months")

            if not missing_any:
                print(f"[collect] {region_name}: nothing missing for {metrics}")
                continue

            print(f"[collect] Running collection for {region_name} metrics={metrics} ({START}..{END})")
            result = await service.collect_for_region(
                region_id=region.id,
                start_date=START,
                end_date=END,
                metrics=metrics,  # type: ignore[arg-type]
                granularity="monthly",
            )
            print(
                f"[collect] {region_name}: created={result.observations_created} errors={len(result.errors)}"
            )
            for err in result.errors:
                print(f"  - {err}")


async def backfill_missing_rasters(regions: dict[str, RegionInfo]) -> None:
    """
    Backfill raster GeoTIFFs for existing observations where raster_path is NULL.
    Only targets MVP-critical metrics for MVP regions.
    """
    from sqlalchemy import select
    from geoalchemy2.functions import ST_AsGeoJSON
    from shapely.geometry import shape as shapely_shape

    from app.core.database import get_db_context
    from app.models.observation import Observation
    from app.models.region import Region
    from app.services.collection.raster_storage import save_raster
    from app.services.features.ndvi import NDVIExtractor
    from app.services.features.nightlights import NightlightsExtractor
    from app.services.satellite.gee_client import GEEClient, VIIRSClient

    region_ids = [
        regions["Phoenix, AZ"].id,
        regions["Miami, FL"].id,
        regions["Las Vegas, NV"].id,
    ]

    metrics = ["ndvi", "nightlights"]

    async with get_db_context() as db:
        # Load region geometries once
        region_rows = await db.execute(
            select(Region.id, Region.name, ST_AsGeoJSON(Region.geometry).label("geojson"))
            .where(Region.id.in_(region_ids))
        )
        region_geo: dict[str, tuple[str, object]] = {}
        import json

        for rid, name, geojson_str in region_rows.all():
            region_geo[rid] = (name, shapely_shape(json.loads(geojson_str)))

        # Query observations missing rasters in the target date range
        obs_result = await db.execute(
            select(Observation)
            .where(Observation.region_id.in_(region_ids))
            .where(Observation.metric.in_(metrics))
            .where(Observation.raster_path.is_(None))
            .where(Observation.date >= START)
            .where(Observation.date <= END)
            .order_by(Observation.region_id, Observation.metric, Observation.date)
        )
        observations = list(obs_result.scalars().all())

        if not observations:
            print("[backfill] No missing rasters to backfill.")
            return

        print(f"[backfill] Need to backfill {len(observations)} rasters (ndvi/nightlights).")

        # Initialize clients once
        gee = GEEClient()
        viirs = VIIRSClient()
        await gee.initialize()
        await viirs.initialize()

        ndvi_extractor = NDVIExtractor()
        night_extractor = NightlightsExtractor()

        updated = 0
        failed = 0

        for i, obs in enumerate(observations, start=1):
            region_name, geom = region_geo[obs.region_id]
            obs_date: date = obs.date
            end_date = month_end(obs_date)

            print(f"[backfill] ({i}/{len(observations)}) {region_name} {obs.metric} {obs_date}...", flush=True)

            try:
                if obs.metric == "ndvi":
                    imagery = await gee.get_composite(
                        geometry=geom,
                        start_date=obs_date,
                        end_date=end_date,
                        bands=["B4", "B8"],
                        max_cloud_cover=20.0,
                        composite_method="median",
                    )
                    if imagery is None:
                        print("  -> no imagery (skip)")
                        failed += 1
                        continue

                    result = await ndvi_extractor.extract(imagery, geom)
                else:  # nightlights
                    imagery_list = await viirs.get_imagery(
                        geometry=geom,
                        start_date=obs_date,
                        end_date=end_date,
                    )
                    if not imagery_list:
                        print("  -> no VIIRS imagery (skip)")
                        failed += 1
                        continue

                    # Prefer the image matching the month, otherwise first
                    imagery = max(imagery_list, key=lambda im: im.date)
                    result = await night_extractor.extract(imagery, geom)

                if result.raster is None or result.bounds is None:
                    print("  -> missing raster/bounds (skip)")
                    failed += 1
                    continue

                raster_path = save_raster(
                    raster=result.raster,
                    bounds=result.bounds,
                    region_id=obs.region_id,
                    metric=obs.metric,
                    obs_date=obs_date,
                )
                if not raster_path:
                    print("  -> save_raster failed (skip)")
                    failed += 1
                    continue

                obs.raster_path = raster_path
                # Keep existing value/extra_data to avoid changing time series; only fill raster_path.
                updated += 1

                if updated % 10 == 0:
                    await db.commit()

            except Exception as e:
                print(f"  -> ERROR: {e}")
                failed += 1

        await db.commit()
        print(f"[backfill] Done. updated={updated} failed={failed}")


async def verify(regions: dict[str, RegionInfo]) -> None:
    """Print a quick verification summary for MVP regions."""
    from sqlalchemy import select, func

    from app.core.database import get_db_context
    from app.models.observation import Observation

    region_ids = [r.id for r in regions.values()]

    async with get_db_context() as db:
        # Metric counts + raster coverage for MVP key metrics
        result = await db.execute(
            select(
                Observation.region_id,
                Observation.metric,
                func.count().label("total"),
                func.count(Observation.raster_path).label("with_raster"),
            )
            .where(Observation.region_id.in_(region_ids))
            .where(Observation.date >= START)
            .where(Observation.date <= END)
            .where(Observation.metric.in_(["ndvi", "nightlights", "urban_density", "parking"]))
            .group_by(Observation.region_id, Observation.metric)
            .order_by(Observation.region_id, Observation.metric)
        )
        rows = result.all()

    id_to_name = {r.id: r.name for r in regions.values()}

    print("\n[verify] MVP region coverage (2023-01..2024-12):")
    for region_id, metric, total, with_raster in rows:
        print(f"  - {id_to_name.get(region_id, region_id)} {metric}: {total} obs, {with_raster} with_raster")


async def main() -> None:
    regions = await fetch_mvp_regions()

    print("[info] MVP regions:")
    for name in MVP_REGION_NAMES:
        print(f"  - {name}: {regions[name].id}")

    await collect_missing_observations(regions)
    await backfill_missing_rasters(regions)
    await verify(regions)


if __name__ == "__main__":
    asyncio.run(main())
