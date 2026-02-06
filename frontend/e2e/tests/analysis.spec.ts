import { test, expect, type APIRequestContext } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

type RegionListResponse = {
  regions: Array<{ id: string; name: string }>;
};

async function getRegionIdByName(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.get(`${API_BASE}/regions?page=1&page_size=200&search=${encodeURIComponent(name)}`);
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as RegionListResponse;
  const region = data.regions.find((r) => r.name === name);
  expect(region, `Region not found in API: ${name}`).toBeTruthy();
  return region!.id;
}

test.describe('Analysis View', () => {
  // This suite hits Earth Engine-backed endpoints; keep it serial to avoid
  // overwhelming local resources and to reduce flakiness.
  test.describe.configure({ mode: 'serial' });

  let testRegionId = '';

  test.beforeAll(async ({ request }) => {
    testRegionId = await getRegionIdByName(request, 'New York, NY');
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/analysis/${testRegionId}`);
  });

  test('displays analysis header with region name', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('New York, NY', { timeout: 15000 });
  });

  test('shows metric selector', async ({ page }) => {
    const metricSelector = page.locator('select.metric-select');
    await expect(metricSelector).toBeVisible();
  });

  test('displays time series chart', async ({ page }) => {
    await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    const chart = page.locator('.chart-card', { hasText: 'Activity Over Time' }).locator('.chart-wrapper svg');
    await expect(chart).toBeVisible();
  });

  test('has date range controls', async ({ page }) => {
    // Look for date inputs or time slider
    const dateControl = page.locator('input[type="date"], .date-range, .time-slider');
    await expect(dateControl.first()).toBeVisible({ timeout: 15000 });
  });

  test('shows map with overlay', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('selecting a map metric adds it to charts/stats (Urban Density)', async ({ page }) => {
    const metricSelector = page.locator('select.metric-select');
    await expect(metricSelector).toBeVisible();

    // Pick an always-available metric for this region and verify it appears in the analysis output.
    await metricSelector.selectOption('urban_density');
    await expect(metricSelector).toHaveValue('urban_density');

    // Avoid asserting during a transient loading state.
    await expect(page.getByText('Loading metrics...')).toHaveCount(0, { timeout: 30000 });

    const urbanStat = page.locator('.stats-grid .stat-card h5', { hasText: 'Urban Density' });
    await expect(urbanStat).toBeVisible({ timeout: 30000 });
  });

  test('has export options', async ({ page }) => {
    const exportBtn = page.getByRole('button', { name: /export|download/i }).or(
      page.getByRole('link', { name: /export/i })
    );
    await expect(exportBtn.first()).toBeVisible();
  });

  test('shows seasonal comparison when date range spans winter and summer', async ({ page }) => {
    // Default date range is last 2 years, which should include both seasons.
    await expect(page.getByText('Activity Over Time')).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('Seasonal Comparison')).toBeVisible({ timeout: 30000 });
  });

  test('can switch to correlation view and see scatter plot', async ({ page }) => {
    await page.getByRole('button', { name: 'Correlation' }).click();
    const chart = page.locator('.correlation-view .chart-wrapper svg');
    await expect(chart).toBeVisible({ timeout: 30000 });
  });

  test('can switch to year-over-year view and see chart', async ({ page }) => {
    await page.getByRole('button', { name: /year over year/i }).click();
    const chart = page.locator('.yoy-view .yoy-chart svg');
    await expect(chart).toBeVisible({ timeout: 30000 });
  });
});
