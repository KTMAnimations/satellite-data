import { test, expect, type APIRequestContext } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

const EXPECTED_METRICS = [
  'ndvi',
  'nightlights',
  'urban_density',
  'parking',
  'land_cover',
  'surface_water',
  'active_fire',
  'no2',
  'temperature',
  'precipitation',
  'aerosol',
  'cropland',
  'evapotranspiration',
  'soil_moisture',
  'impervious',
  'fire_historical',
  'canopy_height',
] as const;

const REGION_NAMES = [
  'Phoenix, AZ',
  'Tokyo, Japan',
  'Delhi, India',
  'Shanghai, China',
  'Sao Paulo, Brazil',
  'Mexico City, Mexico',
  'Cairo, Egypt',
  'London, UK',
  'Paris, France',
] as const;

type RegionListResponse = {
  regions: Array<{ id: string; name: string }>;
};

async function getRegionIdByName(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.get(`${API_BASE}/regions?page=1&page_size=100`);
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as RegionListResponse;
  const region = data.regions.find((r) => r.name === name);
  expect(region, `Region not found in API: ${name}`).toBeTruthy();
  return region!.id;
}

test.describe('Global metrics & time periods', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    void page;
    // These tests are intentionally comprehensive; run once in Chromium to keep the suite fast.
    if (testInfo.project.name !== 'chromium') test.skip();
  });

  test('metrics API returns all expected metrics for major global regions', async ({ page }) => {
    const regionsRes = await page.request.get(`${API_BASE}/regions?page=1&page_size=100`);
    expect(regionsRes.ok()).toBeTruthy();
    const regions = (await regionsRes.json()) as RegionListResponse;

    for (const name of REGION_NAMES) {
      const region = regions.regions.find((r) => r.name === name);
      expect(region, `Missing region in seed data: ${name}`).toBeTruthy();

      const metricsRes = await page.request.get(
        `${API_BASE}/metrics/${region!.id}?start_date=2023-01-01&end_date=2024-12-31&granularity=monthly`
      );
      expect(metricsRes.ok(), `Metrics request failed for ${name}`).toBeTruthy();
      const metricsData = (await metricsRes.json()) as {
        metrics: Record<string, { unit: string; data: Array<{ date: string; value: number }> }>;
      };

      for (const metric of EXPECTED_METRICS) {
        expect(metricsData.metrics[metric], `Missing metric ${metric} for ${name}`).toBeTruthy();
        expect(
          metricsData.metrics[metric].data.length,
          `No data points for ${metric} in ${name}`
        ).toBeGreaterThan(0);
      }
    }
  });

  for (const name of REGION_NAMES) {
    test(`analysis view loads and charts render (${name})`, async ({ page }) => {
      const regionId = await getRegionIdByName(page.request, name);

      await page.goto(`/analysis/${regionId}`);
      await expect(page.locator('h1')).toContainText(name.split(',')[0], { timeout: 15000 });
      await page.waitForSelector('.leaflet-container', { timeout: 15000 });

      // Wait for metrics to finish loading and charts to show.
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // Ensure the map metric selector has all metric options.
      const metricSelect = page.locator('select.metric-select');
      await expect(metricSelect).toBeVisible();
      await expect(metricSelect.locator('option')).toHaveCount(17);
    });
  }

  test('date presets reload metrics (US + non-US)', async ({ page }) => {
    const phoenixId = await getRegionIdByName(page.request, 'Phoenix, AZ');
    const tokyoId = await getRegionIdByName(page.request, 'Tokyo, Japan');

    for (const [name, regionId] of [
      ['Phoenix, AZ', phoenixId],
      ['Tokyo, Japan', tokyoId],
    ] as const) {
      await page.goto(`/analysis/${regionId}`);
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // Jan 2024 preset
      await page.getByRole('button', { name: 'Jan 2024' }).click();
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // COVID Era preset
      await page.getByRole('button', { name: 'COVID Era' }).click();
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // Full Archive preset
      await page.getByRole('button', { name: 'Full Archive' }).click();
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // Last Year preset (dynamic end date)
      await page.getByRole('button', { name: 'Last Year' }).click();
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });

      // Sanity check that we did not end up stuck in a loading state.
      await expect(page.getByText('Loading metrics...')).toHaveCount(0);
      await expect(page.locator('h1')).toContainText(name.split(',')[0]);
    }
  });

  test('map metric selector works across metrics (Tokyo) and key metrics (Phoenix)', async ({ page }) => {
    const phoenixId = await getRegionIdByName(page.request, 'Phoenix, AZ');
    const tokyoId = await getRegionIdByName(page.request, 'Tokyo, Japan');

    // Tokyo: switch through all metrics to ensure UI + API wiring works globally.
    await page.goto(`/analysis/${tokyoId}`);
    await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    const metricSelect = page.locator('select.metric-select');
    await expect(metricSelect).toBeVisible();

    for (const metric of EXPECTED_METRICS) {
      await metricSelect.selectOption({ value: metric });
      await expect(metricSelect).toHaveValue(metric);
      await expect(page.locator('.loading-state')).toHaveCount(0, { timeout: 30000 });
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    }

    // Phoenix: exercise a small representative subset that hits daily + monthly tile paths.
    await page.goto(`/analysis/${phoenixId}`);
    await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    const phoenixSelect = page.locator('select.metric-select');
    await expect(phoenixSelect).toBeVisible();

    for (const metric of ['nightlights', 'ndvi', 'active_fire'] as const) {
      await phoenixSelect.selectOption({ value: metric });
      await expect(phoenixSelect).toHaveValue(metric);
      await expect(page.locator('.loading-state')).toHaveCount(0, { timeout: 30000 });
      await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    }
  });
});
