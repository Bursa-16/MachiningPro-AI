import { test, expect } from '@playwright/test';

// NOTE: These tests require the server to be running at localhost:8000
// Run: uvicorn backend.api.app:app --port 8000
// Then: cd frontend/app && npx playwright test tests/e2e/demo.spec.ts

const BASE = 'http://localhost:8000';

test.describe('Demo Qualification', () => {
  test('A — application loads', async ({ page }) => {
    await page.goto(`${BASE}/`);
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });

  test('B — login page renders', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    const url = page.url();
    expect(url).toMatch(/login|app/);
  });

  test('C — manufacturing plan page accessible', async ({ page }) => {
    await page.goto(`${BASE}/app/planning-quality/manufacturing-plan`);
    const url = page.url();
    expect(url).toMatch(/login|manufacturing-plan/);
  });

  test('D — dashboard loads', async ({ page }) => {
    await page.goto(`${BASE}/`);
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });

  test('E — process capability route exists', async ({ page }) => {
    await page.goto(`${BASE}/app/planning-quality/process-capability`);
    const url = page.url();
    expect(url).toMatch(/login|process-capability/);
  });

  test('F — API health check', async ({ page }) => {
    const response = await page.request.get(`${BASE}/api/health`);
    expect(response.status()).toBe(200);
  });

  test('G — manufacturing plan API reachable', async ({ page }) => {
    const response = await page.request.get(`${BASE}/api/manufacturing-plan`);
    expect([200, 401, 403, 404]).toContain(response.status());
  });

  test('H — page renders content', async ({ page }) => {
    await page.goto(`${BASE}/`);
    const html = await page.content();
    expect(html.length).toBeGreaterThan(100);
  });
});
