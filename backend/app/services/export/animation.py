from datetime import date
from pathlib import Path
from typing import Any, Literal

import imageio
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger

logger = get_logger(__name__)


class AnimationGenerator:
    """Generate time-lapse animations from satellite data."""

    # Color maps for different metrics
    COLORMAPS = {
        "ndvi": "RdYlGn",  # Red-Yellow-Green for vegetation
        "nightlights": "hot",  # Hot colormap for lights
        "urban_density": "YlOrBr",  # Yellow-Orange-Brown for urban
        "parking": "Blues",  # Blues for parking occupancy
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

        if len(frames) == 0:
            raise ValueError("No frames available for animation")

        # Generate output
        output_dir = Path(self.settings.exports_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if format == "gif":
            output_path = output_dir / f"{region_id}_{metric}_animation.gif"
            self._save_gif(frames, output_path, frame_duration_ms)
        elif format == "webm":
            output_path = output_dir / f"{region_id}_{metric}_animation.webm"
            self._save_webm(frames, output_path, frame_duration_ms)
        else:  # frames
            output_path = output_dir / f"{region_id}_{metric}_frames"
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
        """Generate synthetic frames for demonstration."""
        from dateutil.relativedelta import relativedelta

        frames = []
        current = start_date
        frame_idx = 0

        # Create synthetic data with seasonal variation
        while current <= end_date:
            # Create frame
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

            # Generate synthetic heatmap data
            np.random.seed(frame_idx)
            x = np.linspace(0, 4 * np.pi, 50)
            y = np.linspace(0, 4 * np.pi, 50)
            X, Y = np.meshgrid(x, y)

            # Add seasonal variation
            month = current.month
            seasonal_factor = 1 + 0.3 * np.sin((month - 1) * np.pi / 6)

            data = (
                np.sin(X) * np.cos(Y) * seasonal_factor
                + np.random.random((50, 50)) * 0.2
            )

            # Normalize based on metric
            if metric == "ndvi":
                data = np.clip(data, -1, 1)
                vmin, vmax = -1, 1
            elif metric == "nightlights":
                data = np.abs(data) * 50
                vmin, vmax = 0, 100
            else:
                data = (data + 1) / 2
                vmin, vmax = 0, 1

            # Plot
            cmap = self.COLORMAPS.get(metric, "viridis")
            im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
            plt.colorbar(im, ax=ax, label=metric.replace("_", " ").title())

            ax.set_title(f"{region_name} - {current.strftime('%B %Y')}")
            ax.axis("off")

            # Convert to image array
            fig.canvas.draw()
            frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            frames.append(frame)

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

                cmap = self.COLORMAPS.get(metric, "viridis")
                im = ax.imshow(data, cmap=cmap)
                plt.colorbar(im, ax=ax)

                ax.set_title(obs.date.strftime("%B %Y"))
                ax.axis("off")

                # Convert to array
                fig.canvas.draw()
                frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
                frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (3,))
                frames.append(frame)

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
            frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            frames.append(frame)

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
