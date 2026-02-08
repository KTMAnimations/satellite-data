from __future__ import annotations

import asyncio
import ipaddress
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass

import httpx


_LOOKUP_URL_TEMPLATE = "https://ipwho.is/{ip_address}"
_LOOKUP_TIMEOUT = httpx.Timeout(timeout=2.5, connect=1.5)
_LOOKUP_HEADERS = {"User-Agent": "satellite-data-admin/1.0"}
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_SIZE = 20_000
_NON_PUBLIC_IP_LOCATION = "Local / Private Network"
_NON_PUBLIC_NETWORK_TYPE = "private"
_MISSING = object()


@dataclass(frozen=True)
class IpGeolocationDetails:
    location: str | None = None
    continent: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    isp: str | None = None
    organization: str | None = None
    asn: str | None = None
    domain: str | None = None
    network_type: str | None = None


_UNKNOWN_DETAILS = IpGeolocationDetails()
_LOCATION_CACHE: dict[str, tuple[float, IpGeolocationDetails]] = {}


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


def _clean_number(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _normalize_asn(value: object) -> str | None:
    if isinstance(value, int):
        return f"AS{value}" if value > 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    if not text:
        return None
    if text.startswith("AS"):
        return text
    return f"AS{text}" if text.isdigit() else text


def _cache_get(ip_address: str) -> IpGeolocationDetails | object:
    cached = _LOCATION_CACHE.get(ip_address)
    if cached is None:
        return _MISSING

    expires_at, value = cached
    if expires_at <= time.monotonic():
        _LOCATION_CACHE.pop(ip_address, None)
        return _MISSING

    return value


def _cache_set(ip_address: str, value: IpGeolocationDetails) -> None:
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
    details = await _fetch_public_ip_details(ip_address, client)
    return details.location if details else None


def _parse_public_ip_details(payload: dict[str, object]) -> IpGeolocationDetails:
    connection = payload.get("connection")
    if not isinstance(connection, dict):
        connection = {}

    timezone_payload = payload.get("timezone")
    if not isinstance(timezone_payload, dict):
        timezone_payload = {}

    return IpGeolocationDetails(
        location=_format_location(payload),
        continent=_clean_label(payload.get("continent")),
        country=_clean_label(payload.get("country")),
        region=_clean_label(payload.get("region")),
        city=_clean_label(payload.get("city")),
        latitude=_clean_number(payload.get("latitude")),
        longitude=_clean_number(payload.get("longitude")),
        timezone=(
            _clean_label(timezone_payload.get("id"))
            or _clean_label(timezone_payload.get("abbr"))
            or _clean_label(timezone_payload.get("utc"))
        ),
        isp=_clean_label(connection.get("isp")),
        organization=_clean_label(connection.get("org")),
        asn=_normalize_asn(connection.get("asn")),
        domain=_clean_label(connection.get("domain")),
        network_type=_clean_label(payload.get("type")),
    )


async def _fetch_public_ip_details(ip_address: str, client: httpx.AsyncClient) -> IpGeolocationDetails | None:
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

    return _parse_public_ip_details(payload)


async def resolve_ip_details(
    ip_address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> IpGeolocationDetails:
    normalized = (ip_address or "").strip()
    if not normalized:
        return _UNKNOWN_DETAILS

    cached = _cache_get(normalized)
    if cached is not _MISSING:
        return cached if isinstance(cached, IpGeolocationDetails) else _UNKNOWN_DETAILS

    if not _is_global_ip(normalized):
        try:
            parsed = ipaddress.ip_address(normalized)
        except ValueError:
            _cache_set(normalized, _UNKNOWN_DETAILS)
            return _UNKNOWN_DETAILS

        if not parsed.is_global:
            non_public = IpGeolocationDetails(
                location=_NON_PUBLIC_IP_LOCATION,
                network_type=_NON_PUBLIC_NETWORK_TYPE,
            )
            _cache_set(normalized, non_public)
            return non_public

    if client is not None:
        details = await _fetch_public_ip_details(normalized, client)
        resolved = details or _UNKNOWN_DETAILS
        _cache_set(normalized, resolved)
        return resolved

    async with httpx.AsyncClient(timeout=_LOOKUP_TIMEOUT, headers=_LOOKUP_HEADERS) as one_off_client:
        details = await _fetch_public_ip_details(normalized, one_off_client)
        resolved = details or _UNKNOWN_DETAILS
        _cache_set(normalized, resolved)
        return resolved


async def resolve_ip_location(ip_address: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    details = await resolve_ip_details(ip_address, client=client)
    return details.location


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
                details = await resolve_ip_details(ip_address, client=client)
                return ip_address, details.location

        pairs = await asyncio.gather(*(_resolve(ip) for ip in unique_ips))
    return {ip_address: location for ip_address, location in pairs}
