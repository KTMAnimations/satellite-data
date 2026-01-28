#!/usr/bin/env python3
"""
Populate comprehensive observation data for all regions and all 17 metrics.

This script generates realistic synthetic data with seasonal patterns
for testing and demonstration purposes.

Usage:
    docker exec satellite-api python /app/scripts/populate_all_data.py
"""

import asyncio
import math
import random
import sys
from datetime import date, timedelta
from uuid import uuid4

# Ensure app modules are available
sys.path.insert(0, "/app")


# All 17 metrics with their realistic value ranges and seasonal patterns
METRICS_CONFIG = {
    "nightlights": {
        "base_range": (20, 60),  # nW/cm²/sr
        "seasonal_amplitude": 0.15,  # 15% seasonal variation
        "peak_month": 1,  # Peak in winter (January)
        "noise": 0.05,
    },
    "ndvi": {
        "base_range": (0.1, 0.4),  # Vegetation index
        "seasonal_amplitude": 0.4,  # 40% seasonal variation
        "peak_month": 7,  # Peak in summer (July)
        "noise": 0.08,
    },
    "urban_density": {
        "base_range": (0.3, 0.6),  # Ratio 0-1
        "seasonal_amplitude": 0.05,  # 5% variation
        "peak_month": 1,  # Slight winter increase
        "noise": 0.03,
    },
    "parking": {
        "base_range": (0.3, 0.5),  # Occupancy ratio
        "seasonal_amplitude": 0.1,  # 10% variation
        "peak_month": 12,  # Holiday shopping peak
        "noise": 0.05,
    },
    "land_cover": {
        "base_range": (1, 10),  # Land cover class
        "seasonal_amplitude": 0.0,  # Static
        "peak_month": 1,
        "noise": 0.0,
        "static": True,
    },
    "surface_water": {
        "base_range": (0.01, 0.15),  # Water fraction
        "seasonal_amplitude": 0.3,  # 30% variation
        "peak_month": 4,  # Spring peak (snowmelt)
        "noise": 0.1,
    },
    "active_fire": {
        "base_range": (0, 50),  # Fire count
        "seasonal_amplitude": 0.6,  # 60% variation
        "peak_month": 8,  # Late summer peak
        "noise": 0.3,
    },
    "no2": {
        "base_range": (20, 80),  # µmol/m²
        "seasonal_amplitude": 0.2,  # 20% variation
        "peak_month": 1,  # Winter peak (heating)
        "noise": 0.1,
    },
    "temperature": {
        "base_range": (10, 30),  # °C
        "seasonal_amplitude": 0.5,  # 50% variation
        "peak_month": 7,  # Summer peak
        "noise": 0.05,
    },
    "precipitation": {
        "base_range": (20, 100),  # mm/month
        "seasonal_amplitude": 0.4,  # 40% variation
        "peak_month": 6,  # Summer monsoon
        "noise": 0.2,
    },
    "aerosol": {
        "base_range": (0.1, 0.5),  # AOD
        "seasonal_amplitude": 0.25,  # 25% variation
        "peak_month": 3,  # Spring dust
        "noise": 0.1,
    },
    "cropland": {
        "base_range": (0.0, 0.4),  # Cropland fraction
        "seasonal_amplitude": 0.3,  # Growing season
        "peak_month": 7,  # Summer peak
        "noise": 0.05,
    },
    "evapotranspiration": {
        "base_range": (1, 6),  # mm/day
        "seasonal_amplitude": 0.5,  # 50% variation
        "peak_month": 7,  # Summer peak
        "noise": 0.1,
    },
    "soil_moisture": {
        "base_range": (0.1, 0.4),  # m³/m³
        "seasonal_amplitude": 0.3,  # 30% variation
        "peak_month": 4,  # Spring peak
        "noise": 0.08,
    },
    "impervious": {
        "base_range": (0.2, 0.8),  # Impervious fraction
        "seasonal_amplitude": 0.02,  # 2% slight variation
        "peak_month": 1,
        "noise": 0.02,
    },
    "fire_historical": {
        "base_range": (0, 100),  # Historical fire count
        "seasonal_amplitude": 0.5,  # 50% variation
        "peak_month": 8,  # Late summer peak
        "noise": 0.25,
    },
    "canopy_height": {
        "base_range": (5, 25),  # Meters
        "seasonal_amplitude": 0.05,  # 5% growth variation
        "peak_month": 8,  # Late summer
        "noise": 0.02,
    },
}

