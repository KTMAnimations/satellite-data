"""
Locust performance tests for the Satellite Migration API.

Run with:
    locust -f backend/tests/performance/locustfile.py --host=http://localhost:8000

Or headless:
    locust -f backend/tests/performance/locustfile.py --host=http://localhost:8000 \
        --headless -u 100 -r 10 -t 60s
"""

import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner

# Sample region IDs (replace with actual IDs from your database)
SAMPLE_REGION_IDS = [
    "5ada41b8-c754-4cc6-aada-0a693bf7f5db",
    "29e4ad2f-d119-4e65-8f00-9a7ebdfb6d23",
    "35d00577-08c1-450a-b9fb-af18d12fabd5",
]

# Available metrics
METRICS = [
    "ndvi", "nightlights", "urban_density", "parking",
    "land_cover", "surface_water", "active_fire", "no2",
    "temperature", "precipitation", "aerosol", "cropland",
    "evapotranspiration", "impervious", "fire_historical", "canopy_height"
]

# Sample dates
DATES = ["2024-01", "2024-02", "2024-03", "2024-04"]


class AnonymousUser(HttpUser):
    """Simulates anonymous API users (rate limit: 100 req/min)."""

    wait_time = between(1, 3)
    weight = 3  # 3x more anonymous users than authenticated

    @task(10)
    def health_check(self):
        """Health endpoint - should always be fast."""
        self.client.get("/health")

    @task(5)
    def list_regions(self):
        """List predefined regions."""
        self.client.get("/api/v1/regions?type=predefined&page_size=20")

    @task(3)
    def get_region(self):
        """Get a specific region."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.get(f"/api/v1/regions/{region_id}")

    @task(5)
    def get_metrics(self):
        """Get metrics for a region."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.get(f"/api/v1/metrics/{region_id}")

    @task(2)
    def compare_periods(self):
        """Compare two time periods."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        metric = random.choice(METRICS[:4])  # Core metrics only
        self.client.get(
            f"/api/v1/metrics/{region_id}/compare",
            params={
                "period_a_start": "2023-12-01",
                "period_a_end": "2024-02-28",
                "period_b_start": "2023-06-01",
                "period_b_end": "2023-08-31",
                "metrics": metric,
            }
        )

    @task(8)
    def get_tile(self):
        """Request a map tile."""
        metric = random.choice(METRICS)
        date = random.choice(DATES)
        # Random tile coordinates in US bounds (zoom 11)
        z = 11
        x = random.randint(300, 700)
        y = random.randint(700, 1000)
        self.client.get(f"/api/v1/tiles/us/{metric}/{date}/{z}/{x}/{y}.png")

    @task(1)
    def get_analysis(self):
        """Get analysis for a region."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.get(f"/api/v1/analysis/{region_id}")


class AuthenticatedUser(HttpUser):
    """Simulates authenticated API users (rate limit: 1000 req/min)."""

    wait_time = between(0.5, 2)
    weight = 1

    def on_start(self):
        """Set up API key header."""
        # In real tests, use a valid API key
        self.client.headers["X-API-Key"] = "test-api-key-for-load-testing"

    @task(5)
    def list_regions_with_filter(self):
        """List regions with various filters."""
        self.client.get("/api/v1/regions?type=predefined&page_size=50")
        self.client.get("/api/v1/regions?type=custom&page_size=20")

    @task(10)
    def get_metrics_bulk(self):
        """Get metrics for multiple regions rapidly."""
        for region_id in SAMPLE_REGION_IDS[:2]:
            self.client.get(f"/api/v1/metrics/{region_id}")

    @task(5)
    def compare_all_metrics(self):
        """Compare all metrics for a region."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.get(
            f"/api/v1/metrics/{region_id}/compare",
            params={
                "period_a_start": "2023-12-01",
                "period_a_end": "2024-02-28",
                "period_b_start": "2023-06-01",
                "period_b_end": "2023-08-31",
                "metrics": ",".join(METRICS[:4]),
            }
        )

    @task(15)
    def get_tiles_burst(self):
        """Request multiple tiles rapidly (simulating map pan/zoom)."""
        metric = random.choice(METRICS)
        date = random.choice(DATES)
        z = 11
        base_x = random.randint(350, 650)
        base_y = random.randint(750, 950)

        # Request a 3x3 grid of tiles
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self.client.get(
                    f"/api/v1/tiles/us/{metric}/{date}/{z}/{base_x + dx}/{base_y + dy}.png",
                    name="/api/v1/tiles/us/[metric]/[date]/[z]/[x]/[y].png"
                )

    @task(2)
    def request_pdf_export(self):
        """Request a PDF export."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.post(
            "/api/v1/exports/pdf",
            json={
                "region_id": region_id,
                "format": "pdf",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "metrics": ["ndvi", "nightlights"],
                "include_charts": True,
                "include_maps": True,
            }
        )

    @task(2)
    def request_csv_export(self):
        """Request a CSV export."""
        self.client.post(
            "/api/v1/exports/csv",
            json={
                "region_ids": SAMPLE_REGION_IDS[:2],
                "metrics": ["ndvi", "nightlights"],
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            }
        )

    @task(1)
    def request_animation_export(self):
        """Request an animation export."""
        region_id = random.choice(SAMPLE_REGION_IDS)
        self.client.post(
            "/api/v1/exports/animation",
            json={
                "region_id": region_id,
                "metric": "ndvi",
                "format": "gif",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "frame_duration_ms": 500,
            }
        )


class TileHeavyUser(HttpUser):
    """Simulates users primarily viewing maps (tile-heavy workload)."""

    wait_time = between(0.1, 0.5)
    weight = 2

    @task
    def load_map_view(self):
        """Simulate loading a full map view (many tiles)."""
        metric = random.choice(METRICS)
        date = random.choice(DATES)
        z = 11

        # Center on a US city
        centers = [
            (400, 800),   # West Coast
            (500, 850),   # Mountain
            (550, 900),   # Midwest
            (600, 800),   # Northeast
            (580, 950),   # Southeast
        ]
        center_x, center_y = random.choice(centers)

        # Load 5x5 grid of tiles
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                self.client.get(
                    f"/api/v1/tiles/us/{metric}/{date}/{z}/{center_x + dx}/{center_y + dy}.png",
                    name="/api/v1/tiles/us/[metric]/[date]/[z]/[x]/[y].png"
                )


# Custom event handlers for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when test starts."""
    if isinstance(environment.runner, MasterRunner):
        print("Load test started (master)")
    else:
        print("Load test started")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log summary when test stops."""
    print("\n" + "=" * 50)
    print("LOAD TEST SUMMARY")
    print("=" * 50)

    stats = environment.stats
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Failed Requests: {stats.total.num_failures}")
    print(f"Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Avg Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests/s: {stats.total.total_rps:.2f}")
    print("=" * 50)
