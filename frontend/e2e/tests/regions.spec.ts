import { test, expect } from '@playwright/test';

test.describe('Region Explorer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/regions');
  });

  test('displays region explorer header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Region Explorer');
  });

  test('shows map container', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('has region search/filter functionality', async ({ page }) => {
    // Look for search input or region list
    const regionList = page.locator('.region-list, .regions-sidebar');
    await expect(regionList).toBeVisible();
  });

  test('can navigate to region details', async ({ page }) => {
    // Wait for regions to load
    await page.waitForTimeout(2000);

    // Click on first region card if available
    const regionCard = page.locator('.region-card, .region-item').first();
    if (await regionCard.isVisible()) {
      await regionCard.click();
      // Should navigate to analysis view or show region details
      await page.waitForTimeout(1000);
    }
  });

  test('has predefined regions category', async ({ page }) => {
    // Check for predefined regions section or filter
    const predefinedFilter = page.getByText(/predefined|cities|popular/i);
    await expect(predefinedFilter.first()).toBeVisible();
  });
});