# City-specific adjustments for more realistic data
CITY_ADJUSTMENTS = {
    # Migration hotspots - higher winter activity (snowbirds)
    "Phoenix, AZ": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.25}},
    "Miami, FL": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.2}},
    "Las Vegas, NV": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.3}},
    "Tampa, FL": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.2}},
    "Orlando, FL": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.2}},
    "San Diego, CA": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.15}},
    "Austin, TX": {"nightlights": {"peak_month": 1, "seasonal_amplitude": 0.15}},

    # Northern cities - lower winter activity
    "New York, NY": {"nightlights": {"peak_month": 7, "seasonal_amplitude": 0.15}},
    "Chicago, IL": {"nightlights": {"peak_month": 7, "seasonal_amplitude": 0.2}},
    "Boston, MA": {"nightlights": {"peak_month": 7, "seasonal_amplitude": 0.18}},
    "Seattle, WA": {"nightlights": {"peak_month": 7, "seasonal_amplitude": 0.15}},

    # Megacities - higher base values
    "Tokyo, Japan": {"nightlights": {"base_range": (40, 80)}, "urban_density": {"base_range": (0.5, 0.8)}},
    "Shanghai, China": {"nightlights": {"base_range": (35, 75)}, "urban_density": {"base_range": (0.5, 0.75)}},
    "London, UK": {"nightlights": {"base_range": (35, 65)}, "ndvi": {"seasonal_amplitude": 0.3}},
    "Paris, France": {"nightlights": {"base_range": (35, 65)}, "ndvi": {"seasonal_amplitude": 0.35}},
    "Delhi, India": {"no2": {"base_range": (40, 120)}, "aerosol": {"base_range": (0.3, 0.8)}},
    "Beijing, China": {"no2": {"base_range": (35, 110)}, "aerosol": {"base_range": (0.25, 0.7)}},
    "Mumbai, India": {"precipitation": {"peak_month": 7, "seasonal_amplitude": 0.7}},  # Monsoon
    "Sao Paulo, Brazil": {"temperature": {"peak_month": 1, "seasonal_amplitude": 0.2}},  # Southern hemisphere
    "Cairo, Egypt": {"precipitation": {"base_range": (0, 20)}, "ndvi": {"base_range": (0.05, 0.2)}},
    "Mexico City, Mexico": {"aerosol": {"base_range": (0.2, 0.6)}},
}


def generate_value(
    metric: str,
    month: int,
    city_name: str,
) -> float:
    """Generate a realistic value for a metric with seasonal variation."""
    config = METRICS_CONFIG[metric].copy()

    # Apply city-specific adjustments
    if city_name in CITY_ADJUSTMENTS:
        city_config = CITY_ADJUSTMENTS[city_name].get(metric, {})
        config.update(city_config)

    base_min, base_max = config["base_range"]
    base_value = (base_min + base_max) / 2
    base_amplitude = (base_max - base_min) / 2

    # Static metrics don't vary
    if config.get("static"):
        return base_value + random.uniform(-base_amplitude * 0.1, base_amplitude * 0.1)

    # Calculate seasonal component
    peak_month = config["peak_month"]
    seasonal_amplitude = config["seasonal_amplitude"]

    # Seasonal variation using cosine (peak at peak_month)
    month_offset = (month - peak_month) * (2 * math.pi / 12)
    seasonal_factor = math.cos(month_offset)

    # Apply seasonal variation
    value = base_value + base_amplitude * seasonal_factor * seasonal_amplitude

    # Add noise
    noise = config["noise"]
    value += random.gauss(0, base_amplitude * noise)

    # Clamp to valid range
    value = max(base_min * 0.8, min(base_max * 1.2, value))

    # Special handling for certain metrics
    if metric == "active_fire":
        value = max(0, int(value))
    elif metric == "fire_historical":
        value = max(0, int(value))
    elif metric == "land_cover":
        value = int(round(value))

    return round(value, 6)


def generate_monthly_dates(start_year: int, end_year: int) -> list[date]:
    """Generate list of monthly dates."""
    dates = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            dates.append(date(year, month, 1))
    return dates


async def populate_data():
    """Populate observations for all regions and metrics."""
    from sqlalchemy import text
    from app.core.database import get_db_context
    from app.models.observation import Observation

    # Date range: 2023-01 to 2025-01
    dates = generate_monthly_dates(2023, 2024)
    dates.append(date(2025, 1, 1))  # Add Jan 2025

    metrics = list(METRICS_CONFIG.keys())

    async with get_db_context() as db:
        # Get all regions
        result = await db.execute(
            text("SELECT id, name FROM regions WHERE type = 'predefined'")
        )
        regions = result.fetchall()

        if not regions:
            print("No regions found. Run seed_regions.py first.")
            return

        print(f"Found {len(regions)} regions")
        print(f"Populating {len(metrics)} metrics for {len(dates)} dates each")
        print(f"Total observations to create: {len(regions) * len(metrics) * len(dates)}")

        # First, clear existing observations
        print("\nClearing existing observations...")
        await db.execute(text("DELETE FROM observations"))
        await db.commit()

        total_created = 0

        for region_id, region_name in regions:
            print(f"\nPopulating data for {region_name}...")
            region_observations = []

            for metric in metrics:
                for d in dates:
                    value = generate_value(metric, d.month, region_name)

                    obs = Observation(
                        id=str(uuid4()),
                        region_id=region_id,
                        date=d,
                        metric=metric,
                        value=value,
                        raster_path=None,
                        extra_data={"source": "synthetic", "version": "1.0"},
                    )
                    region_observations.append(obs)

            db.add_all(region_observations)
            await db.flush()
            total_created += len(region_observations)
            print(f"  Created {len(region_observations)} observations")

        await db.commit()
        print(f"\n✓ Successfully created {total_created} observations")

        # Verify
        result = await db.execute(
            text("SELECT metric, COUNT(*) as count FROM observations GROUP BY metric ORDER BY metric")
        )
        print("\nObservations per metric:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    asyncio.run(populate_data())
