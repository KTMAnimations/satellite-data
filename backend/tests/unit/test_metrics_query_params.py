from __future__ import annotations

import sys
from queue import Queue

from fastapi.testclient import TestClient


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def test_metrics_accepts_bracket_array_params(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTO_SEED_PREDEFINED_REGIONS", "false")

    client = TestClient(_import_fresh_app())  # intentionally not used as a context manager

    # Patch out Earth Engine compute; just capture requested metrics.
    called_metrics: "Queue[str]" = Queue()

    def fake_compute_time_series(*, metric, **kwargs):  # type: ignore[no-untyped-def]
        called_metrics.put(metric)
        # Return one data point so the response isn't empty.
        return [("2024-01", 1.0)]

    import app.routes.metrics as metrics_routes

    monkeypatch.setattr(metrics_routes, "compute_time_series", fake_compute_time_series)

    # Create a region to request metrics for.
    created = client.post(
        "/api/v1/regions",
        json={
            "name": "Test Region",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
    )
    assert created.status_code == 201, created.text
    region_id = created.json()["id"]

    res = client.get(
        f"/api/v1/metrics/{region_id}",
        params=[
            ("start_date", "2024-01-01"),
            ("end_date", "2024-01-31"),
            ("granularity", "monthly"),
            ("metrics[]", "nightlights"),
        ],
    )
    assert res.status_code == 200, res.text

    seen = []
    while not called_metrics.empty():
        seen.append(called_metrics.get())

    assert seen == ["nightlights"], f"Expected only 'nightlights' to be computed, got: {seen}"

