#!/usr/bin/env python3
"""
Generate synthetic US-wide tiles for all metrics and dates.

This script creates pre-computed tiles for the entire date range,
allowing the map overlay to work for all available data.

Usage:
    docker exec satellite-api python /app/scripts/generate_synthetic_tiles.py
"""

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/app")

from app.core.config import get_settings

# Tile size in pixels
TILE_SIZE = 256

# Continental US bounding box
US_BOUNDS = {
    "west": -125.0,
    "east": -66.0,
    "south": 24.0,
    "north": 50.0,
}

# All 17 metrics
METRICS = [
    "ndvi", "nightlights", "urban_density", "parking",
    "land_cover", "surface_water", "active_fire",
    "no2", "temperature", "precipitation", "aerosol",
    "cropland", "evapotranspiration", "soil_moisture",
    "impervious", "fire_historical", "canopy_height",
]

# Color maps for metrics (RGB tuples)
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


def lon_to_tile_x(lon: float, zoom: int) -> int:
    """Convert longitude to tile X coordinate."""
    return int((lon + 180) / 360 * (2 ** zoom))


def lat_to_tile_y(lat: float, zoom: int) -> int:
    """Convert latitude to tile Y coordinate."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    return int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)


def get_us_tiles(zoom: int) -> list[tuple[int, int]]:
    """Get all tile coordinates covering the US at a given zoom level."""
    x_min = lon_to_tile_x(US_BOUNDS["west"], zoom)
    x_max = lon_to_tile_x(US_BOUNDS["east"], zoom)
    y_min = lat_to_tile_y(US_BOUNDS["north"], zoom)
    y_max = lat_to_tile_y(US_BOUNDS["south"], zoom)

    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y))

    return tiles


def apply_colormap(data: np.ndarray, colors: list) -> Image.Image:
    """Apply a colormap to normalized data (0-1)."""
    height, width = data.shape
    rgb = np.zeros((height, width, 4), dtype=np.uint8)

    for i in range(len(colors)):
        lower = i / len(colors)
        upper = (i + 1) / len(colors)
        mask = (data >= lower) & (data < upper)

        if i < len(colors) - 1:
            t = np.zeros_like(data)
            t[mask] = (data[mask] - lower) / (upper - lower)
            c_low = np.array(colors[i])
            c_high = np.array(colors[min(i + 1, len(colors) - 1)])

            rgb[mask, 0] = (c_low[0] * (1 - t[mask]) + c_high[0] * t[mask]).astype(np.uint8)
            rgb[mask, 1] = (c_low[1] * (1 - t[mask]) + c_high[1] * t[mask]).astype(np.uint8)
            rgb[mask, 2] = (c_low[2] * (1 - t[mask]) + c_high[2] * t[mask]).astype(np.uint8)
            rgb[mask, 3] = 200  # Semi-transparent

    # Handle the last color bin
    mask = data >= (len(colors) - 1) / len(colors)
    rgb[mask, 0] = colors[-1][0]
    rgb[mask, 1] = colors[-1][1]
    rgb[mask, 2] = colors[-1][2]
    rgb[mask, 3] = 200

    # Make zero/nan transparent
    zero_mask = data <= 0.01
    rgb[zero_mask, 3] = 0

    return Image.fromarray(rgb, "RGBA")


def generate_synthetic_data(x: int, y: int, zoom: int, metric: str, month: int) -> np.ndarray:
    """Generate synthetic tile data based on tile position and metric."""
    # Use tile coordinates as seed for consistent patterns
    np.random.seed(x * 10000 + y * 100 + zoom)

    # Create base pattern - urban centers with gaussian distribution
    data = np.zeros((TILE_SIZE, TILE_SIZE))

    # Add multiple hotspots based on tile position
    for _ in range(3):
        cx = np.random.randint(50, TILE_SIZE - 50)
        cy = np.random.randint(50, TILE_SIZE - 50)
        sigma = np.random.randint(30, 80)

        xx, yy = np.meshgrid(np.arange(TILE_SIZE), np.arange(TILE_SIZE))
        gaussian = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))
        data += gaussian * np.random.uniform(0.3, 0.8)

    # Add noise
    data += np.random.random((TILE_SIZE, TILE_SIZE)) * 0.1

    # Apply seasonal variation
    if metric == "nightlights":
        # Higher in winter (snowbird effect for southern tiles)
        seasonal = 1 + 0.15 * np.cos((month - 1) * np.pi / 6)
    elif metric == "ndvi":
        # Higher in summer
        seasonal = 0.5 + 0.5 * np.sin((month - 4) * np.pi / 6)
    elif metric == "temperature":
        # Higher in summer
        seasonal = 0.3 + 0.7 * np.sin((month - 4) * np.pi / 6)
    elif metric in ["active_fire", "fire_historical"]:
        # Higher in late summer
        seasonal = 0.2 + 0.8 * max(0, np.sin((month - 5) * np.pi / 6))
    elif metric == "precipitation":
        # Variable
        seasonal = 0.5 + 0.5 * np.sin((month - 3) * np.pi / 6)
    else:
        seasonal = 1.0

    data = data * seasonal

    # Normalize to 0-1
    data = np.clip(data, 0, 1)

    return data


def generate_tiles():
    """Generate all synthetic tiles for US coverage."""
    settings = get_settings()
    tiles_dir = Path(settings.cache_dir) / "us_tiles"

    # Date range: Jan 2023 to Jan 2025
    dates = []
    for year in [2023, 2024]:
        for month in range(1, 13):
            dates.append(f"{year}-{month:02d}")
    dates.append("2025-01")

    # Zoom level 11 for detailed tiles
    zoom = 11
    tiles = get_us_tiles(zoom)

    print(f"Generating tiles for {len(dates)} months")
    print(f"Zoom level {zoom}: {len(tiles)} tiles per metric")
    print(f"Total tiles to generate: {len(dates) * len(METRICS) * len(tiles)}")
    print()

    total_generated = 0

    for date_str in dates:
        year, month = map(int, date_str.split("-"))

        for metric in METRICS:
            metric_dir = tiles_dir / metric / date_str / str(zoom)

            # Skip if already exists with tiles
            existing_tiles = list(metric_dir.rglob("*.png")) if metric_dir.exists() else []
            if len(existing_tiles) >= len(tiles) * 0.9:  # 90% coverage
                print(f"  Skipping {metric}/{date_str} - already generated")
                continue

            print(f"  Generating {metric}/{date_str}...", end=" ", flush=True)
            colors = COLORMAPS.get(metric, COLORMAPS["ndvi"])
            tiles_generated = 0

            for x, y in tiles:
                tile_path = metric_dir / str(x) / f"{y}.png"

                if tile_path.exists():
                    continue

                # Generate synthetic data
                data = generate_synthetic_data(x, y, zoom, metric, month)

                # Apply colormap
                tile_img = apply_colormap(data, colors)

                # Save tile
                tile_path.parent.mkdir(parents=True, exist_ok=True)
                tile_img.save(tile_path, format="PNG", optimize=True)
                tiles_generated += 1

            total_generated += tiles_generated
            print(f"{tiles_generated} tiles")

    print(f"\nTotal tiles generated: {total_generated}")


if __name__ == "__main__":
    generate_tiles()
