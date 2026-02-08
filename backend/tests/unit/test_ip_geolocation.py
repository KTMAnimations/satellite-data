from __future__ import annotations

from app import ip_geolocation


def _clear_cache() -> None:
    ip_geolocation._LOCATION_CACHE.clear()  # type: ignore[attr-defined]


def setup_function() -> None:
    _clear_cache()


def teardown_function() -> None:
    _clear_cache()


async def test_resolve_ip_locations_skips_remote_for_invalid_and_private_ips(monkeypatch):
    calls: list[str] = []

    async def fake_fetch(ip_address: str, _client):
        calls.append(ip_address)
        return "unused"

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_location", fake_fetch)

    result = await ip_geolocation.resolve_ip_locations(["testclient", "127.0.0.1", "10.0.0.2", "192.168.1.8"])

    assert result["testclient"] is None
    assert result["127.0.0.1"] == "Local / Private Network"
    assert result["10.0.0.2"] == "Local / Private Network"
    assert result["192.168.1.8"] == "Local / Private Network"
    assert calls == []


async def test_resolve_ip_location_caches_public_lookups(monkeypatch):
    calls: list[str] = []

    async def fake_fetch(ip_address: str, _client):
        calls.append(ip_address)
        return "Mountain View, California, United States"

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_location", fake_fetch)

    first = await ip_geolocation.resolve_ip_location("8.8.8.8")
    second = await ip_geolocation.resolve_ip_location("8.8.8.8")

    assert first == "Mountain View, California, United States"
    assert second == "Mountain View, California, United States"
    assert calls == ["8.8.8.8"]


async def test_resolve_ip_locations_deduplicates_batch_lookups(monkeypatch):
    calls: list[str] = []

    async def fake_fetch(ip_address: str, _client):
        calls.append(ip_address)
        return "Sydney, New South Wales, Australia"

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_location", fake_fetch)

    result = await ip_geolocation.resolve_ip_locations(["1.1.1.1", "1.1.1.1"])

    assert result["1.1.1.1"] == "Sydney, New South Wales, Australia"
    assert calls == ["1.1.1.1"]
