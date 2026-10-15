import { describe, expect, it } from 'vitest';
import { analysisToCsv } from '../src/utils/csv';
import type { AnalysisResult } from '../src/types/analysis';

function sample(): AnalysisResult {
  return {
    hazard: 'heatwave',
    region: { type: 'point', latitude: 20, longitude: 85 },
    period: { start_year: 2000, end_year: 2001 },
    definition: {},
    threshold_c: 35.5,
    annual: [
      {
        year: 2000,
        event_count: 2,
        total_heatwave_days: 7,
        mean_duration_days: 3.5,
        max_duration_days: 4,
        mean_intensity_c: 1.2,
        max_intensity_c: 2.1,
        coverage_fraction: 1,
        sufficient_coverage: true,
      },
      {
        year: 2001,
        event_count: 0,
        total_heatwave_days: 0,
        mean_duration_days: null,
        max_duration_days: null,
        mean_intensity_c: null,
        max_intensity_c: null,
        coverage_fraction: 0.5,
        sufficient_coverage: false,
      },
    ],
    summary: {
      direction: 'increasing',
      slope_events_per_year: 1,
      method: 'ols',
      early_period: null,
      late_period: null,
      change_percent: null,
      change_percent_calculable: false,
      caveats: [],
      mann_kendall: {
        trend: 'increasing',
        s: 1,
        p_value: 0.5,
        alpha: 0.05,
        n: 2,
        sens_slope_per_year: 1,
      },
    } as AnalysisResult['summary'],
    quality: { coverage_by_year: [], missing_days: 0, warnings: [] },
    source: {},
    cache: { status: 'hit' },
  };
}

describe('analysisToCsv', () => {
  it('emits header metadata, column header, and one row per year', () => {
    const csv = analysisToCsv(sample());
    expect(csv).toContain('# threshold_c,35.5');
    expect(csv).toContain('# mann_kendall,increasing,p=0.5');
    expect(csv).toContain(
      'year,event_count,total_heatwave_days,mean_duration_days',
    );
    expect(csv).toContain('2000,2,7,3.5,4,1.2,2.1,1,yes');
    expect(csv).toContain('2001,0,0,,,,,0.5,no');
    expect(csv.endsWith('\n')).toBe(true);
  });
});
