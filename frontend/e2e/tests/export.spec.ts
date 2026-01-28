import { test, expect } from '@playwright/test';

test.describe('Export Center', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/exports');
  });

  test('displays export center header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Export Center');
  });

  test('shows region selector', async ({ page }) => {
    const regionSelect = page.locator('select.form-select').first();
    await expect(regionSelect).toBeVisible();
  });

  test('has export format options (PDF, CSV, Animation)', async ({ page }) => {
    // Check for format buttons
    await expect(page.getByRole('button', { name: 'PDF Report' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'CSV Data' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Animation' })).toBeVisible();
  });

  test('shows date range inputs', async ({ page }) => {
    const dateInputs = page.locator('input[type="date"]');
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);
  });

  test('has metric checkboxes for PDF/CSV', async ({ page }) => {
    // Check for metric selection
    const checkboxes = page.locator('input[type="checkbox"]');
    expect(await checkboxes.count()).toBeGreaterThanOrEqual(2);
  });

  test('shows GIF animation format option when animation selected', async ({ page }) => {
    // Click animation format
    await page.getByRole('button', { name: 'Animation' }).click();

    // Check for GIF option
    await expect(page.getByRole('radio', { name: 'GIF' })).toBeVisible();
  });

  test('has generate button', async ({ page }) => {
    const generateBtn = page.getByRole('button', { name: /generate/i });
    await expect(generateBtn).toBeVisible();
  });

  test('shows recent exports section', async ({ page }) => {
    await expect(page.getByText('Recent Exports')).toBeVisible();
  });

  test('generate button requires region selection', async ({ page }) => {
    const generateBtn = page.getByRole('button', { name: /generate/i });
    await expect(generateBtn).toBeDisabled();
  });
});
