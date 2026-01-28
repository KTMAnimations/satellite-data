import { test, expect, type APIRequestContext } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

type RegionListResponse = {
  regions: Array<{ id: string; name: string }>;
};

async function getRegionIdByName(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.get(`${API_BASE}/regions?page=1&page_size=200`);
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as RegionListResponse;
  const region = data.regions.find((r) => r.name === name);
  expect(region, `Region not found in API: ${name}`).toBeTruthy();
  return region!.id;
}

test.describe('Analysis View', () => {
  let testRegionId = '';

  test.beforeAll(async ({ request }) => {
    testRegionId = await getRegionIdByName(request, 'Phoenix, AZ');
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/analysis/${testRegionId}`);
  });

  test('displays analysis header with region name', async ({ page }) => {
    await page.waitForTimeout(2000);
    const header = page.locator('h1, .analysis-header');
    await expect(header.first()).toBeVisible();
  });

  test('shows metric selector', async ({ page }) => {
    const metricSelector = page.locator('select.metric-select');
    await expect(metricSelector).toBeVisible();
  });

  test('displays time series chart', async ({ page }) => {
    await expect(page.getByText('Activity Over Time')).toBeVisible();
    const chart = page.locator('.chart-card', { hasText: 'Activity Over Time' }).locator('.chart-wrapper svg');
    await expect(chart).toBeVisible();
  });

  test('has date range controls', async ({ page }) => {
    await page.waitForTimeout(2000);
    // Look for date inputs or time slider
    const dateControl = page.locator('input[type="date"], .date-range, .time-slider');
    await expect(dateControl.first()).toBeVisible();
  });

  test('shows map with overlay', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('can switch between metrics', async ({ page }) => {
    // Toggle an additional metric (Parking) and ensure charts still render.
    const parkingToggle = page.locator('label.metric-toggle', { hasText: 'Parking Occupancy' });
    await expect(parkingToggle).toBeVisible();
    await parkingToggle.click();

    const parkingStat = page.locator('.stats-grid .stat-card h5', { hasText: 'Parking Occupancy' });
    await expect(parkingStat).toBeVisible();
  });

  test('has export options', async ({ page }) => {
    await page.waitForTimeout(2000);
    const exportBtn = page.getByRole('button', { name: /export|download/i }).or(
      page.getByRole('link', { name: /export/i })
    );
    await expect(exportBtn.first()).toBeVisible();
  });

  test('shows seasonal comparison when date range spans winter and summer', async ({ page }) => {
    const dateInputs = page.locator('.date-section input[type="date"]');
    await expect(dateInputs).toHaveCount(2);

    await dateInputs.nth(0).fill('2023-01-01');
    await dateInputs.nth(1).fill('2023-12-31');

    await expect(page.getByText('Seasonal Comparison')).toBeVisible({ timeout: 15000 });
  });

  test('can switch to correlation view and see scatter plot', async ({ page }) => {
    await page.getByRole('button', { name: 'Correlation' }).click();
    const chart = page.locator('.correlation-view .chart-wrapper svg');
    await expect(chart).toBeVisible();
  });

  test('can switch to year-over-year view and see chart', async ({ page }) => {
    await page.getByRole('button', { name: /year over year/i }).click();
    const chart = page.locator('.yoy-view .yoy-chart svg');
    await expect(chart).toBeVisible();
  });
});
