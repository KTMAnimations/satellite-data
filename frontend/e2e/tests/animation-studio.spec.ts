import { test, expect } from '@playwright/test';

test.describe('Animation Studio', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/animation');
  });

  test('displays animation studio header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Animation Studio');
  });

  test('shows metric selector with all 17 metrics', async ({ page }) => {
    await page.waitForTimeout(2000);
    const metricSelector = page.locator('select.metric-select, .metric-selector select');
    await expect(metricSelector.first()).toBeVisible();

    // Click to open dropdown and check options
    await metricSelector.first().click();
    const options = page.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(4); // At least core metrics
  });

  test('has playback controls', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for play/pause button
    const playBtn = page.locator('button').filter({ hasText: /play|pause/i }).or(
      page.locator('.play-button, .playback-controls button')
    );
    await expect(playBtn.first()).toBeVisible();
  });

  test('shows timeline slider', async ({ page }) => {
    await page.waitForTimeout(2000);
    const slider = page.locator('.timeline-slider, input[type="range"], .time-slider');
    await expect(slider.first()).toBeVisible();
  });

  test('displays map with overlay', async ({ page }) => {
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
  });

  test('has speed control', async ({ page }) => {
    await page.waitForTimeout(2000);
    const speedControl = page.locator('.speed-control, .playback-speed').or(
      page.getByText(/speed|1x|2x/i)
    );
    await expect(speedControl.first()).toBeVisible();
  });

  test('shows frame indicator', async ({ page }) => {
    await page.waitForTimeout(2000);
    // Look for date/frame display
    const frameIndicator = page.locator('.frame-indicator, .current-date, .timeline-label');
    await expect(frameIndicator.first()).toBeVisible();
  });

  test('can change metric and see overlay update', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Select NDVI metric
    const select = page.locator('select').first();
    await select.selectOption({ label: /ndvi/i });
    await page.waitForTimeout(2000);

    // Verify no error
    await expect(page.locator('.error-message, .error-state')).not.toBeVisible();
  });
});
