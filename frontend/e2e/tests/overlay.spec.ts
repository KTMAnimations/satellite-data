import { test, expect, type APIRequestContext } from '@playwright/test';
import { METRIC_DEFAULT_GRANULARITY } from '../../src/config/metrics';
import { MAX_MAP_ZOOM } from '../../src/config/map';
import type { Granularity, MetricType } from '../../src/types';

const API_ORIGIN = 'http://localhost:8000';
const API_BASE = `${API_ORIGIN}/api/v1`;

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

function dateBucketForGranularity(granularity: Granularity): string {
  return granularity === 'monthly' ? '2023-01' : '2023-01-01';
}

function latLonToTile(lat: number, lon: number, z: number): { x: number; y: number } {
  const latRad = (lat * Math.PI) / 180;
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  return { x, y };
}

function parseTileZoom(url: string, metric: MetricType): number | null {
  try {
    const pathname = new URL(url).pathname;
    const parts = pathname.split('/');
    const idx = parts.indexOf('tiles');
    if (idx === -1) return null;
    if (parts[idx + 1] !== metric) return null;
    const zStr = parts[idx + 4];
    const z = Number(zStr);
    return Number.isFinite(z) ? z : null;
  } catch {
    return null;
  }
}

test.describe('Overlay Tiles', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    void page;
    // Keep this suite reasonably fast: run once in Chromium.
    if (testInfo.project.name !== 'chromium') test.skip();
  });

  test('serves overlay templates + PNG tiles for every metric', async ({ page }) => {
    test.setTimeout(420_000);

    const metrics = Object.keys(METRIC_DEFAULT_GRANULARITY) as MetricType[];
    expect(metrics.length).toBe(17);

    // Use a US metro coordinate so all datasets have a fair chance of returning data.
    const phoenix = { lat: 33.4484, lon: -112.074 };
    const z = 14;
    const { x, y } = latLonToTile(phoenix.lat, phoenix.lon, z);

    for (const metric of metrics) {
      const granularity = METRIC_DEFAULT_GRANULARITY[metric];
      const dateBucket = dateBucketForGranularity(granularity);

      const t0 = Date.now();
      const templateRes = await page.request.get(
        `${API_BASE}/tiles/template?metric=${metric}&date_bucket=${dateBucket}&granularity=${granularity}`
      );
      const templateMs = Date.now() - t0;
      expect(templateRes.ok(), `template failed (${metric})`).toBeTruthy();
      expect(templateMs, `template too slow (${metric}): ${templateMs}ms`).toBeLessThan(20_000);

      const templateData = (await templateRes.json()) as { tile_url: string };
      expect(templateData.tile_url).toContain(`/api/v1/tiles/${metric}/${granularity}/${dateBucket}/`);
      expect(templateData.tile_url).toContain('{z}');

      const tilePath = fillTileTemplate(templateData.tile_url, z, x, y);
      const tileUrl = tilePath.startsWith('http') ? tilePath : `${API_ORIGIN}${tilePath}`;
      const t1 = Date.now();
      const tileResp = await page.request.get(tileUrl);
      const tileMs = Date.now() - t1;

      expect(tileResp.ok(), `tile failed (${metric})`).toBeTruthy();
      expect(tileResp.headers()['content-type']).toContain('image');
      expect(tileMs, `tile too slow (${metric}): ${tileMs}ms`).toBeLessThan(25_000);
    }
  });

  test('requests higher-zoom overlay tiles when zooming the map', async ({ page }) => {
    test.setTimeout(240_000);

    const metric: MetricType = 'ndvi';
    const seenZooms = new Set<number>();

    page.on('request', (req) => {
      const z = parseTileZoom(req.url(), metric);
      if (z !== null) seenZooms.add(z);
    });

    const phoenixRegionId = await getRegionIdByName(page.request, 'Phoenix, AZ');
    await page.goto(`/analysis/${phoenixRegionId}`);
    await page.waitForSelector('.leaflet-container', { timeout: 15_000 });

    const metricSelect = page.locator('select.metric-select');
    await expect(metricSelect).toBeVisible();
    await metricSelect.selectOption({ value: metric });
    await expect(metricSelect).toHaveValue(metric);

    await page.waitForFunction(
      () => {
        const w = window as unknown as { __satelliteLeafletMap?: unknown };
        return Boolean(w.__satelliteLeafletMap);
      },
      undefined,
      { timeout: 15_000 }
    );

    // Step through zooms and ensure we see overlay tile requests at each zoom.
    const zMid = 12;
    const zHigh = Math.min(14, MAX_MAP_ZOOM);

    await page.evaluate((z) => {
      const w = window as unknown as {
        __satelliteLeafletMap?: { setZoom: (zoom: number, options?: { animate?: boolean }) => void };
      };
      w.__satelliteLeafletMap?.setZoom(z, { animate: false });
    }, zMid);
    await expect.poll(() => seenZooms.has(zMid), { timeout: 60_000 }).toBeTruthy();

    await page.evaluate((z) => {
      const w = window as unknown as {
        __satelliteLeafletMap?: { setZoom: (zoom: number, options?: { animate?: boolean }) => void };
      };
      w.__satelliteLeafletMap?.setZoom(z, { animate: false });
    }, zHigh);
    await expect.poll(() => seenZooms.has(zHigh), { timeout: 60_000 }).toBeTruthy();
  });
});
