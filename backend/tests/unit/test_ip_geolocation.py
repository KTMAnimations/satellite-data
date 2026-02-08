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
        return ip_geolocation.IpGeolocationDetails(location="unused")

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_details", fake_fetch)

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
        return ip_geolocation.IpGeolocationDetails(
            location="Mountain View, California, United States",
            isp="Google LLC",
            organization="Google",
            asn="AS15169",
            is_residential=False,
        )

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_details", fake_fetch)

    first = await ip_geolocation.resolve_ip_details("8.8.8.8")
    second = await ip_geolocation.resolve_ip_details("8.8.8.8")

    assert first.location == "Mountain View, California, United States"
    assert second.location == "Mountain View, California, United States"
    assert first.isp == "Google LLC"
    assert second.asn == "AS15169"
    assert first.is_residential is False
    assert calls == ["8.8.8.8"]


async def test_resolve_ip_locations_deduplicates_batch_lookups(monkeypatch):
    calls: list[str] = []

    async def fake_fetch(ip_address: str, _client):
        calls.append(ip_address)
        return ip_geolocation.IpGeolocationDetails(
            location="Sydney, New South Wales, Australia",
            is_residential=True,
        )

    monkeypatch.setattr(ip_geolocation, "_fetch_public_ip_details", fake_fetch)

    details = await ip_geolocation.resolve_ip_details_map(["1.1.1.1", "1.1.1.1"])
    result = await ip_geolocation.resolve_ip_locations(["1.1.1.1", "1.1.1.1"])

    assert details["1.1.1.1"].is_residential is True
    assert result["1.1.1.1"] == "Sydney, New South Wales, Australia"
    assert calls == ["1.1.1.1"]


def test_classify_residential_from_ipapi_payload():
    residential_payload = {
        "is_datacenter": False,
        "is_proxy": False,
        "is_vpn": False,
        "is_tor": False,
        "is_crawler": False,
        "is_satellite": False,
        "company": {"type": "isp"},
        "asn": {"type": "isp"},
    }
    non_residential_payload = {
        "is_datacenter": True,
        "is_proxy": False,
        "is_vpn": False,
        "is_tor": False,
        "is_crawler": False,
        "is_satellite": False,
        "company": {"type": "hosting"},
        "asn": {"type": "hosting"},
    }

    assert ip_geolocation._classify_residential(residential_payload) is True  # type: ignore[attr-defined]
    assert ip_geolocation._classify_residential(non_residential_payload) is False  # type: ignore[attr-defined]
