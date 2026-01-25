#!/usr/bin/env python3
"""
Seed the database with predefined regions.

Usage:
    python scripts/seed_regions.py
"""

import asyncio
import json
from datetime import datetime, timezone

# Major US Cities (simplified bounding boxes)
US_MAJOR_CITIES = [
    {"name": "New York, NY", "country": "USA", "state": "New York", "category": "major_city",
     "bbox": [-74.26, 40.49, -73.70, 40.92]},
    {"name": "Los Angeles, CA", "country": "USA", "state": "California", "category": "major_city",
     "bbox": [-118.67, 33.70, -117.68, 34.34]},
    {"name": "Chicago, IL", "country": "USA", "state": "Illinois", "category": "major_city",
     "bbox": [-87.94, 41.64, -87.52, 42.02]},
    {"name": "Houston, TX", "country": "USA", "state": "Texas", "category": "major_city",
     "bbox": [-95.79, 29.52, -95.01, 30.11]},
    {"name": "Phoenix, AZ", "country": "USA", "state": "Arizona", "category": "migration_hotspot",
     "bbox": [-112.32, 33.29, -111.93, 33.70]},
    {"name": "Philadelphia, PA", "country": "USA", "state": "Pennsylvania", "category": "major_city",
     "bbox": [-75.28, 39.87, -74.96, 40.14]},
    {"name": "San Antonio, TX", "country": "USA", "state": "Texas", "category": "major_city",
     "bbox": [-98.73, 29.23, -98.29, 29.65]},
    {"name": "San Diego, CA", "country": "USA", "state": "California", "category": "migration_hotspot",
     "bbox": [-117.28, 32.53, -116.91, 33.11]},
    {"name": "Dallas, TX", "country": "USA", "state": "Texas", "category": "major_city",
     "bbox": [-97.00, 32.62, -96.46, 33.02]},
    {"name": "San Jose, CA", "country": "USA", "state": "California", "category": "major_city",
     "bbox": [-122.05, 37.13, -121.59, 37.47]},
    {"name": "Austin, TX", "country": "USA", "state": "Texas", "category": "migration_hotspot",
     "bbox": [-97.94, 30.10, -97.56, 30.52]},
    {"name": "San Francisco, CA", "country": "USA", "state": "California", "category": "major_city",
     "bbox": [-122.52, 37.71, -122.36, 37.81]},
    {"name": "Seattle, WA", "country": "USA", "state": "Washington", "category": "major_city",
     "bbox": [-122.44, 47.49, -122.24, 47.73]},
    {"name": "Denver, CO", "country": "USA", "state": "Colorado", "category": "major_city",
     "bbox": [-105.11, 39.61, -104.60, 39.91]},
    {"name": "Boston, MA", "country": "USA", "state": "Massachusetts", "category": "major_city",
     "bbox": [-71.19, 42.23, -70.92, 42.40]},
    {"name": "Las Vegas, NV", "country": "USA", "state": "Nevada", "category": "migration_hotspot",
     "bbox": [-115.42, 36.00, -115.06, 36.30]},
    {"name": "Miami, FL", "country": "USA", "state": "Florida", "category": "migration_hotspot",
     "bbox": [-80.33, 25.71, -80.14, 25.86]},
    {"name": "Tampa, FL", "country": "USA", "state": "Florida", "category": "migration_hotspot",
     "bbox": [-82.65, 27.82, -82.37, 28.07]},
    {"name": "Orlando, FL", "country": "USA", "state": "Florida", "category": "migration_hotspot",
     "bbox": [-81.51, 28.36, -81.22, 28.62]},
    {"name": "Atlanta, GA", "country": "USA", "state": "Georgia", "category": "major_city",
     "bbox": [-84.55, 33.65, -84.29, 33.89]},
]

# Global Megacities
GLOBAL_MEGACITIES = [
    {"name": "Tokyo, Japan", "country": "Japan", "category": "megacity",
     "bbox": [139.56, 35.52, 139.92, 35.82]},
    {"name": "Delhi, India", "country": "India", "category": "megacity",
     "bbox": [76.84, 28.40, 77.35, 28.88]},
    {"name": "Shanghai, China", "country": "China", "category": "megacity",
     "bbox": [121.11, 30.98, 121.80, 31.51]},
    {"name": "Sao Paulo, Brazil", "country": "Brazil", "category": "megacity",
     "bbox": [-46.83, -23.74, -46.37, -23.38]},
    {"name": "Mexico City, Mexico", "country": "Mexico", "category": "megacity",
     "bbox": [-99.36, 19.22, -98.96, 19.59]},
    {"name": "Cairo, Egypt", "country": "Egypt", "category": "megacity",
     "bbox": [31.05, 29.87, 31.43, 30.17]},
    {"name": "Mumbai, India", "country": "India", "category": "megacity",
     "bbox": [72.77, 18.89, 72.99, 19.27]},
    {"name": "Beijing, China", "country": "China", "category": "megacity",
     "bbox": [116.17, 39.76, 116.58, 40.03]},
    {"name": "London, UK", "country": "United Kingdom", "category": "megacity",
     "bbox": [-0.51, 51.28, 0.33, 51.69]},
    {"name": "Paris, France", "country": "France", "category": "megacity",
     "bbox": [2.22, 48.81, 2.47, 48.90]},
]


def bbox_to_polygon(bbox: list[float]) -> dict:
    """Convert a bounding box to a GeoJSON Polygon."""
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]]
    }


async def seed_regions():
    """Seed the database with predefined regions."""
    import sys
    sys.path.insert(0, "/app")

    from sqlalchemy import text
    from geoalchemy2.functions import ST_GeomFromGeoJSON

    from app.core.database import get_db_context
    from app.models.region import Region

    all_regions = US_MAJOR_CITIES + GLOBAL_MEGACITIES

    async with get_db_context() as db:
        # Check if regions already exist
        result = await db.execute(
            text("SELECT COUNT(*) FROM regions WHERE type = 'predefined'")
        )
        count = result.scalar()

        if count > 0:
            print(f"Found {count} existing predefined regions. Skipping seed.")
            return

        print(f"Seeding {len(all_regions)} predefined regions...")

        for region_data in all_regions:
            geometry = bbox_to_polygon(region_data["bbox"])
            geojson_str = json.dumps(geometry)

            region = Region(
                name=region_data["name"],
                description=f"Predefined region for {region_data['name']}",
                geometry=ST_GeomFromGeoJSON(geojson_str),
                type="predefined",
                country=region_data["country"],
                state_province=region_data.get("state"),
                category=region_data["category"],
            )
            db.add(region)
            print(f"  Added: {region_data['name']}")

        await db.commit()
        print(f"Successfully seeded {len(all_regions)} regions.")


if __name__ == "__main__":
    asyncio.run(seed_regions())
