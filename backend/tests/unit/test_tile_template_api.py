from __future__ import annotations

import asyncio
import sys

import httpx


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def test_tile_template_returns_without_earth_engine(monkeypatch):
    app = _import_fresh_app()

    import app.gee as gee_module

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("get_tile_fetcher should not be called by /tiles/template")

    monkeypatch.setattr(gee_module, "get_tile_fetcher", boom)

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "ndvi", "date_bucket": "2024-02", "granularity": "monthly"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["metric"] == "ndvi"
            assert data["date_bucket"] == "2024-02"
            assert data["granularity"] == "monthly"
            assert "/api/v1/tiles/ndvi/monthly/2024-02/{z}/{x}/{y}.png" in data["tile_url"]

    asyncio.run(run())


def test_tile_template_uses_metric_tile_visualization_range():
    app = _import_fresh_app()

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "precipitation", "date_bucket": "2024-02", "granularity": "monthly"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["min"] == 0.0
            assert data["max"] == 180.0

    asyncio.run(run())


def test_tile_template_rejects_invalid_date_bucket_format():
    app = _import_fresh_app()

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "ndvi", "date_bucket": "2024-02-01", "granularity": "monthly"},
            )
            assert res.status_code == 400

            res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "ndvi", "date_bucket": "2024-02", "granularity": "weekly"},
            )
            assert res.status_code == 400

    asyncio.run(run())


def test_tile_template_snow_cover_uses_default_opacity():
    app = _import_fresh_app()

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ndvi_res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "ndvi", "date_bucket": "2024-02", "granularity": "monthly"},
            )
            assert ndvi_res.status_code == 200
            ndvi_data = ndvi_res.json()

            snow_res = await client.get(
                "/api/v1/tiles/template",
                params={"metric": "snow_cover", "date_bucket": "2024-02", "granularity": "monthly"},
            )
            assert snow_res.status_code == 200
            snow_data = snow_res.json()

            assert snow_data["opacity"] == ndvi_data["opacity"]
            assert snow_data["opacity"] > 0.0

    asyncio.run(run())
