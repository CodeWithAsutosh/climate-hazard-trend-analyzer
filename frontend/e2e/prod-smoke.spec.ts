import { expect, test } from '@playwright/test';

// Production smoke: NO API mocks — exercises the real Vercel frontend,
// real Render backend, real Open-Meteo provider, and real CORS behavior.
// Run: E2E_BASE_URL=https://<vercel-app> npx playwright test prod-smoke
test.describe('production smoke', () => {
  test('full analysis against the live backend', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /climate hazard/i })).toBeVisible();
    await page.screenshot({ path: 'test-results/prod-before.png' });
    await page.getByRole('button', { name: /analyze heatwaves/i }).click();
    await expect(page.getByTestId('results')).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText(/peak year/i)).toBeVisible();
    await page.screenshot({ path: 'test-results/prod-after.png', fullPage: true });
    expect(errors).toEqual([]);
  });
});
