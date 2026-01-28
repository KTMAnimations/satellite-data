from __future__ import annotations

import sys

from fastapi.testclient import TestClient


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def test_regions_list_seeds_without_lifespan(tmp_path, monkeypatch):
    # Ensure a fresh, isolated SQLite DB for this test.
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "true")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager

    res = client.get("/api/v1/regions", params={"type": "predefined", "page_size": 1})
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] >= 1
    assert len(payload["regions"]) >= 1
    assert payload["regions"][0]["type"] == "predefined"


def test_create_region_without_lifespan(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager

    payload = {
        "name": "My Custom Region",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    }
    created = client.post("/api/v1/regions", json=payload)
    assert created.status_code == 201, created.text
    region = created.json()
    assert region["name"] == "My Custom Region"
    assert region["type"] == "custom"

    listed = client.get("/api/v1/regions", params={"type": "custom", "search": "custom", "page_size": 50})
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["total"] == 1
    assert listed_payload["regions"][0]["id"] == region["id"]
