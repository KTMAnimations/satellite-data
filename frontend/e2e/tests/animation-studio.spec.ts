import { test, expect } from '@playwright/test';

test.describe('Animation Studio', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/animations');
  });

  test('displays animation studio header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Animation Studio');
  });

  test('shows 17 metric cards with granularity badges', async ({ page }) => {
    const metricCards = page.locator('button.metric-card');
    await expect(metricCards).toHaveCount(17);
    await expect(metricCards.first().locator('.granularity-badge')).toBeVisible();
  });

  test('can select a region and see preview map', async ({ page }) => {
    const regionSelect = page.locator('select.region-select');
    await expect(regionSelect).toBeVisible();

    // Wait for regions to load, then select a known region.
    await expect(regionSelect.locator('option', { hasText: 'Phoenix, AZ' })).toHaveCount(1);
    await regionSelect.selectOption({ label: 'Phoenix, AZ' });

    await expect(page.locator('.preview-header h3')).toHaveText('Phoenix, AZ');
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('shows timeline, playback controls, and speed control after selecting region', async ({ page }) => {
    const regionSelect = page.locator('select.region-select');
    await expect(regionSelect).toBeVisible();
    await expect(regionSelect.locator('option', { hasText: 'Phoenix, AZ' })).toHaveCount(1);
    await regionSelect.selectOption({ label: 'Phoenix, AZ' });

    const timeSlider = page.locator('.time-slider');
    await expect(timeSlider).toBeVisible();

    await expect(page.locator('button.play-btn')).toBeVisible();
    await expect(page.locator('.speed-control')).toBeVisible();
    await expect(page.locator('.current-date')).toBeVisible();
  });

  test('can change metric selection', async ({ page }) => {
    const regionSelect = page.locator('select.region-select');
    await expect(regionSelect).toBeVisible();
    await expect(regionSelect.locator('option', { hasText: 'Phoenix, AZ' })).toHaveCount(1);
    await regionSelect.selectOption({ label: 'Phoenix, AZ' });

    const ndviCard = page.locator('button.metric-card', { hasText: 'NDVI' });
    await ndviCard.click();
    await expect(ndviCard).toHaveClass(/active/);
  });
});
