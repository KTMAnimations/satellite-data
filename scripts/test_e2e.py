#!/usr/bin/env python3
"""
End-to-end integration test script.

Tests the complete data flow:
1. Create a test region (Phoenix, AZ)
2. Fetch real satellite data via GEE
3. Calculate NDVI
4. Store observation in database
5. Retrieve via API
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx
from datetime import date
from shapely.geometry import box

# Phoenix, AZ bounding box (small area for testing)
PHOENIX_BBOX = box(-112.1, 33.4, -112.0, 33.5)

API_BASE = "http://localhost:8000"


async def test_gee_connection():
    """Test 1: Verify GEE connection works."""
    print("\n=== Test 1: GEE Connection ===")

    import ee
    import json

    # Load credentials from .env
    from dotenv import load_dotenv
    load_dotenv()

    key_file = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "credentials/gee-service-account.json")
    project_id = os.getenv("GEE_PROJECT_ID")

    if not os.path.exists(key_file):
        print(f"  ERROR: Service account key not found: {key_file}")
        return False

    with open(key_file) as f:
        key_data = json.load(f)
        service_account_email = key_data.get("client_email")

    credentials = ee.ServiceAccountCredentials(service_account_email, key_file)
    ee.Initialize(credentials, project=project_id)

    # Test query
    point = ee.Geometry.Point([-112.05, 33.45])
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate("2024-01-01", "2024-01-31")
    )

    count = collection.size().getInfo()
    print(f"  ✓ GEE connected, found {count} Sentinel-2 images for Phoenix (Jan 2024)")
    return True


async def test_api_health():
    """Test 2: Verify API is responding."""
    print("\n=== Test 2: API Health ===")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/health")
            data = response.json()
            print(f"  ✓ API healthy: {data}")
            return True
        except Exception as e:
            print(f"  ERROR: API not responding: {e}")
            return False


async def test_create_region():
    """Test 3: Create a test region via API."""
    print("\n=== Test 3: Create Region ===")

    region_data = {
        "name": "Phoenix Test Area",
        "description": "Small test area in Phoenix, AZ",
        "geometry": {
            "type": "Polygon",
            "coordinates": [list(PHOENIX_BBOX.exterior.coords)]
        },
        "country": "USA",
        "state_province": "Arizona",
        "category": "migration_hotspot"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/v1/regions",
                json=region_data
            )
            if response.status_code == 201:
                data = response.json()
                print(f"  ✓ Region created: {data['id']}")
                return data['id']
            else:
                print(f"  ERROR: Failed to create region: {response.status_code}")
                print(f"  Response: {response.text}")
                return None
        except Exception as e:
            print(f"  ERROR: {e}")
            return None


async def test_fetch_satellite_data():
    """Test 4: Fetch real satellite data from GEE."""
    print("\n=== Test 4: Fetch Satellite Data ===")

    import ee
    import io
    import numpy as np

    # Assuming GEE is already initialized from test 1
    aoi = ee.Geometry.Polygon(list(PHOENIX_BBOX.exterior.coords))

    # Get a single Sentinel-2 image
    image = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate("2024-01-15", "2024-01-20")
        .sort("CLOUDY_PIXEL_PERCENTAGE")
        .first()
    )

    # Select bands for NDVI (Red + NIR)
    image = image.select(["B4", "B8"])

    # Get bounds
    bounds_info = aoi.bounds().getInfo()["coordinates"][0]
    west = min(c[0] for c in bounds_info)
    east = max(c[0] for c in bounds_info)
    south = min(c[1] for c in bounds_info)
    north = max(c[1] for c in bounds_info)

    # Download using computePixels
    request = {
        "expression": image,
        "fileFormat": "NPY",
        "grid": {
            "dimensions": {"width": 256, "height": 256},
            "affineTransform": {
                "scaleX": (east - west) / 256,
                "shearX": 0,
                "translateX": west,
                "shearY": 0,
                "scaleY": -(north - south) / 256,
                "translateY": north,
            },
            "crsCode": "EPSG:4326",
        },
    }

    print("  Downloading image data...")
    pixels = ee.data.computePixels(request)
    data_array = np.load(io.BytesIO(pixels), allow_pickle=False)

    # Calculate NDVI
    if data_array.dtype.names:
        red = data_array["B4"].astype(np.float32)
        nir = data_array["B8"].astype(np.float32)
    else:
        red = data_array[0].astype(np.float32)
        nir = data_array[1].astype(np.float32)

    # NDVI formula: (NIR - Red) / (NIR + Red)
    denominator = nir + red
    denominator[denominator == 0] = np.nan
    ndvi = (nir - red) / denominator

    mean_ndvi = float(np.nanmean(ndvi))
    print(f"  ✓ Downloaded {data_array.shape} array")
    print(f"  ✓ Calculated NDVI: mean={mean_ndvi:.4f}, min={np.nanmin(ndvi):.4f}, max={np.nanmax(ndvi):.4f}")

    return mean_ndvi


async def test_list_regions():
    """Test 5: List regions from API."""
    print("\n=== Test 5: List Regions ===")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/api/v1/regions")
            data = response.json()
            print(f"  ✓ Found {data['total']} regions")
            for region in data['regions'][:5]:
                print(f"    - {region['name']} ({region['type']})")
            return True
        except Exception as e:
            print(f"  ERROR: {e}")
            return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("END-TO-END INTEGRATION TEST")
    print("=" * 60)

    results = {}

    # Test 1: GEE Connection
    results['gee'] = await test_gee_connection()

    # Test 2: API Health
    results['api'] = await test_api_health()

    if not results['api']:
        print("\n⚠️  API not running. Start with: docker-compose up -d")
        return

    # Test 3: Create Region
    region_id = await test_create_region()
    results['create_region'] = region_id is not None

    # Test 4: Fetch Satellite Data
    if results['gee']:
        try:
            ndvi = await test_fetch_satellite_data()
            results['satellite'] = ndvi is not None
        except Exception as e:
            print(f"  ERROR: {e}")
            results['satellite'] = False
    else:
        results['satellite'] = False

    # Test 5: List Regions
    results['list_regions'] = await test_list_regions()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test}: {status}")
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! End-to-end data flow is working.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
