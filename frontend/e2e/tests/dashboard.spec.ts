import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays hero section with title', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Satellite Migration Analysis');
  });

  test('shows featured analyses cards', async ({ page }) => {
    const featuredCards = page.locator('.featured-card');
    await expect(featuredCards).toHaveCount(4);

    // Check specific presets exist
    await expect(page.getByText('Snowbird Migration Pattern')).toBeVisible();
    await expect(page.getByText('COVID-19 Impact Analysis')).toBeVisible();
    await expect(page.getByText('Urban Growth')).toBeVisible();
    await expect(page.getByText('College Town Seasonality')).toBeVisible();
  });

  test('displays statistics panel', async ({ page }) => {
    await expect(page.getByText('Predefined Regions')).toBeVisible();
    await expect(page.getByText('Data Coverage')).toBeVisible();
    await expect(page.getByText('Metrics Available')).toBeVisible();
  });

  test('shows quick start guide', async ({ page }) => {
    await expect(page.getByText('Quick Start')).toBeVisible();
    await expect(page.getByText('Select a Region')).toBeVisible();
    await expect(page.getByText('Choose Time Period')).toBeVisible();
    await expect(page.getByText('Analyze Metrics')).toBeVisible();
    await expect(page.getByText('Export Results')).toBeVisible();
  });

  test('has working navigation links', async ({ page }) => {
    // Click Explore Regions button
    await page.getByRole('link', { name: 'Explore Regions' }).click();
    await expect(page).toHaveURL('/regions');

    // Go back and click View Examples
    await page.goto('/');
    await page.getByRole('link', { name: 'View Examples' }).click();
    await expect(page).toHaveURL('/gallery');
  });

  test('displays map component', async ({ page }) => {
    // Wait for map to load
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('data sources section is visible', async ({ page }) => {
    await expect(page.getByText('Data Sources')).toBeVisible();
    await expect(page.getByText('Sentinel-2')).toBeVisible();
    await expect(page.getByText('VIIRS')).toBeVisible();
    await expect(page.getByText('GHSL')).toBeVisible();
  });
});
