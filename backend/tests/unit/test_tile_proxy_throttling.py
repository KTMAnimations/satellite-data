from __future__ import annotations

import asyncio
import sys
import threading
import time

import httpx


def _import_fresh_app():
    for name in list(sys.modules.keys()):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)

    from app.main import app

    return app


def test_tile_proxy_global_gee_throttle(monkeypatch):
    monkeypatch.setenv("GEE_MAX_CONCURRENT_REQUESTS", "2")
    # Disable disk cache so every request exercises the EE throttle path.
    monkeypatch.setenv("TILE_CACHE_MAX_MB", "0")

    app = _import_fresh_app()

    from app.routes import tiles as tiles_module

    active_lock = threading.Lock()
    active = 0
    max_active = 0

    class StubFetcher:
        def fetch_tile(self, x: int, y: int, z: int) -> bytes:
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with active_lock:
                active -= 1
            return b"PNG"

    def stub_get_tile_fetcher(metric, date_bucket: str, granularity: str, *, z=None):  # type: ignore[no-untyped-def]
        return StubFetcher()

    monkeypatch.setattr(tiles_module, "get_tile_fetcher", stub_get_tile_fetcher)

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async def one(i: int) -> None:
                res = await client.get(f"/api/v1/tiles/ndvi/weekly/2024-01-01/4/{i}/0.png")
                assert res.status_code == 200
                assert res.content == b"PNG"

            await asyncio.gather(*(one(i) for i in range(10)))

    asyncio.run(run())

    assert max_active <= 2


def test_tile_proxy_png_disk_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("GEE_MAX_CONCURRENT_REQUESTS", "8")
    monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("TILE_CACHE_MAX_MB", "10")

    app = _import_fresh_app()

    from app.routes import tiles as tiles_module

    fetch_count_lock = threading.Lock()
    fetch_count = 0

    class StubFetcher:
        def fetch_tile(self, x: int, y: int, z: int) -> bytes:
            nonlocal fetch_count
            with fetch_count_lock:
                fetch_count += 1
            return b"PNG"

    def stub_get_tile_fetcher(metric, date_bucket: str, granularity: str, *, z=None):  # type: ignore[no-untyped-def]
        return StubFetcher()

    monkeypatch.setattr(tiles_module, "get_tile_fetcher", stub_get_tile_fetcher)

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res1 = await client.get("/api/v1/tiles/ndvi/weekly/2024-01-01/4/3/0.png?v=23")
            assert res1.status_code == 200
            res2 = await client.get("/api/v1/tiles/ndvi/weekly/2024-01-01/4/3/0.png?v=23")
            assert res2.status_code == 200

    asyncio.run(run())

    assert fetch_count == 1


def test_tile_proxy_passes_zoom_to_fetcher(monkeypatch):
    monkeypatch.setenv("TILE_CACHE_MAX_MB", "0")
    app = _import_fresh_app()

    from app.routes import tiles as tiles_module

    seen_zoom: list[int | None] = []

    class StubFetcher:
        def fetch_tile(self, x: int, y: int, z: int) -> bytes:
            return b"PNG"

    def stub_get_tile_fetcher(metric, date_bucket: str, granularity: str, *, z=None):  # type: ignore[no-untyped-def]
        seen_zoom.append(z)
        return StubFetcher()

    monkeypatch.setattr(tiles_module, "get_tile_fetcher", stub_get_tile_fetcher)

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/tiles/ndvi/weekly/2024-01-01/6/3/0.png")
            assert res.status_code == 200

    asyncio.run(run())
    assert seen_zoom == [6]


def test_tile_proxy_clear_metric_cache_only_removes_selected_metric(monkeypatch, tmp_path):
    monkeypatch.setenv("GEE_MAX_CONCURRENT_REQUESTS", "8")
    monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("TILE_CACHE_MAX_MB", "10")

    app = _import_fresh_app()

    from app.routes import tiles as tiles_module

    fetch_count_lock = threading.Lock()
    fetch_count = 0

    class StubFetcher:
        def fetch_tile(self, x: int, y: int, z: int) -> bytes:
            nonlocal fetch_count
            with fetch_count_lock:
                fetch_count += 1
            return b"PNG"

    def stub_get_tile_fetcher(metric, date_bucket: str, granularity: str, *, z=None):  # type: ignore[no-untyped-def]
        return StubFetcher()

    monkeypatch.setattr(tiles_module, "get_tile_fetcher", stub_get_tile_fetcher)

    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ndvi_url = "/api/v1/tiles/ndvi/weekly/2024-01-01/4/3/0.png?v=23"
            nightlights_url = "/api/v1/tiles/nightlights/weekly/2024-01-01/4/3/0.png?v=23"

            res1 = await client.get(ndvi_url)
            assert res1.status_code == 200
            res2 = await client.get(nightlights_url)
            assert res2.status_code == 200
            assert fetch_count == 2

            clear_res = await client.delete("/api/v1/tiles/cache/ndvi")
            assert clear_res.status_code == 200
            payload = clear_res.json()
            assert payload["metric"] == "ndvi"
            assert payload["deleted_files"] >= 1

            ndvi_after_clear = await client.get(ndvi_url)
            assert ndvi_after_clear.status_code == 200
            nightlights_after_clear = await client.get(nightlights_url)
            assert nightlights_after_clear.status_code == 200

    asyncio.run(run())
    assert fetch_count == 3
