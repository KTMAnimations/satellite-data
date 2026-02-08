from __future__ import annotations

import sys

from fastapi.testclient import TestClient


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def test_telemetry_register_events_and_admin_views(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager

    reg = client.post(
        "/api/v1/telemetry/register",
        json={
            "instance_id": "inst-1",
            "device_id": "dev-1",
            "meta": {"foo": "bar"},
            "path": "/map",
        },
    )
    assert reg.status_code == 200, reg.text
    reg_payload = reg.json()
    assert reg_payload["instance_id"] == "inst-1"
    assert reg_payload["ip_address"]

    events = client.post(
        "/api/v1/telemetry/events",
        json={
            "instance_id": "inst-1",
            "device_id": "dev-1",
            "events": [
                {"type": "page_load", "client_ts_ms": 1000, "path": "/map", "data": {"path": "/map"}},
                {"type": "map_zoom", "client_ts_ms": 2000, "path": "/map", "data": {"center": [1.0, 2.0], "zoom": 5}},
            ],
        },
    )
    assert events.status_code == 200, events.text
    assert events.json()["inserted"] == 2

    ips = client.get("/api/v1/admin/ips")
    assert ips.status_code == 200, ips.text
    ips_payload = ips.json()
    assert ips_payload["total"] == 1
    assert len(ips_payload["ips"]) == 1
    ip_address = ips_payload["ips"][0]["ip_address"]
    assert ips_payload["ips"][0]["event_count"] == 2
    assert ips_payload["ips"][0]["instance_count"] == 1
    assert "location" in ips_payload["ips"][0]

    ip_detail = client.get(f"/api/v1/admin/ips/{ip_address}")
    assert ip_detail.status_code == 200, ip_detail.text
    ip_detail_payload = ip_detail.json()
    assert ip_detail_payload["ip"]["ip_address"] == ip_address
    assert ip_detail_payload["ip"]["event_count"] == 2
    assert "location" in ip_detail_payload["ip"]
    assert len(ip_detail_payload["instances"]) == 1
    assert ip_detail_payload["instances"][0]["instance_id"] == "inst-1"

    inst = client.get("/api/v1/admin/instances/inst-1")
    assert inst.status_code == 200, inst.text
    inst_payload = inst.json()
    assert inst_payload["instance_id"] == "inst-1"
    assert inst_payload["device_id"] == "dev-1"
    assert inst_payload["total_events"] == 2
    assert inst_payload["event_type_counts"]["page_load"] == 1
    assert inst_payload["event_type_counts"]["map_zoom"] == 1

    inst_events = client.get("/api/v1/admin/instances/inst-1/events")
    assert inst_events.status_code == 200, inst_events.text
    inst_events_payload = inst_events.json()
    assert inst_events_payload["instance_id"] == "inst-1"
    assert inst_events_payload["total"] == 2
    assert len(inst_events_payload["events"]) == 2
    assert inst_events_payload["events"][0]["event_type"] == "page_load"
    assert inst_events_payload["events"][1]["event_type"] == "map_zoom"
