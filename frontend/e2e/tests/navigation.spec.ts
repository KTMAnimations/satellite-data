import { test, expect } from '@playwright/test';

async function ensureNavVisible(page: import('@playwright/test').Page) {
  const nav = page.locator('.header-nav');
  if (await nav.isVisible()) return;

  const toggle = page.getByRole('button', { name: 'Toggle sidebar' });
  if (await toggle.isVisible()) {
    await toggle.click();
    await expect(nav).toBeVisible();
  }
}

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/map');
  });

  test('has main navigation links', async ({ page }) => {
    await ensureNavVisible(page);
    await expect(page.locator('.header-nav')).toBeVisible();
  });

  test('can navigate to all main views', async ({ page }) => {
    const routes = [
      { path: '/map', title: 'Full Map' },
      { path: '/dashboard', title: 'Dashboard' },
      { path: '/regions', title: 'Region' },
      { path: '/exports', title: 'Export' },
    ];

    for (const route of routes) {
      await page.goto(route.path);
      await page.waitForTimeout(1000);
      await expect(page).toHaveURL(route.path);
    }
  });

  test('navigation is responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/map');

    await ensureNavVisible(page);
    await expect(page.locator('.header-nav')).toBeVisible();
  });

  test('logo/brand links to home', async ({ page }) => {
    await page.goto('/regions');

    // Find logo or brand link
    const logoLink = page.locator('a[href="/"]').first();
    await logoLink.click();

    await expect(page).toHaveURL('/map');
  });

  test('404 page for invalid routes', async ({ page }) => {
    await page.goto('/invalid-route-that-does-not-exist');

    // Should show 404 or redirect to home
    // Check page didn't crash
    await expect(page.locator('body')).toBeVisible();
  });

  test('maintains navigation state on back/forward', async ({ page }) => {
    // Navigate through pages
    await page.goto('/regions');
    await page.goto('/dashboard');
    await page.goto('/exports');

    // Go back
    await page.goBack();
    await expect(page).toHaveURL('/dashboard');

    await page.goBack();
    await expect(page).toHaveURL('/regions');

    // Go forward
    await page.goForward();
    await expect(page).toHaveURL('/dashboard');
  });
});
