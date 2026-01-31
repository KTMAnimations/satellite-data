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
    await expect(featuredCards).toHaveCount(5);

    // Check specific presets exist
    await expect(page.getByText('Snowbird Migration Pattern')).toBeVisible();
    await expect(page.getByText('COVID-19 Impact Analysis')).toBeVisible();
    await expect(page.getByText('Urban Growth: Phoenix')).toBeVisible();
    await expect(page.getByText('College Town Seasonality')).toBeVisible();
    await expect(page.getByText('Tourist Destination Patterns')).toBeVisible();
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

    // Go back and click View Presets
    await page.goto('/');
    await page.getByRole('link', { name: 'View Presets' }).click();
    await expect(page).toHaveURL('/regions?preset=snowbird');
  });

  test('displays map component', async ({ page }) => {
    // Wait for map to load
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('data sources section is visible', async ({ page }) => {
    const dataSourcesHeading = page.getByRole('heading', { name: 'Data Sources' });
    await expect(dataSourcesHeading).toBeVisible();

    const section = page.locator('section.dashboard-section', { has: dataSourcesHeading });
    await expect(section.getByText('Sentinel-2')).toBeVisible();
    await expect(section.getByText('VIIRS')).toBeVisible();
    await expect(section.getByText('GHSL')).toBeVisible();
  });
});
