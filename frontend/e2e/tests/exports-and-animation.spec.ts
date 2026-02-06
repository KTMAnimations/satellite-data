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

test.describe('Exports', () => {
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
