import { test, expect } from '@playwright/test';

test.describe('Full Map', () => {
  test('root redirects to full map', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL('/map');
  });

  test('loads map and timeline controls', async ({ page }) => {
    await page.goto('/map');

    await expect(page.locator('.map-page')).toBeVisible();
    await page.waitForSelector('.leaflet-container', { timeout: 15_000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();

    const metricSelect = page.locator('select.metric-select');
    await expect(metricSelect).toBeVisible();

    const overlayToggle = page.getByRole('button', { name: /overlay/i });
    await expect(overlayToggle).toBeVisible();

    const playBtn = page.locator('button.play-btn');
    await expect(playBtn).toBeVisible();
  });

  test('timeline playback advances the selected date', async ({ page }) => {
    await page.goto('/map');
    await page.waitForSelector('.time-slider svg', { timeout: 15_000 });

    // Disable overlay to avoid playback being blocked while tiles/templates are loading.
    const overlayToggle = page.getByRole('button', { name: /overlay/i });
    await overlayToggle.click();

    const dateLabel = page.locator('.time-slider svg text').first();
    await expect(dateLabel).toBeVisible();

    const before = ((await dateLabel.textContent()) ?? '').trim();
    await page.locator('button.play-btn').click();
    await page.waitForTimeout(1500);
    const after = ((await dateLabel.textContent()) ?? '').trim();

    expect(after).not.toEqual(before);
  });
});
