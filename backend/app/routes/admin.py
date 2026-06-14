from __future__ import annotations

import json
import os
import tempfile

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.gee import initialize_ee, reinitialize_ee
from app.ip_geolocation import resolve_ip_details, resolve_ip_details_map
from app.models import TelemetryEvent, TelemetryInstance
from app.schemas import (
    AdminIpDetail,
    AdminInstanceDetailResponse,
    AdminInstanceEventsResponse,
    AdminInstanceSummary,
    AdminIpDetailResponse,
    AdminIpListResponse,
    AdminIpSummary,
    GeeKeyStatusResponse,
    GeeKeyUpdateRequest,
)
from app.settings import get_settings
from app.telemetry import loads_json


router = APIRouter()
settings = get_settings()


def _admin_auth_or_403(request: Request) -> None:
    """
    Admin endpoints are sensitive.

    - In development: allow without a token.
    - In production: require ADMIN_TOKEN via Authorization: Bearer <token> (or X-Admin-Token).
    """

    if settings.environment == "development":
        return

    token = (getattr(settings, "admin_token", None) or "").strip()
    if not token:
        raise HTTPException(status_code=403, detail="Admin is disabled. Set ADMIN_TOKEN to enable.")

    auth = (request.headers.get("authorization") or "").strip()
    provided = ""
    if auth.lower().startswith("bearer "):
        provided = auth[7:].strip()
    if not provided:
        provided = (request.headers.get("x-admin-token") or "").strip()

    if provided != token:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def require_admin(request: Request) -> None:
    _admin_auth_or_403(request)


def _gee_key_status() -> GeeKeyStatusResponse:
    """Build the non-secret status of the stored Earth Engine key."""
    settings = get_settings()
    key_path = settings.gee_key_path
    configured = key_path.exists()

    project_id = settings.gee_project_id
    client_email: str | None = None
    private_key_id: str | None = None
    if configured:
        try:
            data = json.loads(key_path.read_text(encoding="utf-8"))
            client_email = data.get("client_email")
            private_key_id = data.get("private_key_id")
            project_id = project_id or data.get("project_id")
        except Exception:
            pass

    initialized = False
    error: str | None = None
    try:
        initialize_ee()
        initialized = True
    except Exception as e:  # noqa: BLE001 — surface any init failure to the admin
        error = str(e)

    return GeeKeyStatusResponse(
        configured=configured,
        project_id=project_id,
        client_email=client_email,
        private_key_id=private_key_id,
        key_path=str(key_path),
        initialized=initialized,
        error=error,
    )


@router.get(
    "/credentials/gee",
    response_model=GeeKeyStatusResponse,
    dependencies=[Depends(require_admin)],
)
async def get_gee_key_status() -> GeeKeyStatusResponse:
    return _gee_key_status()


