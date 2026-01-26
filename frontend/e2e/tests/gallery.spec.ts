import { test, expect } from '@playwright/test';

test.describe('Example Gallery', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/gallery');
  });

  test('displays gallery header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Example Gallery');
  });

  test('shows all 5 preset analyses', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for each preset
    await expect(page.getByText('Snowbird Migration Pattern')).toBeVisible();
    await expect(page.getByText('COVID-19 Impact Analysis')).toBeVisible();
    await expect(page.getByText('Urban Growth: Phoenix')).toBeVisible();
    await expect(page.getByText('College Town Seasonality')).toBeVisible();
    await expect(page.getByText('Tourist Destination Patterns')).toBeVisible();
  });

  test('preset cards have descriptions', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check that descriptions are visible
    await expect(page.getByText(/Track winter population/i)).toBeVisible();
    await expect(page.getByText(/COVID/i).first()).toBeVisible();
  });

  test('preset cards show regions', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for region tags
    await expect(page.getByText('Phoenix, AZ')).toBeVisible();
    await expect(page.getByText('Miami, FL')).toBeVisible();
  });

  test('preset cards show key findings', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for findings sections
    await expect(page.getByText('Key Findings')).toBeVisible();
    await expect(page.getByText(/\+\d+%/)).toBeVisible(); // Percentage change
  });

  test('preset cards have explore button', async ({ page }) => {
    await page.waitForTimeout(2000);

    const exploreButtons = page.getByRole('link', { name: /explore analysis/i });
    expect(await exploreButtons.count()).toBe(5);
  });

  test('shows methodology section', async ({ page }) => {
    await page.waitForTimeout(2000);

    await expect(page.getByText('Methodology')).toBeVisible();
    await expect(page.getByText(/proxy metrics/i)).toBeVisible();
  });

  test('methodology lists data sources', async ({ page }) => {
    await page.waitForTimeout(2000);

    await expect(page.getByText(/Nighttime Lights.*VIIRS/i)).toBeVisible();
    await expect(page.getByText(/NDVI/i)).toBeVisible();
    await expect(page.getByText(/Urban Density/i)).toBeVisible();
  });

  test('can click explore to navigate', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Click first explore button
    const exploreBtn = page.getByRole('link', { name: /explore analysis/i }).first();
    await exploreBtn.click();

    // Should navigate to regions with preset param
    await expect(page).toHaveURL(/\/regions\?preset=/);
  });
});
