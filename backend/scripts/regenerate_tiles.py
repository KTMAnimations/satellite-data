#!/usr/bin/env python3
"""
Regenerate US tiles with fixed chunk blending.

Run with: docker exec -it satellite-api python scripts/regenerate_tiles.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tiles.us_tile_generator import USTileGenerator


async def main():
    """Regenerate nightlights tiles for January 2024."""
    print("Starting tile regeneration with chunk blending fix...")

    generator = USTileGenerator()

    # Clear existing tiles first
    import shutil
    tiles_path = generator.tiles_dir / "nightlights" / "2024-01"
    if tiles_path.exists():
        print(f"Removing old tiles at {tiles_path}")
        shutil.rmtree(tiles_path)

    # Regenerate with force=True to ensure all tiles are recreated
    print("Generating new tiles for nightlights 2024-01 at zoom level 11...")
    stats = await generator.generate_month(
        year=2024,
        month=1,
        metrics=["nightlights"],
        zoom_levels=[11],
        force=True,
    )

    print(f"Tile generation complete: {stats}")
    return stats


if __name__ == "__main__":
    asyncio.run(main())
