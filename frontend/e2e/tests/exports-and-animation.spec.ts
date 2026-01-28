import { test, expect, type APIRequestContext } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';

async function pollExportStatus(request: APIRequestContext, exportId: string, timeoutMs = 120_000) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const res = await request.get(`${API_BASE}/exports/${exportId}/status`);
    expect(res.ok()).toBeTruthy();
    const data = (await res.json()) as { status: string; format: string; file_size?: number | null };
    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error(`Export failed for ${exportId}`);
    if (Date.now() - start > timeoutMs) throw new Error(`Timed out waiting for export ${exportId}`);
    await new Promise((r) => setTimeout(r, 1000));
  }
}

test.describe('Exports & animation playback', () => {
  test('animation studio: play timeline and export a GIF', async ({ page }) => {
    test.setTimeout(240_000);

    // Export generation + polling is slow; keep this to Chromium only.
    if (test.info().project.name !== 'chromium') test.skip();

    await page.goto('/animations');

    const regionSelect = page.locator('select.region-select');
    await expect(regionSelect).toBeVisible();
    await expect(regionSelect.locator('option', { hasText: 'Tokyo, Japan' })).toHaveCount(1);
    await regionSelect.selectOption({ label: 'Tokyo, Japan' });

    await expect(page.locator('.leaflet-container')).toBeVisible();

    // Verify playback advances the displayed date.
    const currentDate = page.locator('.current-date');
    const before = (await currentDate.innerText()).trim();
    await page.locator('button.play-btn').click();
    await page.waitForTimeout(1500);
    const after = (await currentDate.innerText()).trim();
    expect(after).not.toEqual(before);

    // Trigger export and capture the export id from the API response.
    const exportResponsePromise = page.waitForResponse((resp) => {
      return resp.url().includes('/api/v1/exports/animation') && resp.request().method() === 'POST';
    });
    await page.getByRole('button', { name: 'Export Animation' }).click();

    const exportResponse = await exportResponsePromise;
    expect(exportResponse.ok()).toBeTruthy();
    const exportData = (await exportResponse.json()) as { id: string };
    expect(exportData.id).toBeTruthy();

    // Wait for completion and verify we can download bytes.
    await pollExportStatus(page.request, exportData.id, 180_000);
    const downloadUrl = `${API_BASE}/exports/download/${exportData.id}`;
    const download = await page.request.get(downloadUrl, {
      headers: { Range: 'bytes=0-2047' },
    });
    expect([200, 206]).toContain(download.status());

    const contentRange = download.headers()['content-range'];
    const contentLength = download.headers()['content-length'];

    if (contentRange) {
      const totalSize = Number(contentRange.split('/')[1]);
      expect(totalSize).toBeGreaterThan(10_000);
    } else if (contentLength) {
      expect(Number(contentLength)).toBeGreaterThan(10_000);
    } else {
      // Worst-case: fall back to a tiny body check.
      const body = await download.body();
      expect(body.length).toBeGreaterThan(100);
    }
  });

  test('export center: generate CSV and download it', async ({ page }) => {
    test.setTimeout(240_000);
    if (test.info().project.name !== 'chromium') test.skip();

    await page.goto('/exports');

    // Select region
    const regionSelect = page.locator('select.form-select').first();
    await expect(regionSelect).toBeVisible();
    await expect(regionSelect.locator('option', { hasText: 'Tokyo, Japan' })).toHaveCount(1);
    await regionSelect.selectOption({ label: 'Tokyo, Japan' });

    // Switch to CSV
    await page.getByRole('button', { name: 'CSV Data' }).click();

    const exportResponsePromise = page.waitForResponse((resp) => {
      return resp.url().includes('/api/v1/exports/csv') && resp.request().method() === 'POST';
    });
    await page.getByRole('button', { name: /generate csv/i }).click();

    const exportResponse = await exportResponsePromise;
    expect(exportResponse.ok()).toBeTruthy();
    const exportData = (await exportResponse.json()) as { id: string };
    expect(exportData.id).toBeTruthy();

    await pollExportStatus(page.request, exportData.id, 180_000);
    const download = await page.request.get(`${API_BASE}/exports/download/${exportData.id}`);
    expect(download.ok()).toBeTruthy();
    const text = await download.text();
    expect(text).toContain('date,region,metric,value');
    expect(text.length).toBeGreaterThan(100);
  });
});
