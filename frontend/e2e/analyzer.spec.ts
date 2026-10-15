import { expect, test } from '@playwright/test';

const SAMPLE = {
  hazard: 'heatwave',
  region: { type: 'point', latitude: 20, longitude: 85 },
  period: { start_year: 2000, end_year: 2005 },
  definition: {
    baseline_period: { start_year: 2000, end_year: 2005 },
    minimum_consecutive_days: 3,
  },
  threshold_c: 35.5,
  annual: [2000, 2001, 2002, 2003, 2004, 2005].map((year, i) => ({
    year,
    event_count: i,
    total_heatwave_days: i * 4,
    mean_duration_days: i === 0 ? null : 4,
    max_duration_days: i === 0 ? null : 5,
    mean_intensity_c: i === 0 ? null : 1.5,
    max_intensity_c: i === 0 ? null : 2.5,
    coverage_fraction: 1,
    sufficient_coverage: true,
  })),
  summary: {
    direction: 'increasing',
    slope_events_per_year: 1,
    method: 'ols',
    early_period: { start_year: 2000, end_year: 2002, mean_events: 1 },
    late_period: { start_year: 2003, end_year: 2005, mean_events: 4 },
    change_percent: 300,
    change_percent_calculable: true,
    caveats: ['descriptive trend only'],
  },
  quality: {
    coverage_by_year: [],
    missing_days: 0,
    warnings: ['2001: coverage 85.0% below 90% advisory level'],
  },
  source: { attribution: 'Weather data by Open-Meteo.com (CC-BY 4.0)' },
  cache: { status: 'miss' },
};

test.describe('heatwave analysis journey', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/analysis/heatwaves', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SAMPLE),
      });
    });
    await page.goto('/');
  });

  test('heatwave selected by default; full workflow renders results', async ({ page }) => {
    await expect(page.getByLabel(/hazard type/i)).toHaveValue('heatwave');
    await page.getByLabel(/start year/i).fill('2000');
    await page.getByLabel(/end year/i).fill('2005');
    await page.getByRole('button', { name: /analyze heatwaves/i }).click();
    await expect(page.getByTestId('results')).toBeVisible();
    await expect(page.getByText(/peak year/i)).toContainText('2005');
    await expect(page.getByText(/weather data by open-meteo/i).first()).toBeVisible();
    await expect(page.getByRole('alert')).toContainText(/coverage/);
  });

  test('map click sets the point coordinates', async ({ page }) => {
    const lat = page.getByLabel(/latitude/i);
    await expect(lat).toHaveValue('20.0');
    const map = page.locator('.leaflet-container');
    await expect(map).toBeVisible();
    await map.click({ position: { x: 80, y: 60 } });
    await expect(lat).not.toHaveValue('20.0');
  });

  test('invalid input shows validation without a request', async ({ page }) => {
    await page.getByLabel(/latitude/i).fill('999');
    await page.getByRole('button', { name: /analyze heatwaves/i }).click();
    await expect(page.getByText(/latitude must be/i)).toBeVisible();
  });

  test('primary workflow is keyboard accessible', async ({ page }) => {
    await page.getByLabel(/latitude/i).focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(/longitude/i)).toBeFocused();
  });
});

test.describe('failure states', () => {
  test('upstream failure shows recoverable error', async ({ page }) => {
    await page.route('**/api/v1/analysis/heatwaves', async (route) => {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'upstream_error', message: 'provider down' } }),
      });
    });
    await page.goto('/');
    await page.getByRole('button', { name: /analyze heatwaves/i }).click();
    await expect(page.getByTestId('error-state')).toBeVisible();
  });
});
