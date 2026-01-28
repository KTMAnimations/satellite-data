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

test.describe('Compare View', () => {
  let testRegionId = '';

  test.beforeAll(async ({ request }) => {
    testRegionId = await getRegionIdByName(request, 'Phoenix, AZ');
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/compare/${testRegionId}`);
  });

  test('displays temporal comparison header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Temporal Comparison');
  });

  test('shows preset comparison buttons', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for preset buttons
    await expect(page.getByText('Winter vs Summer')).toBeVisible();
    await expect(page.getByText('COVID Impact')).toBeVisible();
    await expect(page.getByText('Year over Year')).toBeVisible();
  });

  test('has period A and period B date inputs', async ({ page }) => {
    const dateInputs = page.locator('input[type="date"]');
    await expect
      .poll(async () => dateInputs.count(), { timeout: 15000 })
      .toBeGreaterThanOrEqual(4); // 2 for each period
  });

  test('shows split-screen map comparison', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });

    // Should have split view with two maps
    const maps = page.locator('.leaflet-container');
    const count = await maps.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('displays comparison results', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Look for results section
    const results = page.locator('.results-section, .comparison-results, .results-card');
    await expect(results.first()).toBeVisible();
  });

  test('shows change percentage indicator', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Look for percentage change display
    const changeIndicator = page.locator('.change-indicator, .change-value').or(
      page.getByText(/%/)
    );
    await expect(changeIndicator.first()).toBeVisible();
  });

  test('can apply preset comparison', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Click on a preset
    await page.getByText('Winter vs Summer').click();
    await page.waitForTimeout(1000);

    // Verify dates updated (no specific check, just no error)
    await expect(page.locator('.error-state')).not.toBeVisible();
  });

  test('has metric selector', async ({ page }) => {
    await page.waitForTimeout(2000);
    const metricSelect = page.locator('.metric-select, select');
    await expect(metricSelect.first()).toBeVisible();
  });
});