@router.post(
    "/credentials/gee",
    response_model=GeeKeyStatusResponse,
    dependencies=[Depends(require_admin)],
)
async def update_gee_key(payload: GeeKeyUpdateRequest = Body(...)) -> GeeKeyStatusResponse:
    """
    Store a new Earth Engine service-account key on the server and apply it
    immediately. The secret is written to disk (owner-only, off git) and is
    NEVER returned in the response — only safe identifiers are echoed back.
    """
    settings = get_settings()

    # Validate before touching disk.
    try:
        data = json.loads(payload.key_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Key must be a JSON object.")
    if data.get("type") != "service_account":
        raise HTTPException(
            status_code=400,
            detail='Not a service-account key (expected "type": "service_account").',
        )
    for field in ("private_key", "client_email"):
        if not data.get(field):
            raise HTTPException(status_code=400, detail=f"Key is missing required field: {field}")

    key_path = settings.gee_key_path
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write with owner-only permissions.
    fd, tmp = tempfile.mkstemp(dir=str(key_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, key_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    # Apply without a restart; if EE rejects it, the key is still saved and the
    # error is reported in the status.
    try:
        reinitialize_ee()
    except Exception as e:  # noqa: BLE001
        status = _gee_key_status()
        status.error = str(e)
        return status

    return _gee_key_status()


@router.get("/ips", response_model=AdminIpListResponse, dependencies=[Depends(require_admin)])
async def list_ips(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> AdminIpListResponse:
    total = int(
        (await db.scalar(select(func.count(func.distinct(TelemetryInstance.ip_address))))) or 0
    )

    event_counts = (
        select(
            TelemetryEvent.ip_address.label("ip_address"),
            func.count(TelemetryEvent.id).label("event_count"),
        )
        .group_by(TelemetryEvent.ip_address)
        .subquery()
    )

    query = (
        select(
            TelemetryInstance.ip_address.label("ip_address"),
            func.min(TelemetryInstance.first_seen_at).label("first_seen_at"),
            func.max(TelemetryInstance.last_seen_at).label("last_seen_at"),
            func.count(TelemetryInstance.id).label("instance_count"),
            func.coalesce(event_counts.c.event_count, 0).label("event_count"),
        )
        .outerjoin(event_counts, event_counts.c.ip_address == TelemetryInstance.ip_address)
        .group_by(TelemetryInstance.ip_address, event_counts.c.event_count)
        .order_by(func.max(TelemetryInstance.last_seen_at).desc())
        .offset(offset)
        .limit(limit)
    )

    rows = (await db.execute(query)).all()
    details_by_ip = await resolve_ip_details_map([row.ip_address for row in rows])

    ips = []
    for row in rows:
        details = details_by_ip.get(row.ip_address)
        ips.append(
            AdminIpSummary(
                ip_address=row.ip_address,
                location=details.location if details else None,
                is_residential=details.is_residential if details else None,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                instance_count=int(row.instance_count or 0),
                event_count=int(row.event_count or 0),
            )
        )

    return AdminIpListResponse(ips=ips, total=total)


@router.get("/ips/{ip_address}", response_model=AdminIpDetailResponse, dependencies=[Depends(require_admin)])
async def get_ip_detail(ip_address: str, db: AsyncSession = Depends(get_db)) -> AdminIpDetailResponse:
    instance_count = int(
        (await db.scalar(select(func.count()).select_from(TelemetryInstance).where(TelemetryInstance.ip_address == ip_address)))
        or 0
    )
    if instance_count == 0:
        raise HTTPException(status_code=404, detail="IP not found")

    first_seen_at = await db.scalar(
        select(func.min(TelemetryInstance.first_seen_at)).where(TelemetryInstance.ip_address == ip_address)
    )
    last_seen_at = await db.scalar(
        select(func.max(TelemetryInstance.last_seen_at)).where(TelemetryInstance.ip_address == ip_address)
    )
    event_count = int(
        (await db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.ip_address == ip_address)))
        or 0
    )

    counts_by_instance = (
        select(
            TelemetryEvent.instance_id.label("instance_id"),
            func.count(TelemetryEvent.id).label("event_count"),
        )
        .where(TelemetryEvent.ip_address == ip_address)
        .group_by(TelemetryEvent.instance_id)
        .subquery()
    )

    query = (
        select(
            TelemetryInstance.id.label("instance_id"),
            TelemetryInstance.device_id,
            TelemetryInstance.user_agent,
            TelemetryInstance.accept_language,
            TelemetryInstance.first_seen_at,
            TelemetryInstance.last_seen_at,
            TelemetryInstance.last_path,
            func.coalesce(counts_by_instance.c.event_count, 0).label("event_count"),
        )
        .where(TelemetryInstance.ip_address == ip_address)
        .outerjoin(counts_by_instance, counts_by_instance.c.instance_id == TelemetryInstance.id)
        .order_by(TelemetryInstance.last_seen_at.desc())
    )
    rows = (await db.execute(query)).all()

    instances = [
        AdminInstanceSummary(
            instance_id=row.instance_id,
            device_id=row.device_id,
            user_agent=row.user_agent,
            accept_language=row.accept_language,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            last_path=row.last_path,
            event_count=int(row.event_count or 0),
        )
        for row in rows
    ]

    details = await resolve_ip_details(ip_address)

    ip = AdminIpDetail(
        ip_address=ip_address,
        location=details.location,
        is_residential=details.is_residential,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        instance_count=instance_count,
        event_count=event_count,
        continent=details.continent,
        country=details.country,
        region=details.region,
        city=details.city,
        latitude=details.latitude,
        longitude=details.longitude,
        timezone=details.timezone,
        isp=details.isp,
        organization=details.organization,
        asn=details.asn,
        domain=details.domain,
        network_type=details.network_type,
    )

    return AdminIpDetailResponse(ip=ip, instances=instances)


@router.get(
    "/instances/{instance_id}",
    response_model=AdminInstanceDetailResponse,
    dependencies=[Depends(require_admin)],
)
async def get_instance_detail(instance_id: str, db: AsyncSession = Depends(get_db)) -> AdminInstanceDetailResponse:
    result = await db.execute(select(TelemetryInstance).where(TelemetryInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="Instance not found")

    total_events = int(
        (await db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.instance_id == instance_id)))
        or 0
    )
    distinct_paths = int(
        (
            await db.scalar(
                select(func.count(func.distinct(TelemetryEvent.path)))
                .select_from(TelemetryEvent)
                .where(TelemetryEvent.instance_id == instance_id)
                .where(TelemetryEvent.path.is_not(None))
            )
        )
        or 0
    )

    counts = await db.execute(
        select(TelemetryEvent.event_type, func.count(TelemetryEvent.id))
        .where(TelemetryEvent.instance_id == instance_id)
        .group_by(TelemetryEvent.event_type)
        .order_by(func.count(TelemetryEvent.id).desc())
    )
    event_type_counts = {row[0]: int(row[1] or 0) for row in counts.all()}

    return AdminInstanceDetailResponse(
        instance_id=instance.id,
        device_id=instance.device_id,
        ip_address=instance.ip_address,
        user_agent=instance.user_agent,
        accept_language=instance.accept_language,
        meta=loads_json(instance.meta_json),
        first_seen_at=instance.first_seen_at,
        last_seen_at=instance.last_seen_at,
        last_path=instance.last_path,
        total_events=total_events,
        event_type_counts=event_type_counts,
        distinct_paths=distinct_paths,
    )


@router.get(
    "/instances/{instance_id}/events",
    response_model=AdminInstanceEventsResponse,
    dependencies=[Depends(require_admin)],
)
async def list_instance_events(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> AdminInstanceEventsResponse:
    exists = await db.scalar(select(func.count()).select_from(TelemetryInstance).where(TelemetryInstance.id == instance_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Instance not found")

    total = int(
        (await db.scalar(select(func.count()).select_from(TelemetryEvent).where(TelemetryEvent.instance_id == instance_id)))
        or 0
    )

    query = (
        select(TelemetryEvent)
        .where(TelemetryEvent.instance_id == instance_id)
        .order_by(TelemetryEvent.id.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()

    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "client_ts_ms": e.client_ts_ms,
            "received_at": e.received_at,
            "path": e.path,
            "data": loads_json(e.data_json) or None,
        }
        for e in rows
    ]

    return AdminInstanceEventsResponse(
        instance_id=instance_id,
        events=events,  # type: ignore[arg-type]
        total=total,
    )
