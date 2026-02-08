from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import TelemetryEvent, TelemetryInstance
from app.schemas import (
    TelemetryEventsRequest,
    TelemetryEventsResponse,
    TelemetryRegisterRequest,
    TelemetryRegisterResponse,
)
from app.telemetry import dumps_json, get_request_ip


router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/register", response_model=TelemetryRegisterResponse)
async def register_instance(
    payload: TelemetryRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TelemetryRegisterResponse:
    ip_address = get_request_ip(request)
    now = _utcnow()
    user_agent = request.headers.get("user-agent")
    accept_language = request.headers.get("accept-language")

    result = await db.execute(select(TelemetryInstance).where(TelemetryInstance.id == payload.instance_id))
    instance = result.scalar_one_or_none()

    if instance is None:
        instance = TelemetryInstance(
            id=payload.instance_id,
            device_id=payload.device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            accept_language=accept_language,
            meta_json=dumps_json(payload.meta),
            first_seen_at=now,
            last_seen_at=now,
            last_path=payload.path,
        )
        db.add(instance)
        await db.flush()
    else:
        instance.device_id = payload.device_id or instance.device_id
        instance.ip_address = ip_address or instance.ip_address
        instance.user_agent = user_agent or instance.user_agent
        instance.accept_language = accept_language or instance.accept_language
        if payload.meta:
            instance.meta_json = dumps_json(payload.meta)
        instance.last_seen_at = now
        instance.last_path = payload.path or instance.last_path

    return TelemetryRegisterResponse(
        instance_id=instance.id,
        ip_address=instance.ip_address,
        first_seen_at=instance.first_seen_at,
        last_seen_at=instance.last_seen_at,
    )


@router.post("/events", response_model=TelemetryEventsResponse)
async def ingest_events(
    payload: TelemetryEventsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventsResponse:
    ip_address = get_request_ip(request)
    now = _utcnow()
    user_agent = request.headers.get("user-agent")
    accept_language = request.headers.get("accept-language")

    result = await db.execute(select(TelemetryInstance).where(TelemetryInstance.id == payload.instance_id))
    instance = result.scalar_one_or_none()

    if instance is None:
        instance = TelemetryInstance(
            id=payload.instance_id,
            device_id=payload.device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            accept_language=accept_language,
            meta_json="{}",
            first_seen_at=now,
            last_seen_at=now,
            last_path=payload.events[-1].path if payload.events else None,
        )
        db.add(instance)
        await db.flush()
    else:
        instance.device_id = payload.device_id or instance.device_id
        instance.ip_address = ip_address or instance.ip_address
        instance.user_agent = user_agent or instance.user_agent
        instance.accept_language = accept_language or instance.accept_language
        instance.last_seen_at = now
        last_path = next((e.path for e in reversed(payload.events) if e.path), None)
        if last_path:
            instance.last_path = last_path

    rows: list[TelemetryEvent] = []
    for event in payload.events:
        rows.append(
            TelemetryEvent(
                instance_id=instance.id,
                ip_address=instance.ip_address,
                event_type=event.type,
                client_ts_ms=event.client_ts_ms,
                received_at=now,
                path=event.path,
                data_json=dumps_json(event.data or {}),
            )
        )

    db.add_all(rows)
    await db.flush()

    return TelemetryEventsResponse(inserted=len(rows))

