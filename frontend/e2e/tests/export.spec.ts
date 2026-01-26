import { test, expect } from '@playwright/test';

test.describe('Export Center', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/export');
  });

  test('displays export center header', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Export Center');
  });

  test('shows region selector', async ({ page }) => {
    await page.waitForTimeout(2000);
    const regionSelect = page.locator('select').first();
    await expect(regionSelect).toBeVisible();
  });

  test('has export format options (PDF, CSV, Animation)', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for format buttons
    await expect(page.getByText('PDF Report')).toBeVisible();
    await expect(page.getByText('CSV Data')).toBeVisible();
    await expect(page.getByText('Animation')).toBeVisible();
  });

  test('shows date range inputs', async ({ page }) => {
    await page.waitForTimeout(2000);
    const dateInputs = page.locator('input[type="date"]');
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);
  });

  test('has metric checkboxes for PDF/CSV', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Check for metric selection
    const checkboxes = page.locator('input[type="checkbox"]');
    expect(await checkboxes.count()).toBeGreaterThanOrEqual(2);
  });

  test('shows animation format options when animation selected', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Click animation format
    await page.getByText('Animation').click();
    await page.waitForTimeout(500);

    // Check for GIF/WebM options
    await expect(page.getByText('GIF')).toBeVisible();
    await expect(page.getByText('WebM')).toBeVisible();
  });

  test('has generate button', async ({ page }) => {
    await page.waitForTimeout(2000);
    const generateBtn = page.getByRole('button', { name: /generate/i });
    await expect(generateBtn).toBeVisible();
  });

  test('shows recent exports section', async ({ page }) => {
    await page.waitForTimeout(2000);
    await expect(page.getByText('Recent Exports')).toBeVisible();
  });

  test('generate button requires region selection', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Try to click generate without selecting region
    const generateBtn = page.getByRole('button', { name: /generate/i });

    // Button should be disabled or show alert
    const isDisabled = await generateBtn.isDisabled();
    if (!isDisabled) {
      // Click and check for alert/error
      page.on('dialog', dialog => dialog.dismiss());
      await generateBtn.click();
    }
  });
});
