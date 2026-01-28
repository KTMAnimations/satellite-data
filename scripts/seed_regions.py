#!/usr/bin/env python3
"""
Seed the local SQLite database with predefined regions.

Usage:
  python scripts/seed_regions.py

This reads `backend/data/predefined_regions.json` and inserts any missing
predefined regions into the backend database.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"


def _bounds_to_polygon(bounds: dict) -> dict:
    min_lat = float(bounds["minLat"])
    max_lat = float(bounds["maxLat"])
    min_lon = float(bounds["minLon"])
    max_lon = float(bounds["maxLon"])

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _normalize_category(raw: str | None) -> str | None:
    if not raw:
        return None
    mapping = {
        "Migration Hotspots": "migration_hotspot",
        "Major Cities": "major_city",
        "Megacities": "megacity",
    }
    return mapping.get(raw, raw.strip().lower().replace(" ", "_"))

def _display_name(name: str, country: str | None) -> str:
    """
    Keep US-style names like "Phoenix, AZ" as-is, but append the country for
    global cities like "Tokyo" -> "Tokyo, Japan".
    """
    if "," in name or not country:
        return name

    country_display = {"United Kingdom": "UK", "United States": "USA"}.get(country, country)
    return f"{name}, {country_display}"


async def main() -> None:
    sys.path.insert(0, str(BACKEND_DIR))

    from sqlalchemy import select

    from app.db import async_session_factory, close_db, init_db
    from app.models import Region

    regions_path = BACKEND_DIR / "data" / "predefined_regions.json"
    with open(regions_path, encoding="utf-8") as f:
        payload = json.load(f)

    regions = payload.get("regions", [])
    if not isinstance(regions, list) or not regions:
        raise RuntimeError("No regions found in predefined_regions.json")

    await init_db()

    inserted = 0
    async with async_session_factory() as db:
        existing = set(
            (await db.execute(select(Region.name).where(Region.type == "predefined"))).scalars().all()
        )

        for r in regions:
            name_raw = str(r.get("name", "")).strip()
            if not name_raw:
                continue
            country = (str(r.get("country")).strip() if r.get("country") else None)
            name = _display_name(name_raw, country)
            if name in existing:
                continue

            bounds = r.get("bounds") or {}
            if not isinstance(bounds, dict):
                continue
            geometry = _bounds_to_polygon(bounds)

            region = Region(
                name=name,
                description=(str(r.get("description")).strip() if r.get("description") else None),
                geometry=json.dumps(geometry),
                type="predefined",
                country=country,
                state_province=(str(r.get("state_province")).strip() if r.get("state_province") else None),
                category=_normalize_category(r.get("category")),
            )
            db.add(region)
            inserted += 1

        await db.commit()

    await close_db()
    print(f"Seed complete. Inserted {inserted} region(s).")


if __name__ == "__main__":
    asyncio.run(main())
