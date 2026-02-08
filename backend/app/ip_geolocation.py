from __future__ import annotations

import asyncio
import ipaddress
import time
from collections.abc import Sequence

import httpx


_LOOKUP_URL_TEMPLATE = "https://ipwho.is/{ip_address}"
_LOOKUP_TIMEOUT = httpx.Timeout(timeout=2.5, connect=1.5)
_LOOKUP_HEADERS = {"User-Agent": "satellite-data-admin/1.0"}
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_SIZE = 20_000
_NON_PUBLIC_IP_LOCATION = "Local / Private Network"
_MISSING = object()
_LOCATION_CACHE: dict[str, tuple[float, str | None]] = {}


def _clean_label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _format_location(payload: dict[str, object]) -> str | None:
    parts: list[str] = []
    for candidate in (
        _clean_label(payload.get("city")),
        _clean_label(payload.get("region")),
        _clean_label(payload.get("country")),
    ):
        if candidate and candidate not in parts:
            parts.append(candidate)
    if not parts:
        return None
    return ", ".join(parts)


def _cache_get(ip_address: str) -> str | None | object:
    cached = _LOCATION_CACHE.get(ip_address)
    if cached is None:
        return _MISSING

    expires_at, value = cached
    if expires_at <= time.monotonic():
        _LOCATION_CACHE.pop(ip_address, None)
        return _MISSING

    return value


def _cache_set(ip_address: str, value: str | None) -> None:
    if len(_LOCATION_CACHE) >= _CACHE_MAX_SIZE:
        _LOCATION_CACHE.clear()
    _LOCATION_CACHE[ip_address] = (time.monotonic() + _CACHE_TTL_SECONDS, value)


def _is_global_ip(ip_address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    return parsed.is_global


async def _fetch_public_ip_location(ip_address: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(_LOOKUP_URL_TEMPLATE.format(ip_address=ip_address))
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False:
        return None

    return _format_location(payload)


async def resolve_ip_location(ip_address: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    normalized = (ip_address or "").strip()
    if not normalized:
        return None

    cached = _cache_get(normalized)
    if cached is not _MISSING:
        return cached if isinstance(cached, str) or cached is None else None

    if not _is_global_ip(normalized):
        try:
            parsed = ipaddress.ip_address(normalized)
        except ValueError:
            _cache_set(normalized, None)
            return None

        if not parsed.is_global:
            _cache_set(normalized, _NON_PUBLIC_IP_LOCATION)
            return _NON_PUBLIC_IP_LOCATION

    if client is not None:
        location = await _fetch_public_ip_location(normalized, client)
        _cache_set(normalized, location)
        return location

    async with httpx.AsyncClient(timeout=_LOOKUP_TIMEOUT, headers=_LOOKUP_HEADERS) as one_off_client:
        location = await _fetch_public_ip_location(normalized, one_off_client)
        _cache_set(normalized, location)
        return location


async def resolve_ip_locations(ip_addresses: Sequence[str]) -> dict[str, str | None]:
    unique_ips: list[str] = []
    seen: set[str] = set()
    for raw in ip_addresses:
        normalized = (raw or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_ips.append(normalized)

    if not unique_ips:
        return {}

    semaphore = asyncio.Semaphore(16)
    async with httpx.AsyncClient(timeout=_LOOKUP_TIMEOUT, headers=_LOOKUP_HEADERS) as client:
        async def _resolve(ip_address: str) -> tuple[str, str | None]:
            async with semaphore:
                return ip_address, await resolve_ip_location(ip_address, client=client)

        pairs = await asyncio.gather(*(_resolve(ip) for ip in unique_ips))
    return {ip_address: location for ip_address, location in pairs}
