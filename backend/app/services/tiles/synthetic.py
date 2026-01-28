"""
Synthetic tile generator for on-demand tile creation.

Generates realistic-looking metric overlay tiles when pre-generated tiles aren't available.
Uses world coordinates to ensure seamless patterns across tile boundaries.
"""

import math
from io import BytesIO

import numpy as np
from PIL import Image

# Tile size in pixels
TILE_SIZE = 256


def tile_to_lon_lat(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """Convert tile coordinates to lon/lat bounds (west, south, east, north)."""
    n = 2 ** z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.atan(math.sinh(math.pi * (1 - 2 * y / n))) * 180.0 / math.pi
    south = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))) * 180.0 / math.pi
    return west, south, east, north


def hash_grid(xi: np.ndarray, yi: np.ndarray) -> np.ndarray:
    """Vectorized hash function for integer grid coordinates."""
    # Use bit manipulation for fast deterministic pseudo-random values
    h = (xi * 374761393 + yi * 668265263) & 0x7FFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF
    return (h & 0xFFFF) / 65535.0


def smoothstep(t: np.ndarray) -> np.ndarray:
    """Smooth interpolation function."""
    return t * t * (3 - 2 * t)


def value_noise_fast(lon: np.ndarray, lat: np.ndarray, scale: float = 1.0) -> np.ndarray:
    """Fast vectorized value noise based on world coordinates."""
    # Scale coordinates
    x = lon * scale
    y = lat * scale

    # Integer and fractional parts
    xi = np.floor(x).astype(np.int32)
    yi = np.floor(y).astype(np.int32)
    xf = x - xi
    yf = y - yi

    # Smooth interpolation weights
    u = smoothstep(xf)
    v = smoothstep(yf)

    # Hash values at four corners (fully vectorized)
    n00 = hash_grid(xi, yi)
    n10 = hash_grid(xi + 1, yi)
    n01 = hash_grid(xi, yi + 1)
    n11 = hash_grid(xi + 1, yi + 1)

    # Bilinear interpolation (fully vectorized)
    nx0 = n00 * (1 - u) + n10 * u
    nx1 = n01 * (1 - u) + n11 * u
    return nx0 * (1 - v) + nx1 * v


def fbm_noise_fast(lon: np.ndarray, lat: np.ndarray, octaves: int = 4) -> np.ndarray:
    """Fast fractional Brownian motion - multi-octave noise."""
    result = np.zeros_like(lon)
    amplitude = 1.0
    frequency = 1.0
    max_value = 0.0

    for _ in range(octaves):
        result += amplitude * value_noise_fast(lon, lat, frequency)
        max_value += amplitude
        amplitude *= 0.5
        frequency *= 2.0

    return result / max_value


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

    # Make low values more transparent
    low_mask = data <= 0.05
    rgb[low_mask, 3] = 0

    return Image.fromarray(rgb, "RGBA")


def generate_synthetic_data(x: int, y: int, zoom: int, metric: str, month: int) -> np.ndarray:
    """
    Generate synthetic tile data based on world coordinates.

    Uses continuous functions that produce seamless patterns across tile boundaries.
    All operations are fully vectorized for fast generation.
    """
    # Get tile bounds in lon/lat
    west, south, east, north = tile_to_lon_lat(x, y, zoom)

    # Create coordinate grids for each pixel (world coordinates)
    lon_vals = np.linspace(west, east, TILE_SIZE, endpoint=False)
    lat_vals = np.linspace(north, south, TILE_SIZE, endpoint=False)  # north to south (top to bottom)
    lon, lat = np.meshgrid(lon_vals, lat_vals)

    # Generate base pattern using fast multi-octave noise (seamless across tiles)
    coarse_noise = fbm_noise_fast(lon, lat, octaves=3)  # Large-scale patterns
    fine_noise = value_noise_fast(lon, lat, scale=8.0)  # Fine detail

    # Create urban-like hotspots using deterministic sin/cos patterns
    # These create a regular pattern of "cities" that seamlessly tile
    hotspots = (
        0.4 * (np.sin(lon * 0.3) ** 2) * (np.sin(lat * 0.4) ** 2) +
        0.3 * (np.sin(lon * 0.7 + 1.5) ** 2) * (np.sin(lat * 0.5 + 0.8) ** 2)
    )

    # Add medium-frequency variation
    medium_var = 0.5 + 0.5 * np.sin(lon * 1.2 + lat * 0.7) * np.cos(lon * 0.6 - lat * 1.1)

    # Combine patterns
    data = (
        0.35 * coarse_noise +     # Base terrain variation
        0.30 * hotspots +         # Urban hotspot pattern
        0.20 * medium_var +       # Medium-scale variation
        0.15 * fine_noise         # Fine texture
    )

    # Apply seasonal variation based on metric
    if metric == "nightlights":
        # Higher in winter (snowbird effect)
        seasonal = 1 + 0.15 * np.cos((month - 1) * np.pi / 6)
    elif metric == "ndvi":
        # Higher in summer
        seasonal = 0.4 + 0.6 * np.sin((month - 4) * np.pi / 6)
    elif metric == "temperature":
        # Higher in summer
        seasonal = 0.3 + 0.7 * np.sin((month - 4) * np.pi / 6)
    elif metric in ["active_fire", "fire_historical"]:
        # Higher in late summer (fire season)
        seasonal = 0.15 + 0.85 * max(0, np.sin((month - 5) * np.pi / 6))
    elif metric == "precipitation":
        # Variable by season
        seasonal = 0.5 + 0.5 * np.sin((month - 3) * np.pi / 6)
    elif metric == "surface_water":
        # Higher in spring (snowmelt)
        seasonal = 0.6 + 0.4 * np.sin((month - 2) * np.pi / 6)
    else:
        seasonal = 1.0

    data = data * seasonal

    # Normalize to 0-1
    data = np.clip(data, 0, 1)

    return data


def generate_synthetic_tile(x: int, y: int, z: int, metric: str, month: int) -> bytes:
    """
    Generate a synthetic tile for the given coordinates and metric.

    Returns PNG image bytes.
    """
    # Generate synthetic data
    data = generate_synthetic_data(x, y, z, metric, month)

    # Get colormap
    colors = COLORMAPS.get(metric, COLORMAPS["ndvi"])

    # Apply colormap
    tile_img = apply_colormap(data, colors)

    # Convert to PNG bytes
    buffer = BytesIO()
    tile_img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
