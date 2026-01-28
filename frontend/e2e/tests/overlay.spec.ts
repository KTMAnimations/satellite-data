import { test, expect } from '@playwright/test';

test.describe('Overlay Tiles', () => {
  const phoenixRegionId = 'a6942280-a353-4fdc-a468-3e269354091f';
  const tokyoRegionId = 'e32b6710-1172-4432-989d-e01db382bb6e';

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

  test('serves non-empty world nightlights tiles and requests them for non-US regions', async ({ page }) => {
    test.setTimeout(180_000);

    // Tokyo at z11 roughly maps to x=1818, y=806.
    const tileUrl =
      'http://localhost:8000/api/v1/tiles/world/nightlights/2023-01-01/11/1818/806.png?v=1';

    await expect
      .poll(async () => {
        const resp = await page.request.get(tileUrl);
        if (!resp.ok()) return 0;
        if (!resp.headers()['content-type']?.includes('image/png')) return 0;
        const body = await resp.body();
        return body.length;
      }, { timeout: 150_000 })
      .toBeGreaterThan(1000);

    const tileResponses: string[] = [];
    page.on('response', (resp) => {
      const url = resp.url();
      if (url.includes('/api/v1/tiles/world/nightlights/2023-01-01/') && url.includes('v=1')) {
        tileResponses.push(url);
      }
    });

    await page.goto(`/analysis/${tokyoRegionId}`);
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });

    await expect.poll(() => tileResponses.length, { timeout: 60_000 }).toBeGreaterThan(0);
  });
});
