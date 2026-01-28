from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Region
from app.schemas import (
    MetricId,
    PresetCompare,
    PresetComparePeriod,
    PresetDateRange,
    PresetListResponse,
    PresetRegion,
    PresetResponse,
)


router = APIRouter()


def _project_root() -> Path:
    # backend/app/routes -> repo root
    return Path(__file__).resolve().parents[3]


def _presets_dir() -> Path:
    return _project_root() / "data" / "presets"


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _normalize_regions(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    out.append(name)
            elif isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if name:
                    out.append(name)
        return out
    return []


def _normalize_metrics(raw: Any) -> list[MetricId]:
    if not isinstance(raw, list):
        return []
    out: list[MetricId] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        val = item.strip()
        if not val:
            continue
        # Let Pydantic validate on response; keep only strings here.
        out.append(val)  # type: ignore[arg-type]
    return out


def _extract_compare(payload: dict[str, Any]) -> PresetCompare | None:
    raw = payload.get("compare") or payload.get("comparison")
    if not isinstance(raw, dict):
        return None

    period_a = raw.get("period_a") or raw.get("periodA")
    period_b = raw.get("period_b") or raw.get("periodB")
    if not isinstance(period_a, dict) or not isinstance(period_b, dict):
        return None

    a_start = _parse_date(period_a.get("start_date") or period_a.get("start"))
    a_end = _parse_date(period_a.get("end_date") or period_a.get("end"))
    b_start = _parse_date(period_b.get("start_date") or period_b.get("start"))
    b_end = _parse_date(period_b.get("end_date") or period_b.get("end"))
    if not all([a_start, a_end, b_start, b_end]):
        return None

    return PresetCompare(
        period_a=PresetComparePeriod(
            label=str(period_a.get("name") or period_a.get("label") or "").strip() or None,
            start_date=a_start,
            end_date=a_end,
        ),
        period_b=PresetComparePeriod(
            label=str(period_b.get("name") or period_b.get("label") or "").strip() or None,
            start_date=b_start,
            end_date=b_end,
        ),
    )


def _extract_date_range(payload: dict[str, Any]) -> PresetDateRange | None:
    raw = payload.get("date_range") or payload.get("time_range")
    if isinstance(raw, dict):
        start = _parse_date(raw.get("start_date") or raw.get("start"))
        end = _parse_date(raw.get("end_date") or raw.get("end"))
        if start and end:
            return PresetDateRange(start_date=start, end_date=end)

    # Fall back to compare periods if present.
    compare = _extract_compare(payload)
    if compare:
        start = min(compare.period_a.start_date, compare.period_b.start_date)
        end = max(compare.period_a.end_date, compare.period_b.end_date)
        return PresetDateRange(start_date=start, end_date=end)

    return None


def _load_preset_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


async def _map_region_ids(db: AsyncSession, names: list[str]) -> dict[str, str]:
    if not names:
        return {}
    rows = (
        await db.execute(select(Region.name, Region.id).where(Region.name.in_(names)))
    ).all()
    return {name: region_id for name, region_id in rows}


def _preset_from_payload(payload: dict[str, Any], region_id_by_name: dict[str, str]) -> PresetResponse | None:
    preset_id = str(payload.get("id", "")).strip()
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not preset_id or not name or not description:
        return None

    region_names = _normalize_regions(payload.get("regions"))
    metrics = _normalize_metrics(payload.get("metrics"))

    return PresetResponse(
        id=preset_id,
        name=name,
        description=description,
        category=(str(payload.get("category")).strip() if payload.get("category") else None),
        regions=[PresetRegion(name=r, region_id=region_id_by_name.get(r)) for r in region_names],
        metrics=metrics,
        date_range=_extract_date_range(payload),
        compare=_extract_compare(payload),
        methodology_notes=(str(payload.get("methodology_notes")).strip() if payload.get("methodology_notes") else None),
    )


@router.get("", response_model=PresetListResponse)
async def list_presets(db: AsyncSession = Depends(get_db)) -> PresetListResponse:
    presets_dir = _presets_dir()
    if not presets_dir.exists():
        return PresetListResponse(presets=[])

    payloads: list[dict[str, Any]] = []
    for path in sorted(presets_dir.glob("*.json")):
        payload = _load_preset_file(path)
        if payload:
            payloads.append(payload)

    all_region_names: list[str] = []
    for p in payloads:
        all_region_names.extend(_normalize_regions(p.get("regions")))

    region_id_by_name = await _map_region_ids(db, sorted(set(all_region_names)))

    presets: list[PresetResponse] = []
    for payload in payloads:
        preset = _preset_from_payload(payload, region_id_by_name)
        if preset:
            presets.append(preset)

    return PresetListResponse(presets=presets)


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(preset_id: str, db: AsyncSession = Depends(get_db)) -> PresetResponse:
    presets_dir = _presets_dir()
    path = presets_dir / f"{preset_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preset not found")

    payload = _load_preset_file(path)
    if not payload:
        raise HTTPException(status_code=500, detail="Preset file invalid")

    region_names = _normalize_regions(payload.get("regions"))
    region_id_by_name = await _map_region_ids(db, region_names)
    preset = _preset_from_payload(payload, region_id_by_name)
    if not preset:
        raise HTTPException(status_code=500, detail="Preset file missing required fields")
    return preset

