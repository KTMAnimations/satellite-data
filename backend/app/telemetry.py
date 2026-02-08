from __future__ import annotations

import json
from typing import Any

from fastapi import Request


def get_request_ip(request: Request) -> str:
    """
    Best-effort client IP resolution.

    Prefers forwarding headers when present (common behind reverse proxies),
    otherwise falls back to the direct client address.
    """

    x_forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if x_forwarded_for:
        # XFF may be a comma-separated list. Use the left-most hop.
        first = x_forwarded_for.split(",")[0].strip()
        if first:
            return first

    forwarded = (request.headers.get("forwarded") or "").strip()
    if forwarded:
        # Very small parser for RFC 7239, e.g.: for=1.2.3.4;proto=https;by=...
        for part in forwarded.split(";"):
            part = part.strip()
            if not part.lower().startswith("for="):
                continue
            value = part[4:].strip().strip('"')
            if value.startswith("[") and "]" in value:
                value = value[1 : value.index("]")]
            if value:
                return value

    x_real_ip = (request.headers.get("x-real-ip") or "").strip()
    if x_real_ip:
        return x_real_ip

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def dumps_json(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return "{}"


def loads_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}

