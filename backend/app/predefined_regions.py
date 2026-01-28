from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region


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


def _default_seed_path() -> Path:
    # `backend/data/predefined_regions.json` relative to this module.
    # This stays stable regardless of cwd and env configuration.
    return Path(__file__).resolve().parents[1] / "data" / "predefined_regions.json"


async def seed_predefined_regions(
    session: AsyncSession,
    regions_path: Path | None = None,
) -> int:
    """
    Insert missing predefined regions from the curated JSON file.

    This is safe to call multiple times; it checks for existing predefined
    regions by name.
    """

    path = regions_path or _default_seed_path()
    if not path.exists():
        return 0

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    regions = payload.get("regions", [])
    if not isinstance(regions, list) or not regions:
        return 0

    existing = set(
        (await session.execute(select(Region.name).where(Region.type == "predefined")))
        .scalars()
        .all()
    )

    inserted = 0
    for r in regions:
        name_raw = str(r.get("name", "")).strip()
        if not name_raw:
            continue

        country = str(r.get("country")).strip() if r.get("country") else None
        name = _display_name(name_raw, country)
        if name in existing:
            continue

        bounds = r.get("bounds") or {}
        if not isinstance(bounds, dict):
            continue

        try:
            geometry = _bounds_to_polygon(bounds)
        except Exception:
            continue

        region = Region(
            name=name,
            description=(str(r.get("description")).strip() if r.get("description") else None),
            geometry=json.dumps(geometry),
            type="predefined",
            country=country,
            state_province=(str(r.get("state_province")).strip() if r.get("state_province") else None),
            category=_normalize_category(r.get("category")),
        )
        session.add(region)
        inserted += 1

    if inserted:
        await session.flush()

    return inserted
