import { test, expect } from '@playwright/test';

test.describe('Analysis View', () => {
  // Use a known region ID for testing
  const testRegionId = '5ada41b8-c754-4cc6-aada-0a693bf7f5db';

  test.beforeEach(async ({ page }) => {
    await page.goto(`/analysis/${testRegionId}`);
  });

  test('displays analysis header with region name', async ({ page }) => {
    await page.waitForTimeout(2000);
    const header = page.locator('h1, .analysis-header');
    await expect(header.first()).toBeVisible();
  });

  test('shows metric selector', async ({ page }) => {
    await page.waitForTimeout(2000);
    // Look for metric toggle or selector
    const metricSelector = page.locator('.metric-toggle, .metric-selector, select');
    await expect(metricSelector.first()).toBeVisible();
  });

  test('displays time series chart', async ({ page }) => {
    await page.waitForTimeout(3000);
    // Look for chart container or SVG
    const chart = page.locator('.chart-container, .time-series-chart, svg');
    await expect(chart.first()).toBeVisible();
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
    await page.waitForTimeout(2000);

    // Find and click metric options
    const metricButtons = page.locator('.metric-toggle button, .metric-option');
    const count = await metricButtons.count();

    if (count > 1) {
      await metricButtons.nth(1).click();
      await page.waitForTimeout(1000);
      // Verify chart/map updates (no error state)
      await expect(page.locator('.error-state')).not.toBeVisible();
    }
  });

  test('has export options', async ({ page }) => {
    await page.waitForTimeout(2000);
    const exportBtn = page.getByRole('button', { name: /export|download/i }).or(
      page.getByRole('link', { name: /export/i })
    );
    await expect(exportBtn.first()).toBeVisible();
  });
});
