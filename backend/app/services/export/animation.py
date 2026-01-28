from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

import imageio
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless operation
import math
import numpy as np

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


class AnimationGenerator:
    """Generate time-lapse animations from satellite data."""

    # Color maps for different metrics (RGB tuples for custom gradients)
    COLORMAPS = {
        "ndvi": [
            (165, 0, 38), (215, 48, 39), (244, 109, 67), (253, 174, 97),
            (254, 224, 139), (217, 239, 139), (166, 217, 106), (102, 189, 99),
            (26, 152, 80), (0, 104, 55),
        ],
        "nightlights": [
            (0, 0, 0), (30, 0, 50), (60, 0, 100), (100, 0, 150),
            (150, 50, 150), (200, 100, 100), (255, 150, 50), (255, 200, 100),
            (255, 255, 150), (255, 255, 255),
        ],
        "urban_density": [
            (255, 255, 229), (255, 247, 188), (254, 227, 145), (254, 196, 79),
            (254, 153, 41), (236, 112, 20), (204, 76, 2), (153, 52, 4),
            (102, 37, 6), (51, 18, 3),
        ],
        "parking": [
            (247, 251, 255), (222, 235, 247), (198, 219, 239), (158, 202, 225),
            (107, 174, 214), (66, 146, 198), (33, 113, 181), (8, 81, 156),
            (8, 48, 107), (3, 19, 43),
        ],
        "land_cover": [
            (247, 244, 249), (231, 225, 239), (212, 185, 218), (201, 148, 199),
            (186, 111, 178), (170, 79, 160), (152, 49, 142), (122, 1, 119),
            (92, 0, 89), (63, 0, 60),
        ],
        "surface_water": [
            (255, 255, 255), (240, 249, 255), (214, 234, 248), (174, 214, 241),
            (133, 193, 233), (93, 173, 226), (52, 152, 219), (41, 128, 185),
            (31, 97, 141), (21, 67, 96),
        ],
        "active_fire": [
            (255, 255, 204), (255, 237, 160), (254, 217, 118), (254, 178, 76),
            (253, 141, 60), (252, 78, 42), (227, 26, 28), (189, 0, 38),
            (128, 0, 38), (80, 0, 0),
        ],
        "no2": [
            (49, 54, 149), (69, 117, 180), (116, 173, 209), (171, 217, 233),
            (224, 243, 248), (254, 224, 144), (253, 174, 97), (244, 109, 67),
            (215, 48, 39), (165, 0, 38),
        ],
        "temperature": [
            (5, 48, 97), (33, 102, 172), (67, 147, 195), (146, 197, 222),
            (209, 229, 240), (253, 219, 199), (244, 165, 130), (214, 96, 77),
            (178, 24, 43), (103, 0, 31),
        ],
        "precipitation": [
            (255, 255, 255), (240, 249, 232), (204, 235, 197), (168, 221, 181),
            (123, 204, 196), (78, 179, 211), (43, 140, 190), (8, 104, 172),
            (8, 64, 129), (37, 37, 86),
        ],
        "aerosol": [
            (255, 255, 255), (253, 245, 230), (252, 226, 196), (250, 197, 152),
            (242, 165, 117), (221, 132, 82), (186, 101, 56), (145, 72, 36),
            (100, 45, 20), (50, 20, 5),
        ],
        "cropland": [
            (255, 255, 178), (254, 217, 118), (254, 178, 76), (253, 141, 60),
            (240, 59, 32), (189, 0, 38), (0, 128, 0), (34, 139, 34),
            (144, 238, 144), (255, 255, 0),
        ],
        "evapotranspiration": [
            (166, 97, 26), (191, 129, 45), (216, 179, 101), (229, 218, 169),
            (245, 245, 220), (199, 234, 229), (128, 205, 193), (53, 151, 143),
            (1, 102, 94), (0, 60, 48),
        ],
        "soil_moisture": [
            (139, 69, 19), (160, 82, 45), (188, 143, 90), (210, 180, 140),
            (245, 222, 179), (173, 216, 230), (135, 206, 235), (70, 130, 180),
            (65, 105, 225), (0, 0, 139),
        ],
        "impervious": [
            (255, 255, 255), (240, 240, 240), (217, 217, 217), (189, 189, 189),
            (150, 150, 150), (115, 115, 115), (82, 82, 82), (54, 54, 54),
            (26, 26, 26), (0, 0, 0),
        ],
        "fire_historical": [
            (255, 255, 204), (255, 237, 160), (254, 217, 118), (254, 178, 76),
            (253, 141, 60), (252, 78, 42), (227, 26, 28), (189, 0, 38),
            (128, 0, 38), (80, 0, 0),
        ],
        "canopy_height": [
            (247, 252, 245), (229, 245, 224), (199, 233, 192), (161, 217, 155),
            (116, 196, 118), (65, 171, 93), (35, 139, 69), (0, 109, 44),
            (0, 68, 27), (0, 40, 16),
        ],
    }

    # Value ranges for normalization
    VALUE_RANGES = {
        "ndvi": (-1.0, 1.0),
        "nightlights": (0.0, 100.0),
        "urban_density": (0.0, 1.0),
        "parking": (0.0, 1.0),
        "land_cover": (0.0, 1.0),
        "surface_water": (0.0, 1.0),
        "active_fire": (0.0, 500.0),
        "no2": (0.0, 0.0002),
        "temperature": (-30.0, 45.0),
        "precipitation": (0.0, 500.0),
        "aerosol": (-2.0, 5.0),
        "cropland": (0.0, 255.0),
        "evapotranspiration": (0.0, 300.0),
        "soil_moisture": (0.0, 0.5),
        "impervious": (0.0, 1.0),
        "fire_historical": (0.0, 500.0),
        "canopy_height": (0.0, 60.0),
    }

    def __init__(self):
        self.settings = get_settings()

    def _mercator_to_pixel(
        self,
        x_merc: float,
        y_merc: float,
        zoom: int,
    ) -> tuple[float, float]:
        """
        Convert Web Mercator meters (EPSG:3857) to global pixel coordinates at a given zoom.

        Slippy map / OSM tiles use Web Mercator with:
          originShift = pi * R
          worldSizePx = 256 * 2^zoom
        """
        origin_shift = math.pi * 6378137.0
        world_m = 2.0 * origin_shift
        world_px = 256.0 * (2**zoom)
        px = (x_merc + origin_shift) / world_m * world_px
        py = (origin_shift - y_merc) / world_m * world_px
        return px, py

    def _pixel_to_mercator(
        self,
        px: float,
        py: float,
        zoom: int,
    ) -> tuple[float, float]:
        """Inverse of _mercator_to_pixel()."""
        origin_shift = math.pi * 6378137.0
        world_m = 2.0 * origin_shift
        world_px = 256.0 * (2**zoom)
        x_merc = (px / world_px) * world_m - origin_shift
        y_merc = origin_shift - (py / world_px) * world_m
        return x_merc, y_merc

    def _choose_basemap_zoom(
        self,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
        *,
        min_zoom: int = 4,
        max_zoom: int = 11,
        max_tiles: int = 64,
    ) -> int:
        """Pick a zoom that provides detail without fetching too many tiles."""
        x_min, y_min, x_max, y_max = bbox_merc

        def tile_count_for_zoom(z: int) -> tuple[int, float, float]:
            px_tl, py_tl = self._mercator_to_pixel(x_min, y_max, z)
            px_br, py_br = self._mercator_to_pixel(x_max, y_min, z)
            bbox_px_w = max(1.0, px_br - px_tl)
            bbox_px_h = max(1.0, py_br - py_tl)

            tx_min = int(math.floor(px_tl / 256.0))
            ty_min = int(math.floor(py_tl / 256.0))
            tx_max = int(math.floor((px_br - 1.0) / 256.0))
            ty_max = int(math.floor((py_br - 1.0) / 256.0))
            tiles = max(1, tx_max - tx_min + 1) * max(1, ty_max - ty_min + 1)
            return tiles, bbox_px_w, bbox_px_h

        for z in range(max_zoom, min_zoom - 1, -1):
            tiles, bbox_px_w, bbox_px_h = tile_count_for_zoom(z)
            if tiles <= max_tiles and bbox_px_w >= width and bbox_px_h >= height:
                return z

        for z in range(max_zoom, min_zoom - 1, -1):
            tiles, _, _ = tile_count_for_zoom(z)
            if tiles <= max_tiles:
                return z

        return min_zoom

    async def _fetch_osm_tile(self, client: Any, z: int, x: int, y: int) -> "Image.Image":
        """Fetch an OSM tile with simple disk cache; falls back to a gray tile on failure."""
        from PIL import Image

        cache_path = (
            Path(self.settings.cache_dir)
            / "basemap_tiles"
            / "osm"
            / str(z)
            / str(x)
            / f"{y}.png"
        )
        # Read from cache if available.
        if cache_path.exists():
            try:
                return Image.open(cache_path).convert("RGB")
            except Exception:
                # Corrupt cache; ignore and re-fetch.
                pass

        try:
            url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            resp = await client.get(url)
            resp.raise_for_status()
            tile_bytes = resp.content

            # Best-effort cache write; don't fail the tile if disk is read-only.
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(tile_bytes)
            except Exception:
                pass

            return Image.open(BytesIO(tile_bytes)).convert("RGB")
        except Exception:
            # Network failures shouldn't break export; return a neutral placeholder.
            return Image.new("RGB", (256, 256), (235, 235, 235))

    async def _render_osm_basemap(
        self,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
        zoom: int,
    ) -> "Image.Image":
        """Render a stitched OSM basemap image for the requested bbox and output size."""
        import asyncio

        import httpx
        from PIL import Image

        x_min, y_min, x_max, y_max = bbox_merc

        px_tl, py_tl = self._mercator_to_pixel(x_min, y_max, zoom)
        px_br, py_br = self._mercator_to_pixel(x_max, y_min, zoom)

        tx_min = int(math.floor(px_tl / 256.0))
        ty_min = int(math.floor(py_tl / 256.0))
        tx_max = int(math.floor((px_br - 1.0) / 256.0))
        ty_max = int(math.floor((py_br - 1.0) / 256.0))

        max_index = (2**zoom) - 1
        tx_min = max(0, min(tx_min, max_index))
        tx_max = max(0, min(tx_max, max_index))
        ty_min = max(0, min(ty_min, max_index))
        ty_max = max(0, min(ty_max, max_index))

        tile_w = max(1, tx_max - tx_min + 1)
        tile_h = max(1, ty_max - ty_min + 1)
        if tile_w * tile_h > 64:
            raise ValueError(f"Basemap request too large: {tile_w * tile_h} tiles at z={zoom}")

        headers = {
            "User-Agent": "SatelliteMigration/animation-export (+https://localhost)",
            "Accept": "image/png,image/*;q=0.8,*/*;q=0.5",
        }

        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            sem = asyncio.Semaphore(8)

            async def fetch_tile(tx: int, ty: int) -> "Image.Image":
                async with sem:
                    return await self._fetch_osm_tile(client, zoom, tx, ty)

            tasks = []
            for ty in range(ty_min, ty_max + 1):
                for tx in range(tx_min, tx_max + 1):
                    tasks.append(fetch_tile(tx, ty))
            tiles = await asyncio.gather(*tasks)

        stitched = Image.new("RGB", (tile_w * 256, tile_h * 256), (235, 235, 235))
        idx = 0
        for ty in range(ty_min, ty_max + 1):
            for tx in range(tx_min, tx_max + 1):
                stitched.paste(tiles[idx], ((tx - tx_min) * 256, (ty - ty_min) * 256))
                idx += 1

        origin_px_x = tx_min * 256.0
        origin_px_y = ty_min * 256.0
        crop_left = int(round(px_tl - origin_px_x))
        crop_top = int(round(py_tl - origin_px_y))
        crop_right = int(round(px_br - origin_px_x))
        crop_bottom = int(round(py_br - origin_px_y))

        crop_left = max(0, min(crop_left, stitched.width))
        crop_top = max(0, min(crop_top, stitched.height))
        crop_right = max(crop_left + 1, min(crop_right, stitched.width))
        crop_bottom = max(crop_top + 1, min(crop_bottom, stitched.height))

        cropped = stitched.crop((crop_left, crop_top, crop_right, crop_bottom))
        if cropped.size != (width, height):
            cropped = cropped.resize((width, height), Image.Resampling.LANCZOS)
        return cropped

    async def _get_us_tile_bytes(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
        *,
        tile_version: int = 4,
    ) -> bytes:
        """Read (or generate) a US overlay tile, mirroring `/tiles/us/...` behavior."""
        import asyncio

        from app.services.tiles.generator import create_empty_tile
        from app.services.tiles.us_tile_on_demand import (
            ResolvedTileRequest,
            generate_us_tile_png,
            resolve_us_tile_request,
        )

        resolved = resolve_us_tile_request(metric=metric, date_str=date_str, requested_granularity=None)
        tiles_dir_name = "us_tiles" if tile_version <= 2 else f"us_tiles_v{tile_version}"

        tile_path = (
            Path(self.settings.cache_dir)
            / tiles_dir_name
            / metric
            / resolved.date_bucket
            / str(z)
            / str(x)
            / f"{y}.png"
        )

        if tile_path.exists():
            return tile_path.read_bytes()

        # Backwards-compatible fallback: if a daily tile is requested but the monthly tile exists,
        # serve the monthly one to avoid returning an empty tile.
        if resolved.granularity == "daily":
            monthly_bucket = resolved.date_bucket[:7]
            monthly_path = (
                Path(self.settings.cache_dir)
                / tiles_dir_name
                / metric
                / monthly_bucket
                / str(z)
                / str(x)
                / f"{y}.png"
            )
            if monthly_path.exists():
                return monthly_path.read_bytes()

        cache_ok = True
        cache_path = tile_path

        async def generate_with_retries(resolved_request: ResolvedTileRequest) -> bytes:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    return await generate_us_tile_png(metric=metric, resolved=resolved_request, z=z, x=x, y=y)
                except Exception as e:  # pragma: no cover - depends on EE/network
                    last_error = e
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (2**attempt))
            assert last_error is not None
            raise last_error

        try:
            tile_data = await generate_with_retries(resolved)
        except Exception:
            # Do not cache error-empties: transient EE failures should be retried later.
            cache_ok = False
            # Try monthly fallback generation for daily requests.
            if resolved.granularity == "daily":
                try:
                    monthly_resolved = ResolvedTileRequest(metric=metric, date_bucket=resolved.date_bucket[:7], granularity="monthly")
                    tile_data = await generate_with_retries(monthly_resolved)
                    cache_path = (
                        Path(self.settings.cache_dir)
                        / tiles_dir_name
                        / metric
                        / monthly_resolved.date_bucket
                        / str(z)
                        / str(x)
                        / f"{y}.png"
                    )
                    cache_ok = True
                except Exception:
                    tile_data = create_empty_tile()
            else:
                tile_data = create_empty_tile()

        if cache_ok:
            # Cache the generated tile for future requests (including legitimate empty tiles).
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(tile_data)
            except Exception:
                pass

        return tile_data

    async def _get_world_tile_bytes(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
        *,
        tile_version: int = 1,
    ) -> bytes:
        """Read (or generate) a global overlay tile, mirroring `/tiles/world/...` behavior."""
        import asyncio

        from app.services.tiles.generator import create_empty_tile
        from app.services.tiles.overlay_tile_on_demand import (
            ResolvedTileRequest,
            generate_overlay_tile_png,
            resolve_tile_request,
        )

        resolved = resolve_tile_request(metric=metric, date_str=date_str, requested_granularity=None)
        tiles_dir_name = "world_tiles" if tile_version <= 2 else f"world_tiles_v{tile_version}"

        tile_path = (
            Path(self.settings.cache_dir)
            / tiles_dir_name
            / metric
            / resolved.date_bucket
            / str(z)
            / str(x)
            / f"{y}.png"
        )

        if tile_path.exists():
            return tile_path.read_bytes()

        # Backwards-compatible fallback: if a daily tile is requested but the monthly tile exists,
        # serve the monthly one to avoid returning an empty tile.
        if resolved.granularity == "daily":
            monthly_bucket = resolved.date_bucket[:7]
            monthly_path = (
                Path(self.settings.cache_dir)
                / tiles_dir_name
                / metric
                / monthly_bucket
                / str(z)
                / str(x)
                / f"{y}.png"
            )
            if monthly_path.exists():
                return monthly_path.read_bytes()

        cache_ok = True
        cache_path = tile_path

        async def generate_with_retries(resolved_request: ResolvedTileRequest) -> bytes:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    return await generate_overlay_tile_png(metric=metric, resolved=resolved_request, z=z, x=x, y=y)
                except Exception as e:  # pragma: no cover - depends on EE/network
                    last_error = e
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (2**attempt))
            assert last_error is not None
            raise last_error

        try:
            tile_data = await generate_with_retries(resolved)
        except Exception:
            # Do not cache error-empties: transient EE failures should be retried later.
            cache_ok = False
            # Try monthly fallback generation for daily requests.
            if resolved.granularity == "daily":
                try:
                    monthly_resolved = ResolvedTileRequest(metric=metric, date_bucket=resolved.date_bucket[:7], granularity="monthly")
                    tile_data = await generate_with_retries(monthly_resolved)
                    cache_path = (
                        Path(self.settings.cache_dir)
                        / tiles_dir_name
                        / metric
                        / monthly_resolved.date_bucket
                        / str(z)
                        / str(x)
                        / f"{y}.png"
                    )
                    cache_ok = True
                except Exception:
                    tile_data = create_empty_tile()
            else:
                tile_data = create_empty_tile()

        if cache_ok:
            # Cache the generated tile for future requests (including legitimate empty tiles).
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(tile_data)
            except Exception:
                pass

        return tile_data

    async def _fetch_us_overlay_tile(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
        *,
        tile_version: int = 4,
    ) -> "Image.Image":
        from PIL import Image

        tile_bytes = await self._get_us_tile_bytes(metric, date_str, z, x, y, tile_version=tile_version)
        return Image.open(BytesIO(tile_bytes)).convert("RGBA")

    async def _fetch_world_overlay_tile(
        self,
        metric: str,
        date_str: str,
        z: int,
        x: int,
        y: int,
        *,
        tile_version: int = 1,
    ) -> "Image.Image":
        from PIL import Image

        tile_bytes = await self._get_world_tile_bytes(metric, date_str, z, x, y, tile_version=tile_version)
        return Image.open(BytesIO(tile_bytes)).convert("RGBA")

    async def _render_composite_overlay(
        self,
        *,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
        zoom: int,
        native_zoom: int,
        max_composite_zoom_diff: int,
        layer_opacity: float,
        fetch_tile: Callable[[int, int, int], Awaitable["Image.Image"]],
    ) -> np.ndarray:
        """
        Render an overlay layer using the same logic as `CompositeTileLayer`.

        The frontend always fetches tiles at `native_zoom` (11) and composites them down when
        viewing at lower zoom levels, up to `max_composite_zoom_diff`.
        """
        import asyncio

        from PIL import Image

        x_min, y_min, x_max, y_max = bbox_merc

        px_tl, py_tl = self._mercator_to_pixel(x_min, y_max, zoom)
        px_br, py_br = self._mercator_to_pixel(x_max, y_min, zoom)

        tx_min = int(math.floor(px_tl / 256.0))
        ty_min = int(math.floor(py_tl / 256.0))
        tx_max = int(math.floor((px_br - 1.0) / 256.0))
        ty_max = int(math.floor((py_br - 1.0) / 256.0))

        max_index = (2**zoom) - 1
        tx_min = max(0, min(tx_min, max_index))
        tx_max = max(0, min(tx_max, max_index))
        ty_min = max(0, min(ty_min, max_index))
        ty_max = max(0, min(ty_max, max_index))

        tile_w = max(1, tx_max - tx_min + 1)
        tile_h = max(1, ty_max - ty_min + 1)
        if tile_w * tile_h > 256:
            raise ValueError(f"Overlay request too large: {tile_w * tile_h} tiles at z={zoom}")

        is_composite = zoom < native_zoom
        zoom_diff = native_zoom - zoom if is_composite else 0
        if is_composite and zoom_diff > max_composite_zoom_diff:
            return np.zeros((height, width, 4), dtype=np.uint8)

        sem = asyncio.Semaphore(4)

        async def fetch(z: int, x: int, y: int) -> "Image.Image":
            async with sem:
                return await fetch_tile(z, x, y)

        if not is_composite:
            tasks: list[Awaitable["Image.Image"]] = []
            for ty in range(ty_min, ty_max + 1):
                for tx in range(tx_min, tx_max + 1):
                    tasks.append(fetch(native_zoom, tx, ty))
            tiles = await asyncio.gather(*tasks)
        else:
            scale = 2**zoom_diff
            tile_size = 256 // scale

            async def build_tile(tx: int, ty: int) -> "Image.Image":
                native_x0 = tx * scale
                native_y0 = ty * scale

                source_tasks: list[Awaitable["Image.Image"]] = []
                positions: list[tuple[int, int]] = []
                for dy in range(scale):
                    for dx in range(scale):
                        source_tasks.append(fetch(native_zoom, native_x0 + dx, native_y0 + dy))
                        positions.append((dx, dy))

                source_tiles = await asyncio.gather(*source_tasks)

                out = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                for src, (dx, dy) in zip(source_tiles, positions):
                    resized = (
                        src.resize((tile_size, tile_size), Image.Resampling.BILINEAR)
                        if tile_size != 256
                        else src
                    )
                    out.paste(resized, (dx * tile_size, dy * tile_size))
                return out

            tasks = []
            for ty in range(ty_min, ty_max + 1):
                for tx in range(tx_min, tx_max + 1):
                    tasks.append(build_tile(tx, ty))
            tiles = await asyncio.gather(*tasks)

        stitched = Image.new("RGBA", (tile_w * 256, tile_h * 256), (0, 0, 0, 0))
        idx = 0
        for ty in range(ty_min, ty_max + 1):
            for tx in range(tx_min, tx_max + 1):
                stitched.paste(tiles[idx], ((tx - tx_min) * 256, (ty - ty_min) * 256))
                idx += 1

        origin_px_x = tx_min * 256.0
        origin_px_y = ty_min * 256.0
        crop_left = int(round(px_tl - origin_px_x))
        crop_top = int(round(py_tl - origin_px_y))
        crop_right = int(round(px_br - origin_px_x))
        crop_bottom = int(round(py_br - origin_px_y))

        crop_left = max(0, min(crop_left, stitched.width))
        crop_top = max(0, min(crop_top, stitched.height))
        crop_right = max(crop_left + 1, min(crop_right, stitched.width))
        crop_bottom = max(crop_top + 1, min(crop_bottom, stitched.height))

        cropped = stitched.crop((crop_left, crop_top, crop_right, crop_bottom))
        if cropped.size != (width, height):
            cropped = cropped.resize((width, height), Image.Resampling.LANCZOS)

        overlay = np.array(cropped, dtype=np.uint8)
        opacity = float(max(0.0, min(1.0, layer_opacity)))
        if opacity < 1.0:
            overlay[..., 3] = (overlay[..., 3].astype(np.float32) * opacity).astype(np.uint8)
        return overlay

    async def _render_us_overlay(
        self,
        metric: str,
        date_str: str,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
        zoom: int,
        *,
        tile_version: int = 4,
        layer_opacity: float = 0.7,
        native_zoom: int = 11,
        max_composite_zoom_diff: int = 2,
    ) -> np.ndarray:
        """Render the US overlay tiles for the viewport and return an RGBA array."""
        async def fetch(z: int, x: int, y: int) -> "Image.Image":
            return await self._fetch_us_overlay_tile(
                metric,
                date_str,
                z,
                x,
                y,
                tile_version=tile_version,
            )

        return await self._render_composite_overlay(
            bbox_merc=bbox_merc,
            width=width,
            height=height,
            zoom=zoom,
            native_zoom=native_zoom,
            max_composite_zoom_diff=max_composite_zoom_diff,
            layer_opacity=layer_opacity,
            fetch_tile=fetch,
        )

    async def _render_world_overlay(
        self,
        metric: str,
        date_str: str,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
        zoom: int,
        *,
        tile_version: int = 1,
        layer_opacity: float = 0.7,
        native_zoom: int = 11,
        max_composite_zoom_diff: int = 2,
    ) -> np.ndarray:
        """Render the global overlay tiles for the viewport and return an RGBA array."""
        async def fetch(z: int, x: int, y: int) -> "Image.Image":
            return await self._fetch_world_overlay_tile(
                metric,
                date_str,
                z,
                x,
                y,
                tile_version=tile_version,
            )

        return await self._render_composite_overlay(
            bbox_merc=bbox_merc,
            width=width,
            height=height,
            zoom=zoom,
            native_zoom=native_zoom,
            max_composite_zoom_diff=max_composite_zoom_diff,
            layer_opacity=layer_opacity,
            fetch_tile=fetch,
        )

    async def _get_basemap(
        self,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> "Image.Image":
        from PIL import Image

        try:
            zoom = self._choose_basemap_zoom(bbox_merc, width, height)
            return await self._render_osm_basemap(bbox_merc, width, height, zoom)
        except Exception as e:
            logger.warning("Failed to render basemap, using fallback", error=str(e))
            return Image.new("RGB", (width, height), (235, 235, 235))

    def _compute_view_bbox_mercator(
        self,
        region_bounds_4326: tuple[float, float, float, float],
        width: int,
        height: int,
        *,
        padding_fraction: float = 0.10,
    ) -> tuple[float, float, float, float]:
        """Compute a padded, aspect-correct Web Mercator bbox for the output frame."""
        from pyproj import Transformer

        lon_min, lat_min, lon_max, lat_max = region_bounds_4326
        # Web Mercator is only defined up to about ±85.0511 degrees.
        lat_min = max(-85.05112878, min(85.05112878, lat_min))
        lat_max = max(-85.05112878, min(85.05112878, lat_max))

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x_min, y_min = transformer.transform(lon_min, lat_min)
        x_max, y_max = transformer.transform(lon_max, lat_max)

        # Guard against degenerate bboxes
        if x_min == x_max:
            x_min -= 500.0
            x_max += 500.0
        if y_min == y_max:
            y_min -= 500.0
            y_max += 500.0

        # Padding
        pad_x = (x_max - x_min) * padding_fraction
        pad_y = (y_max - y_min) * padding_fraction
        x_min -= pad_x
        x_max += pad_x
        y_min -= pad_y
        y_max += pad_y

        # Aspect correction (expand bbox to match output aspect ratio)
        desired_aspect = width / float(height)
        bbox_w = x_max - x_min
        bbox_h = y_max - y_min
        current_aspect = bbox_w / bbox_h if bbox_h else desired_aspect

        if current_aspect > desired_aspect:
            # Too wide -> increase height
            new_h = bbox_w / desired_aspect
            extra = (new_h - bbox_h) / 2.0
            y_min -= extra
            y_max += extra
        else:
            # Too tall -> increase width
            new_w = bbox_h * desired_aspect
            extra = (new_w - bbox_w) / 2.0
            x_min -= extra
            x_max += extra

        return x_min, y_min, x_max, y_max

    def _compute_leaflet_viewport(
        self,
        region_bounds_4326: tuple[float, float, float, float],
        width: int,
        height: int,
        *,
        padding_px: int = 50,
        min_zoom: int = 4,
        max_zoom: int = 11,
    ) -> tuple[tuple[float, float, float, float], int]:
        """
        Approximate Leaflet's `fitBounds(..., { padding: [padding_px, padding_px], maxZoom })`.

        Returns (viewport_bbox_mercator, zoom).
        """
        from pyproj import Transformer

        lon_min, lat_min, lon_max, lat_max = region_bounds_4326
        lat_min = max(-85.05112878, min(85.05112878, lat_min))
        lat_max = max(-85.05112878, min(85.05112878, lat_max))

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x_min, y_min = transformer.transform(lon_min, lat_min)
        x_max, y_max = transformer.transform(lon_max, lat_max)

        # Guard against degenerate bboxes
        if x_min == x_max:
            x_min -= 500.0
            x_max += 500.0
        if y_min == y_max:
            y_min -= 500.0
            y_max += 500.0

        usable_w = max(1, width - (padding_px * 2))
        usable_h = max(1, height - (padding_px * 2))

        chosen_zoom = min_zoom
        for z in range(max_zoom, min_zoom - 1, -1):
            px_tl, py_tl = self._mercator_to_pixel(x_min, y_max, z)
            px_br, py_br = self._mercator_to_pixel(x_max, y_min, z)
            bbox_px_w = px_br - px_tl
            bbox_px_h = py_br - py_tl
            if bbox_px_w <= usable_w and bbox_px_h <= usable_h:
                chosen_zoom = z
                break

        px_tl, py_tl = self._mercator_to_pixel(x_min, y_max, chosen_zoom)
        px_br, py_br = self._mercator_to_pixel(x_max, y_min, chosen_zoom)

        # Apply pixel padding to bounds, then center the padded bounds in the viewport.
        px_tl -= padding_px
        py_tl -= padding_px
        px_br += padding_px
        py_br += padding_px

        center_px_x = (px_tl + px_br) / 2.0
        center_px_y = (py_tl + py_br) / 2.0

        view_left = center_px_x - (width / 2.0)
        view_right = center_px_x + (width / 2.0)
        view_top = center_px_y - (height / 2.0)
        view_bottom = center_px_y + (height / 2.0)

        x_left, y_top = self._pixel_to_mercator(view_left, view_top, chosen_zoom)
        x_right, y_bottom = self._pixel_to_mercator(view_right, view_bottom, chosen_zoom)

        return (x_left, y_bottom, x_right, y_top), chosen_zoom

    def _compute_center_zoom_viewport(
        self,
        center_4326: tuple[float, float],
        zoom: int,
        width: int,
        height: int,
    ) -> tuple[tuple[float, float, float, float], int]:
        """
        Compute a viewport bbox in Web Mercator from an explicit center+zoom.

        `center_4326` is (lat, lon) as provided by the frontend.
        """
        from pyproj import Transformer

        lat, lon = center_4326
        lat = max(-85.05112878, min(85.05112878, lat))

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x_center, y_center = transformer.transform(lon, lat)

        center_px_x, center_px_y = self._mercator_to_pixel(x_center, y_center, zoom)

        view_left = center_px_x - (width / 2.0)
        view_right = center_px_x + (width / 2.0)
        view_top = center_px_y - (height / 2.0)
        view_bottom = center_px_y + (height / 2.0)

        x_left, y_top = self._pixel_to_mercator(view_left, view_top, zoom)
        x_right, y_bottom = self._pixel_to_mercator(view_right, view_bottom, zoom)

        return (x_left, y_bottom, x_right, y_top), zoom

    def _bounds_from_region_geojson(self, region_geojson: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
        if not region_geojson:
            return None
        if region_geojson.get("type") != "Polygon":
            return None
        coords = region_geojson.get("coordinates")
        if not coords:
            return None

        lon_min = float("inf")
        lat_min = float("inf")
        lon_max = float("-inf")
        lat_max = float("-inf")
        for ring in coords:
            for lon, lat in ring:
                lon_min = min(lon_min, float(lon))
                lat_min = min(lat_min, float(lat))
                lon_max = max(lon_max, float(lon))
                lat_max = max(lat_max, float(lat))
        if not (
            math.isfinite(lon_min)
            and math.isfinite(lat_min)
            and math.isfinite(lon_max)
            and math.isfinite(lat_max)
        ):
            return None
        return lon_min, lat_min, lon_max, lat_max

    def _build_region_mask(
        self,
        region_geojson: dict[str, Any] | None,
        bbox_merc: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> np.ndarray | None:
        """Return a boolean mask (True inside region) in output pixel space."""
        if not region_geojson or region_geojson.get("type") != "Polygon":
            return None

        coords = region_geojson.get("coordinates")
        if not coords:
            return None

        from PIL import Image, ImageDraw
        from pyproj import Transformer

        x_min, y_min, x_max, y_max = bbox_merc
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

        def ring_to_pixels(ring: list[list[float]]) -> list[tuple[float, float]]:
            pts: list[tuple[float, float]] = []
            for lon, lat in ring:
                x, y = transformer.transform(float(lon), float(lat))
                px = (x - x_min) / (x_max - x_min) * width
                py = (y_max - y) / (y_max - y_min) * height
                pts.append((px, py))
            return pts

        mask_img = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask_img)

        outer = ring_to_pixels(coords[0])
        draw.polygon(outer, fill=255)
        for hole in coords[1:]:
            draw.polygon(ring_to_pixels(hole), fill=0)

        return np.array(mask_img) > 0

    def _apply_colormap_rgba(
        self,
        values: np.ndarray,
        metric: str,
        valid_mask: np.ndarray,
        *,
        overlay_opacity: float = 0.7,
    ) -> np.ndarray:
        """Convert scalar values to an RGBA uint8 image using metric colormap."""
        colors = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])
        vmin, vmax = self.VALUE_RANGES.get(metric, (0.0, 1.0))
        if vmax == vmin:
            vmax = vmin + 1.0

        norm = (values - vmin) / (vmax - vmin)
        norm = np.clip(norm, 0.0, 1.0)

        xp = np.linspace(0.0, 1.0, num=len(colors), dtype=np.float32)
        r_vals = np.array([c[0] for c in colors], dtype=np.float32)
        g_vals = np.array([c[1] for c in colors], dtype=np.float32)
        b_vals = np.array([c[2] for c in colors], dtype=np.float32)

        flat = norm.reshape(-1).astype(np.float32)
        r = np.interp(flat, xp, r_vals).reshape(values.shape).astype(np.uint8)
        g = np.interp(flat, xp, g_vals).reshape(values.shape).astype(np.uint8)
        b = np.interp(flat, xp, b_vals).reshape(values.shape).astype(np.uint8)

        rgba = np.zeros((values.shape[0], values.shape[1], 4), dtype=np.uint8)
        rgba[..., 0] = r
        rgba[..., 1] = g
        rgba[..., 2] = b

        alpha = int(max(0.0, min(1.0, overlay_opacity)) * 255.0)
        rgba[..., 3] = 0
        rgba[valid_mask, 3] = alpha
        return rgba

    def _composite_frame(
        self,
        basemap_rgb: "Image.Image",
        overlay_rgba: np.ndarray,
        *,
        label: str | None = None,
    ) -> np.ndarray:
        from PIL import Image, ImageDraw

        base_rgba = basemap_rgb.convert("RGBA")
        overlay_img = Image.fromarray(overlay_rgba, mode="RGBA")
        composed = Image.alpha_composite(base_rgba, overlay_img)

        draw = ImageDraw.Draw(composed)
        if label:
            padding = 8
            # Simple label pill in top-left
            text_bbox = draw.textbbox((0, 0), label)
            tw = text_bbox[2] - text_bbox[0]
            th = text_bbox[3] - text_bbox[1]
            box = (padding, padding, padding + tw + padding, padding + th + padding)
            draw.rectangle(box, fill=(0, 0, 0, 140))
            draw.text((box[0] + padding, box[1] + padding), label, fill=(255, 255, 255, 255))

        # Tile usage requires attribution; bake it into the export.
        attribution = "© OpenStreetMap contributors"
        margin = 6
        attrib_bbox = draw.textbbox((0, 0), attribution)
        aw = attrib_bbox[2] - attrib_bbox[0]
        ah = attrib_bbox[3] - attrib_bbox[1]
        ax0 = composed.width - aw - (margin * 2) - margin
        ay0 = composed.height - ah - (margin * 2) - margin
        ax1 = composed.width - margin
        ay1 = composed.height - margin
        draw.rectangle((ax0, ay0, ax1, ay1), fill=(0, 0, 0, 120))
        draw.text((ax0 + margin, ay0 + margin), attribution, fill=(255, 255, 255, 220))

        return np.array(composed.convert("RGB"))

    async def generate(
        self,
        region_id: str,
        metric: str,
        start_date: date,
        end_date: date,
        format: Literal["gif", "frames"] = "gif",
        frame_duration_ms: int = 500,
        width: int = 800,
        height: int = 600,
        export_id: str | None = None,
        *,
        lock_view: bool = False,
        view_center: tuple[float, float] | None = None,
        view_zoom: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """
        Generate an animation for a metric over time.

        Returns:
            Dictionary with file info and metadata
        """
        import json
        from sqlalchemy import select
        from geoalchemy2.functions import ST_AsGeoJSON

        from app.models.region import Region

        async with get_db_context() as db:
            # Get region info
            region_result = await db.execute(
                select(Region, ST_AsGeoJSON(Region.geometry).label("geojson")).where(Region.id == region_id)
            )
            row = region_result.one_or_none()
            region = row[0] if row else None
            region_geojson = json.loads(row[1]) if row and row[1] else None

            if not region:
                raise ValueError(f"Region {region_id} not found")

        region_bounds = self._bounds_from_region_geojson(region_geojson)
        if region_bounds is None:
            # Should never happen (region geometry is required), but keep a safe fallback.
            region_bounds = (-180.0, -85.0, 180.0, 85.0)

        if lock_view:
            if view_center is None or view_zoom is None:
                logger.warning("lock_view requested but view_center/view_zoom missing; falling back to fitBounds")
                view_bbox_merc, map_zoom = self._compute_leaflet_viewport(
                    region_bounds, width, height, padding_px=50, max_zoom=11
                )
            else:
                view_bbox_merc, map_zoom = self._compute_center_zoom_viewport(
                    view_center, view_zoom, width, height
                )
        else:
            # Match the AnimationStudio experience (Leaflet fitBounds with padding and maxZoom=11).
            view_bbox_merc, map_zoom = self._compute_leaflet_viewport(
                region_bounds, width, height, padding_px=50, max_zoom=11
            )

        if progress_callback:
            await progress_callback({"progress": 2.0, "message": "Preparing basemap"})
        # Use the higher-level helper so tests can mock basemap rendering and so
        # exports gracefully fall back on any tile/network failures.
        basemap = await self._get_basemap(view_bbox_merc, width, height)
        region_mask = self._build_region_mask(region_geojson, view_bbox_merc, width, height)

        from dateutil.relativedelta import relativedelta

        # ExportCenter defaults to monthly animations; keep that cadence.
        frame_dates: list[date] = []
        current = start_date
        while current <= end_date:
            frame_dates.append(current)
            current = (current + relativedelta(months=1))

        daily_metrics: set[str] = {"nightlights", "active_fire"}
        frames: list[np.ndarray] = []
        total_frames = len(frame_dates)

        us_bounds = (-125.0, 24.0, -66.0, 50.0)
        use_us_overlay = not (
            region_bounds[2] < us_bounds[0]
            or region_bounds[0] > us_bounds[2]
            or region_bounds[3] < us_bounds[1]
            or region_bounds[1] > us_bounds[3]
        )

        if progress_callback:
            await progress_callback(
                {
                    "progress": 5.0,
                    "message": f"Rendering frames 0/{total_frames}",
                    "frame_count": total_frames,
                }
            )

        for idx, frame_date in enumerate(frame_dates):
            if metric in daily_metrics:
                tile_date_str = frame_date.isoformat()  # YYYY-MM-DD
            else:
                tile_date_str = frame_date.strftime("%Y-%m")  # YYYY-MM

            overlay = np.zeros((height, width, 4), dtype=np.uint8)
            if map_zoom >= 9:
                try:
                    overlay = (
                        await self._render_us_overlay(
                            metric=metric,
                            date_str=tile_date_str,
                            bbox_merc=view_bbox_merc,
                            width=width,
                            height=height,
                            zoom=map_zoom,
                            tile_version=4,
                            layer_opacity=0.7,
                        )
                        if use_us_overlay
                        else await self._render_world_overlay(
                            metric=metric,
                            date_str=tile_date_str,
                            bbox_merc=view_bbox_merc,
                            width=width,
                            height=height,
                            zoom=map_zoom,
                            tile_version=1,
                            layer_opacity=0.7,
                        )
                    )
                except Exception as e:
                    logger.warning("Failed to render overlay tiles; exporting basemap only", error=str(e))

            if region_mask is not None:
                overlay[~region_mask, 3] = 0

            label = f"{region.name} • {metric.replace('_', ' ').title()} • {frame_date.strftime('%b %Y')}"
            frames.append(self._composite_frame(basemap, overlay, label=label))
            if progress_callback and total_frames > 0:
                pct = 5.0 + (float(idx + 1) / float(total_frames)) * 90.0
                await progress_callback(
                    {"progress": min(95.0, pct), "message": f"Rendering frames {idx + 1}/{total_frames}"}
                )

        if len(frames) == 0:
            raise ValueError("No frames available for animation")

        # Generate output
        output_dir = Path(self.settings.exports_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use export_id for filename if provided (for API exports), else use region/metric naming
        base_name = export_id if export_id else f"{region_id}_{metric}_animation"

        if format == "gif":
            output_path = output_dir / f"{base_name}.gif"
            if progress_callback:
                await progress_callback({"progress": 97.0, "message": "Encoding GIF"})
            self._save_gif(frames, output_path, frame_duration_ms)
        else:  # frames
            output_path = output_dir / f"{base_name}_frames"
            output_path.mkdir(exist_ok=True)
            if progress_callback:
                await progress_callback({"progress": 97.0, "message": "Writing frames"})
            self._save_frames(frames, output_path)

        file_size = (
            sum(f.stat().st_size for f in output_path.glob("*"))
            if format == "frames"
            else output_path.stat().st_size
        )

        logger.info(
            "Animation generated",
            path=str(output_path),
            frames=len(frames),
            format=format,
        )

        return {
            "path": str(output_path),
            "frame_count": len(frames),
            "file_size": file_size,
            "format": format,
        }

    def _generate_synthetic_frames(
        self,
        region_name: str,
        metric: str,
        start_date: date,
        end_date: date,
        width: int,
        height: int,
        basemap: "Image.Image",
        view_bbox_merc: tuple[float, float, float, float],
        region_mask: np.ndarray | None,
        region_bounds_4326: tuple[float, float, float, float],
    ) -> list[np.ndarray]:
        """Generate synthetic frames rendered as a semi-transparent overlay over a basemap."""
        from dateutil.relativedelta import relativedelta
        from rasterio.transform import from_bounds
        from rasterio.warp import Resampling, reproject

        frames = []
        current = start_date
        frame_idx = 0

        # Get value range for this metric
        vmin, vmax = self.VALUE_RANGES.get(metric, (0.0, 1.0))

        # Data resolution for the overlay
        data_width, data_height = 200, 150

        # Create synthetic data with seasonal variation
        while current <= end_date:
            # Generate synthetic heatmap data with geographic-like patterns
            np.random.seed(frame_idx * 1000 + hash(region_name) % 1000)

            # Create base pattern that looks like geographic features
            x = np.linspace(0, 6 * np.pi, data_width)
            y = np.linspace(0, 4 * np.pi, data_height)
            X, Y = np.meshgrid(x, y)

            # Add seasonal variation based on metric
            month = current.month

            # Different seasonal patterns for different metrics
            if metric == "nightlights":
                # Phoenix-style: higher in winter (snowbirds)
                if "Phoenix" in region_name or "Miami" in region_name or "Tampa" in region_name:
                    seasonal_factor = 1 + 0.2 * np.cos((month - 1) * np.pi / 6)  # Peak in winter
                else:
                    seasonal_factor = 1 + 0.1 * np.sin((month - 7) * np.pi / 6)  # Slight summer peak
            elif metric == "ndvi":
                # Vegetation peaks in summer
                seasonal_factor = 0.5 + 0.5 * np.sin((month - 4) * np.pi / 6)  # Peak in July
            elif metric == "temperature":
                # Temperature peaks in summer
                seasonal_factor = 0.3 + 0.7 * np.sin((month - 4) * np.pi / 6)  # Peak in July
            elif metric == "precipitation":
                # Variable by region
                seasonal_factor = 0.5 + 0.5 * np.sin((month - 3) * np.pi / 6)  # Peak in June
            elif metric == "active_fire" or metric == "fire_historical":
                # Fire season peaks in late summer
                seasonal_factor = 0.2 + 0.8 * np.maximum(0, np.sin((month - 5) * np.pi / 6))  # Peak Aug
            else:
                seasonal_factor = 1 + 0.2 * np.sin((month - 1) * np.pi / 6)

            # Generate urban-like pattern with hotspots
            base_pattern = (
                0.3 * np.exp(-((X - 3 * np.pi) ** 2 + (Y - 2 * np.pi) ** 2) / 8)  # Central hotspot
                + 0.2 * np.exp(-((X - 4.5 * np.pi) ** 2 + (Y - 1.5 * np.pi) ** 2) / 4)  # Secondary
                + 0.15 * np.exp(-((X - 1.5 * np.pi) ** 2 + (Y - 3 * np.pi) ** 2) / 3)  # Tertiary
                + 0.1 * np.random.random((data_height, data_width))  # Noise
            )

            # Apply seasonal factor
            data = base_pattern * seasonal_factor

            # Scale to metric's value range
            data = vmin + (data / data.max()) * (vmax - vmin) * 0.8

            # Reproject synthetic data to output viewport (EPSG:3857)
            lon_min, lat_min, lon_max, lat_max = region_bounds_4326
            src_transform = from_bounds(lon_min, lat_min, lon_max, lat_max, data_width, data_height)
            dst_transform = from_bounds(*view_bbox_merc, width, height)
            nodata = -9999.0
            dst = np.full((height, width), nodata, dtype=np.float32)

            reproject(
                source=data.astype(np.float32),
                destination=dst,
                src_transform=src_transform,
                src_crs="EPSG:4326",
                dst_transform=dst_transform,
                dst_crs="EPSG:3857",
                dst_nodata=nodata,
                resampling=Resampling.bilinear,
            )

            valid = np.isfinite(dst) & (dst != nodata)
            if region_mask is not None:
                valid = valid & region_mask

            overlay = self._apply_colormap_rgba(dst, metric, valid, overlay_opacity=0.7)
            label = f"{region_name} • {metric.replace('_', ' ').title()} • {current.strftime('%b %Y')}"
            frame = self._composite_frame(basemap, overlay, label=label)
            frames.append(frame)

            current += relativedelta(months=1)
            frame_idx += 1

        return frames

    async def _load_observation_frames(
        self,
        observations: list,
        metric: str,
        width: int,
        height: int,
        basemap: "Image.Image",
        view_bbox_merc: tuple[float, float, float, float],
        region_mask: np.ndarray | None,
        region_name: str,
    ) -> list[np.ndarray]:
        """Load and render frames from observation rasters, composited over a basemap."""
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.warp import Resampling, reproject

        frames = []

        for obs in observations:
            try:
                if not getattr(obs, "raster_path", None):
                    continue

                raster_full_path = Path(self.settings.rasters_dir) / obs.raster_path
                if not raster_full_path.exists():
                    continue

                with rasterio.open(raster_full_path) as src:
                    src_data = src.read(1).astype(np.float32)
                    src_crs = src.crs or "EPSG:4326"
                    src_transform = src.transform
                    nodata = float(src.nodata) if src.nodata is not None else -9999.0

                dst_transform = from_bounds(*view_bbox_merc, width, height)
                dst = np.full((height, width), nodata, dtype=np.float32)

                reproject(
                    source=src_data,
                    destination=dst,
                    src_transform=src_transform,
                    src_crs=src_crs,
                    src_nodata=nodata,
                    dst_transform=dst_transform,
                    dst_crs="EPSG:3857",
                    dst_nodata=nodata,
                    resampling=Resampling.bilinear,
                )

                valid = np.isfinite(dst) & (dst != nodata)
                if region_mask is not None:
                    valid = valid & region_mask

                overlay = self._apply_colormap_rgba(dst, metric, valid, overlay_opacity=0.7)
                label = f"{region_name} • {metric.replace('_', ' ').title()} • {obs.date.strftime('%b %Y')}"
                frame = self._composite_frame(basemap, overlay, label=label)
                frames.append(frame)

            except Exception as e:
                logger.warning(
                    "Failed to load frame",
                    date=str(obs.date),
                    error=str(e),
                )
                continue

        return frames

    def _save_gif(
        self, frames: list[np.ndarray], path: Path, duration_ms: int
    ) -> None:
        """Save frames as animated GIF."""
        imageio.mimsave(
            str(path),
            frames,
            format="GIF",
            duration=duration_ms / 1000,
            loop=0,
        )

    def _save_frames(self, frames: list[np.ndarray], path: Path) -> None:
        """Save individual frames as PNG files."""
        for i, frame in enumerate(frames):
            frame_path = path / f"frame_{i:04d}.png"
            imageio.imwrite(str(frame_path), frame)


class FlowAnimationGenerator:
    """Generate migration flow animations with animated particles."""

    def __init__(self):
        self.settings = get_settings()

    async def generate_flow_animation(
        self,
        flows: list[dict],
        width: int = 1200,
        height: int = 800,
        duration_seconds: int = 10,
        fps: int = 30,
    ) -> dict[str, Any]:
        """
        Generate an animation showing migration flows between regions.

        Args:
            flows: List of flow dictionaries with origin, destination, intensity
            width: Output width in pixels
            height: Output height in pixels
            duration_seconds: Animation duration
            fps: Frames per second

        Returns:
            Dictionary with output file info
        """
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch

        total_frames = duration_seconds * fps
        frames = []

        # Create base map (simplified US outline for demo)
        for frame_idx in range(total_frames):
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

            # Draw base map (placeholder)
            ax.set_xlim(-130, -60)
            ax.set_ylim(20, 55)
            ax.set_facecolor("#e6f3ff")

            # Draw flows
            for flow in flows:
                origin = flow.get("origin_coords", (-75, 40))  # NYC default
                dest = flow.get("dest_coords", (-80, 26))  # Miami default
                intensity = flow["intensity"]

                # Animate particle along the path
                t = (frame_idx % fps) / fps
                current_x = origin[0] + (dest[0] - origin[0]) * t
                current_y = origin[1] + (dest[1] - origin[1]) * t

                # Draw flow line
                ax.plot(
                    [origin[0], dest[0]],
                    [origin[1], dest[1]],
                    color="orange",
                    alpha=0.3,
                    linewidth=intensity * 5,
                )

                # Draw moving particle
                ax.scatter(
                    [current_x],
                    [current_y],
                    s=intensity * 100,
                    c="red",
                    alpha=0.8,
                    zorder=5,
                )

                # Draw endpoints
                ax.scatter([origin[0]], [origin[1]], s=50, c="blue", zorder=4)
                ax.scatter([dest[0]], [dest[1]], s=50, c="green", zorder=4)

            ax.set_title("Seasonal Migration Flows")
            ax.axis("off")

            # Convert to array
            fig.canvas.draw()
            # Use buffer_rgba() which works in newer matplotlib versions
            rgba = np.asarray(fig.canvas.buffer_rgba())
            frame = rgba[:, :, :3]  # Remove alpha channel
            frames.append(frame.copy())

            plt.close(fig)

        # Save animation
        output_path = Path(self.settings.exports_dir) / "migration_flow.gif"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        imageio.mimsave(str(output_path), frames, format="GIF", duration=1 / fps, loop=0)

        return {
            "path": str(output_path),
            "frame_count": len(frames),
            "file_size": output_path.stat().st_size,
        }
