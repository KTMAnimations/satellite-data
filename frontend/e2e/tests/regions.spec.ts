import { test, expect } from '@playwright/test';

test.describe('Region Explorer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/regions');
  });

  test('displays region explorer header', async ({ page }) => {
    await expect(page.locator('.region-sidebar h2')).toHaveText('Regions');
  });

  test('shows map container', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('has region search/filter functionality', async ({ page }) => {
    await expect(page.locator('input.search-input')).toBeVisible();
    await expect(page.locator('.region-list')).toBeVisible();
  });

  test('can navigate to region details', async ({ page }) => {
    const regionItem = page.locator('.region-item').first();
    await expect(regionItem).toBeVisible();
    await regionItem.click();

    const viewAnalysis = page.getByRole('button', { name: 'View Analysis' });
    await expect(viewAnalysis).toBeVisible();
    await viewAnalysis.click();

    await expect(page).toHaveURL(/\/analysis\//);
  });

  test('has predefined regions category', async ({ page }) => {
    const typeSelect = page.locator('select.filter-select').first();
    await expect(typeSelect).toBeVisible();

    await typeSelect.selectOption('predefined');
    await expect(page.locator('.region-item').first()).toBeVisible();
    await expect(page.locator('.region-item').first().locator('.region-type')).toHaveText('predefined');
  });

  test('can search regions by name', async ({ page }) => {
    const search = page.locator('input.search-input');
    await expect(search).toBeVisible();

    await search.fill('Phoenix');
    await expect(page.getByText('Phoenix, AZ')).toBeVisible();
  });
});
