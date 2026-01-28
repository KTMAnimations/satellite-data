from datetime import date
from pathlib import Path
from typing import Any, Literal

import imageio
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless operation
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)


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

    async def generate(
        self,
        region_id: str,
        metric: str,
        start_date: date,
        end_date: date,
        format: Literal["gif", "webm", "frames"] = "gif",
        frame_duration_ms: int = 500,
        width: int = 800,
        height: int = 600,
        export_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate an animation for a metric over time.

        Returns:
            Dictionary with file info and metadata
        """
        from sqlalchemy import select

        from app.models.observation import Observation
        from app.models.region import Region

        async with get_db_context() as db:
            # Get region info
            region_result = await db.execute(
                select(Region).where(Region.id == region_id)
            )
            region = region_result.scalar_one_or_none()

            if not region:
                raise ValueError(f"Region {region_id} not found")

            # Get observations with raster paths
            query = (
                select(Observation)
                .where(
                    Observation.region_id == region_id,
                    Observation.metric == metric,
                    Observation.date >= start_date,
                    Observation.date <= end_date,
                    Observation.raster_path.isnot(None),
                )
                .order_by(Observation.date)
            )

            result = await db.execute(query)
            observations = result.scalars().all()

        if not observations:
            # Generate synthetic frames for demo
            frames = self._generate_synthetic_frames(
                region.name, metric, start_date, end_date, width, height
            )
        else:
            frames = await self._load_observation_frames(
                observations, metric, width, height
            )
            # Fall back to synthetic frames if no raster files could be loaded
            if len(frames) == 0:
                logger.info(
                    "No raster files available, generating synthetic frames",
                    region=region.name,
                    metric=metric,
                )
                frames = self._generate_synthetic_frames(
                    region.name, metric, start_date, end_date, width, height
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
            self._save_gif(frames, output_path, frame_duration_ms)
        elif format == "webm":
            output_path = output_dir / f"{base_name}.webm"
            self._save_webm(frames, output_path, frame_duration_ms)
        else:  # frames
            output_path = output_dir / f"{base_name}_frames"
            output_path.mkdir(exist_ok=True)
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
    ) -> list[np.ndarray]:
        """Generate synthetic frames with proper metric colormaps for demonstration."""
        from dateutil.relativedelta import relativedelta
        from PIL import Image

        frames = []
        current = start_date
        frame_idx = 0

        # Get value range for this metric
        vmin, vmax = self.VALUE_RANGES.get(metric, (0.0, 1.0))

        # Get colormap for this metric
        colors = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])

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

            # Normalize to 0-1 for colormap application
            data_normalized = (data - vmin) / (vmax - vmin)
            data_normalized = np.clip(data_normalized, 0, 1)

            # Apply custom colormap (RGB tuples)
            rgb_data = np.zeros((data_height, data_width, 3), dtype=np.uint8)
            for i, color in enumerate(colors):
                lower = i / len(colors)
                upper = (i + 1) / len(colors)
                mask = (data_normalized >= lower) & (data_normalized < upper)

                if i < len(colors) - 1:
                    t = (data_normalized[mask] - lower) / (upper - lower)
                    c_low = np.array(color)
                    c_high = np.array(colors[min(i + 1, len(colors) - 1)])

                    rgb_data[mask, 0] = (c_low[0] * (1 - t) + c_high[0] * t).astype(np.uint8)
                    rgb_data[mask, 1] = (c_low[1] * (1 - t) + c_high[1] * t).astype(np.uint8)
                    rgb_data[mask, 2] = (c_low[2] * (1 - t) + c_high[2] * t).astype(np.uint8)

            # Handle the last color bin
            mask = data_normalized >= (len(colors) - 1) / len(colors)
            rgb_data[mask] = colors[-1]

            # Create figure with the colored overlay
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

            # Add a subtle map-like background (light gray)
            ax.set_facecolor('#e8e8e8')

            # Display the overlay
            im = ax.imshow(rgb_data, aspect='auto', extent=[0, 10, 0, 7.5])

            # Add title and date
            ax.set_title(f"{region_name} - {metric.replace('_', ' ').title()}\n{current.strftime('%B %Y')}",
                        fontsize=12, fontweight='bold', pad=10)
            ax.axis("off")

            # Add colorbar with proper labels
            from matplotlib.colors import LinearSegmentedColormap
            # Create matplotlib colormap from our colors for the colorbar
            cmap_colors = [(c[0]/255, c[1]/255, c[2]/255) for c in colors]
            custom_cmap = LinearSegmentedColormap.from_list(metric, cmap_colors, N=256)
            sm = plt.cm.ScalarMappable(cmap=custom_cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label(metric.replace("_", " ").title(), fontsize=10)

            # Convert to image array
            fig.canvas.draw()
            rgba = np.asarray(fig.canvas.buffer_rgba())
            frame = rgba[:, :, :3]  # Remove alpha channel
            frames.append(frame.copy())

            plt.close(fig)

            current += relativedelta(months=1)
            frame_idx += 1

        return frames

    async def _load_observation_frames(
        self,
        observations: list,
        metric: str,
        width: int,
        height: int,
    ) -> list[np.ndarray]:
        """Load and render frames from observation rasters."""
        import rasterio

        frames = []

        for obs in observations:
            try:
                with rasterio.open(obs.raster_path) as src:
                    data = src.read(1)

                # Create figure
                fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

                cmap_value = self.COLORMAPS.get(metric, self.COLORMAPS["ndvi"])
                if isinstance(cmap_value, str):
                    cmap = plt.get_cmap(cmap_value)
                else:
                    cmap_colors = [(c[0] / 255, c[1] / 255, c[2] / 255) for c in cmap_value]
                    cmap = LinearSegmentedColormap.from_list(metric, cmap_colors, N=256)

                im = ax.imshow(data, cmap=cmap)
                plt.colorbar(im, ax=ax)

                ax.set_title(obs.date.strftime("%B %Y"))
                ax.axis("off")

                # Convert to array
                fig.canvas.draw()
                # Use buffer_rgba() which works in newer matplotlib versions
                rgba = np.asarray(fig.canvas.buffer_rgba())
                frame = rgba[:, :, :3]  # Remove alpha channel
                frames.append(frame.copy())

                plt.close(fig)

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

    def _save_webm(
        self, frames: list[np.ndarray], path: Path, duration_ms: int
    ) -> None:
        """Save frames as WebM video."""
        fps = 1000 / duration_ms
        imageio.mimsave(
            str(path),
            frames,
            format="FFMPEG",
            fps=fps,
            codec="libvpx-vp9",
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
