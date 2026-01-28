import { test, expect } from '@playwright/test';

test.describe('US Overlay Tiles', () => {
  const phoenixRegionId = 'a6942280-a353-4fdc-a468-3e269354091f';

  test('serves non-empty US nightlights tiles and requests them in the UI', async ({ page }) => {
    // Verify the tile endpoint returns a real PNG (not an empty/JSON error response).
    // Phoenix at z11 roughly maps to x=386, y=821.
    const tileUrl =
      'http://localhost:8000/api/v1/tiles/us/nightlights/2023-01-01/11/386/821.png?v=4';

    const tileResponse = await page.request.get(tileUrl);
    expect(tileResponse.ok()).toBeTruthy();
    expect(tileResponse.headers()['content-type']).toContain('image/png');
    const tileBody = await tileResponse.body();
    expect(tileBody.length).toBeGreaterThan(1000);

    // Now confirm the analysis page actually requests US tiles (overlay path).
    const tileResponses: string[] = [];
    page.on('response', (resp) => {
      const url = resp.url();
      if (url.includes('/api/v1/tiles/us/nightlights/2023-01-01/') && url.includes('v=4')) {
        tileResponses.push(url);
      }
    });

    await page.goto(`/analysis/${phoenixRegionId}`);
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });

    await expect.poll(() => tileResponses.length, { timeout: 30000 }).toBeGreaterThan(0);
  });
});

