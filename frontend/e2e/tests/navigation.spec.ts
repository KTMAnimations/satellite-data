import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('has main navigation links', async ({ page }) => {
    // Check navigation exists
    const nav = page.locator('nav, .nav, .navigation');
    await expect(nav.first()).toBeVisible();
  });

  test('can navigate to all main views', async ({ page }) => {
    const routes = [
      { path: '/regions', title: 'Region' },
      { path: '/animation', title: 'Animation' },
      { path: '/export', title: 'Export' },
      { path: '/gallery', title: 'Gallery' },
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
    await page.goto('/');

    // Check for mobile menu or responsive nav
    const nav = page.locator('nav, .nav, .mobile-nav');
    await expect(nav.first()).toBeVisible();
  });

  test('logo/brand links to home', async ({ page }) => {
    await page.goto('/regions');

    // Find logo or brand link
    const logoLink = page.locator('a[href="/"]').first();
    await logoLink.click();

    await expect(page).toHaveURL('/');
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
    await page.goto('/animation');
    await page.goto('/export');

    // Go back
    await page.goBack();
    await expect(page).toHaveURL('/animation');

    await page.goBack();
    await expect(page).toHaveURL('/regions');

    // Go forward
    await page.goForward();
    await expect(page).toHaveURL('/animation');
  });
});
