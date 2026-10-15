import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import type { AnalysisResult } from '../src/types/analysis';

function sampleResult(): AnalysisResult {
  return {
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
      coverage_by_year: [2000, 2001].map((year) => ({ year, coverage: 0.75, sufficient: false })),
      missing_days: 10,
      warnings: ['2000: low data coverage 75.0% below 80% minimum'],
    },
    source: { attribution: 'Weather data by Open-Meteo.com (CC-BY 4.0)' },
    cache: { status: 'miss' },
  };
}

const pendingFetch = () => new Promise(() => {});
const okFetch = (result: AnalysisResult) =>
  async () =>
    new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

describe('AnalyzerPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('selects Heatwave by default', () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(pendingFetch));
    render(<App />);
    const hazard = screen.getByLabelText(/hazard type/i) as HTMLSelectElement;
    expect(hazard.value).toBe('heatwave');
  });

  it('shows validation errors for invalid input', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn());
    render(<App />);
    await user.clear(screen.getByLabelText(/latitude/i));
    await user.type(screen.getByLabelText(/latitude/i), '999');
    await user.click(screen.getByRole('button', { name: /analyze heatwaves/i }));
    expect(await screen.findByText(/latitude must be/i)).toBeInTheDocument();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it('renders charts and summary from the API response', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', okFetch(sampleResult()));
    render(<App />);
    await user.click(screen.getByRole('button', { name: /analyze heatwaves/i }));
    expect(await screen.findByTestId('results')).toBeInTheDocument();
    // values come from the mocked response, not hard-coded fixtures
    expect(screen.getByText(/Peak year:/).textContent).toContain('2005');
    expect(screen.getByText(/Threshold:/).textContent).toContain('35.5');
    expect(screen.getByRole('alert')).toHaveTextContent(/low data coverage/);
  });

  it('prevents duplicate submissions while loading', async () => {
    const user = userEvent.setup();
    const spy = vi.fn().mockImplementation(pendingFetch);
    vi.stubGlobal('fetch', spy);
    render(<App />);
    const btn = screen.getByRole('button', { name: /analyze heatwaves/i });
    await user.click(btn);
    expect(await screen.findByTestId('loading-state')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(btn).toBeDisabled();
  });

  it('shows a rate-limit message on 429', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      async () =>
        new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'slow down' } }), {
          status: 429,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /analyze heatwaves/i }));
    expect(await screen.findByTestId('error-state')).toHaveTextContent(/rate limit/i);
  });

  it('shows a server-error state on 500', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      async () =>
        new Response(JSON.stringify({ error: { code: 'internal_error', message: 'boom' } }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /analyze heatwaves/i }));
    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /try again/i }));
    await waitFor(() => expect(screen.queryByTestId('error-state')).not.toBeInTheDocument());
  });

  it('handles a malformed API response gracefully', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      async () =>
        new Response(JSON.stringify({ hazard: 'heatwave' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    render(<App />);
    await user.click(screen.getByRole('button', { name: /analyze heatwaves/i }));
    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
  });

  it('exposes an empty state before analysis', () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(pendingFetch));
    render(<App />);
    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
  });
});
