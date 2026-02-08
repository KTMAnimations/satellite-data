from __future__ import annotations

import sys
import time

from fastapi.testclient import TestClient


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def _create_region(client: TestClient) -> str:
    created = client.post(
        "/api/v1/regions",
        json={
            "name": "Export Test Region",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _poll_terminal_status(client: TestClient, export_id: str, timeout_seconds: float = 5.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload: dict | None = None

    while time.time() < deadline:
        res = client.get(f"/api/v1/exports/{export_id}/status")
        if res.status_code == 200:
            last_payload = res.json()
            if last_payload["status"] in {"completed", "failed"}:
                return last_payload
        time.sleep(0.05)

    raise AssertionError(f"Timed out waiting for export {export_id} to reach terminal state; last={last_payload}")


def _patch_gee_for_csv_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.gee as gee
    import app.routes.exports as exports_routes

    def fake_compute_time_series(*, metric, **kwargs):  # type: ignore[no-untyped-def]
        return [("2024-01", 1.0)]

    async def fake_gee_to_thread(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        return fn(*args, **kwargs)

    monkeypatch.setattr(gee, "compute_time_series", fake_compute_time_series)
    monkeypatch.setattr(exports_routes, "gee_to_thread", fake_gee_to_thread)


def _patch_gee_for_csv_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.gee as gee
    import app.routes.exports as exports_routes

    def fake_compute_time_series(*, metric, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("synthetic csv export failure")

    async def fake_gee_to_thread(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        return fn(*args, **kwargs)

    monkeypatch.setattr(gee, "compute_time_series", fake_compute_time_series)
    monkeypatch.setattr(exports_routes, "gee_to_thread", fake_gee_to_thread)


def _patch_gee_for_pdf_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import app.gee as gee
    import app.routes.exports as exports_routes

    # Provide enough monthly points to produce both time-series and seasonal charts.
    sample_series = [
        ("2024-01", 12.0),
        ("2024-02", 14.0),
        ("2024-03", 16.0),
        ("2024-04", 18.0),
        ("2024-05", 20.0),
        ("2024-06", 22.0),
        ("2024-07", 24.0),
        ("2024-08", 26.0),
        ("2024-09", 23.0),
        ("2024-10", 21.0),
        ("2024-11", 19.0),
        ("2024-12", 17.0),
    ]

    def fake_compute_time_series(*, metric, **kwargs):  # type: ignore[no-untyped-def]
        return list(sample_series)

    async def fake_gee_to_thread(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        return fn(*args, **kwargs)

    monkeypatch.setattr(gee, "compute_time_series", fake_compute_time_series)
    monkeypatch.setattr(exports_routes, "gee_to_thread", fake_gee_to_thread)


def test_export_csv_status_available_immediately_and_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager
    _patch_gee_for_csv_success(monkeypatch)
    region_id = _create_region(client)

    created = client.post(
        "/api/v1/exports/csv",
        json={
            "region_ids": [region_id],
            "metrics": ["nightlights"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )
    assert created.status_code == 202, created.text
    export_id = created.json()["id"]

    immediate = client.get(f"/api/v1/exports/{export_id}/status")
    assert immediate.status_code == 200, immediate.text
    assert immediate.json()["id"] == export_id

    final = _poll_terminal_status(client, export_id)
    assert final["status"] == "completed", final
    assert final["download_url"] is not None

    download = client.get(f"/api/v1/exports/download/{export_id}")
    assert download.status_code == 200, download.text
    assert "date,region,metric,value" in download.text


def test_export_csv_background_error_sets_failed_status(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager
    _patch_gee_for_csv_failure(monkeypatch)
    region_id = _create_region(client)

    created = client.post(
        "/api/v1/exports/csv",
        json={
            "region_ids": [region_id],
            "metrics": ["nightlights"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )
    assert created.status_code == 202, created.text
    export_id = created.json()["id"]

    final = _poll_terminal_status(client, export_id)
    assert final["status"] == "failed", final
    assert "synthetic csv export failure" in (final.get("error") or "")


def test_export_pdf_include_charts_adds_graph_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager
    _patch_gee_for_pdf_success(monkeypatch)
    region_id = _create_region(client)

    payload_base = {
        "region_id": region_id,
        "format": "pdf",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "metrics": ["nightlights", "ndvi"],
    }

    created_no_charts = client.post("/api/v1/exports/pdf", json={**payload_base, "include_charts": False})
    assert created_no_charts.status_code == 202, created_no_charts.text
    export_no_charts = created_no_charts.json()["id"]
    final_no_charts = _poll_terminal_status(client, export_no_charts)
    assert final_no_charts["status"] == "completed", final_no_charts
    download_no_charts = client.get(f"/api/v1/exports/download/{export_no_charts}")
    assert download_no_charts.status_code == 200, download_no_charts.text

    created_with_charts = client.post("/api/v1/exports/pdf", json={**payload_base, "include_charts": True})
    assert created_with_charts.status_code == 202, created_with_charts.text
    export_with_charts = created_with_charts.json()["id"]
    final_with_charts = _poll_terminal_status(client, export_with_charts)
    assert final_with_charts["status"] == "completed", final_with_charts
    download_with_charts = client.get(f"/api/v1/exports/download/{export_with_charts}")
    assert download_with_charts.status_code == 200, download_with_charts.text

    # Chart-enabled PDFs should contain additional drawing instructions and be larger.
    assert len(download_with_charts.content) > len(download_no_charts.content) + 500
