import { test, expect, type APIRequestContext } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

type RegionListResponse = {
  regions: Array<{ id: string; name: string }>;
};

async function getRegionIdByName(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.get(`${API_BASE}/regions?page=1&page_size=200`);
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as RegionListResponse;
  const region = data.regions.find((r) => r.name === name);
  expect(region, `Region not found in API: ${name}`).toBeTruthy();
  return region!.id;
}

function fillTileTemplate(template: string, z: number, x: number, y: number): string {
  return template.replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y));
}

test.describe('Overlay Tiles', () => {
  test('serves Earth Engine tiles and requests them in the UI', async ({ page }) => {
    test.setTimeout(180_000);

    // Verify the tile template endpoint returns a real Earth Engine URL.
    const templateRes = await page.request.get(
      `${API_BASE}/tiles/template?metric=nightlights&date_bucket=2023-01&granularity=monthly`
    );
    expect(templateRes.ok()).toBeTruthy();
    const templateData = (await templateRes.json()) as { tile_url: string };
    expect(templateData.tile_url).toContain('earthengine.googleapis.com/map/');

    // Fetch a single tile from the returned template (sanity check).
    const tileUrl = fillTileTemplate(templateData.tile_url, 1, 0, 0);
    const tileResp = await page.request.get(tileUrl);
    expect(tileResp.ok()).toBeTruthy();
    expect(tileResp.headers()['content-type']).toContain('image');

    // Now confirm the analysis page actually requests Earth Engine tiles.
    const tileResponses: string[] = [];
    page.on('response', (resp) => {
      const url = resp.url();
      if (url.includes('earthengine.googleapis.com/map/')) {
        tileResponses.push(url);
      }
    });

    const phoenixRegionId = await getRegionIdByName(page.request, 'Phoenix, AZ');
    await page.goto(`/analysis/${phoenixRegionId}`);
    await page.waitForSelector('.leaflet-container', { timeout: 15_000 });

    await expect.poll(() => tileResponses.length, { timeout: 60_000 }).toBeGreaterThan(0);
  });
});
