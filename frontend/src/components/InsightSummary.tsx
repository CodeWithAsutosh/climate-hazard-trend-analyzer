import type { AnalysisResult } from '../types/analysis';

function directionText(d: string): string {
  if (d === 'increasing') return 'increasing';
  if (d === 'decreasing') return 'decreasing';
  if (d === 'no_clear_trend') return 'no clear trend';
  return 'insufficient data for a trend estimate';
}

export default function InsightSummary({ result }: { result: AnalysisResult }) {
  const s = result.summary;
  const totalEvents = result.annual.reduce((n, a) => n + a.event_count, 0);
  const totalDays = result.annual.reduce((n, a) => n + a.total_heatwave_days, 0);
  const mk = result.summary.mann_kendall;
  const peak = result.annual.reduce(
    (best, a) => (a.event_count > best.event_count ? a : best),
    result.annual[0],
  );
  const change =
    s.change_percent_calculable && s.change_percent !== null
      ? `${s.change_percent > 0 ? '+' : ''}${s.change_percent}%`
      : 'not calculable';
  const range =
    s.early_period && s.late_period
      ? ` (early ${s.early_period.start_year}–${s.early_period.end_year} mean ${s.early_period.mean_events} vs late ${s.late_period.start_year}–${s.late_period.end_year} mean ${s.late_period.mean_events})`
      : '';

  return (
    <section aria-label="Summary insights">
      <h2>Summary insights</h2>
      <ul>
        <li>
          Detected <strong>{totalEvents}</strong> heatwave events totalling{' '}
          <strong>{totalDays}</strong> heatwave days over {result.period.start_year}–
          {result.period.end_year}.
        </li>
        {peak && totalEvents > 0 && (
          <li>
            Peak year: <strong>{peak.year}</strong> with {peak.event_count} events (
            {peak.total_heatwave_days} heatwave days).
          </li>
        )}
        <li>
          Trend: <strong>{directionText(s.direction)}</strong>
          {s.slope_events_per_year !== null &&
            ` (slope ${s.slope_events_per_year} events/year)`}
          ; change {change}
          {range}.
        </li>
        <li>
          Threshold: {result.threshold_c !== null ? `${result.threshold_c} °C` : 'n/a'}{' '}
          (95th percentile of daily maximum temperature, baseline{' '}
          {(result.definition.baseline_period as { start_year: number; end_year: number })
            ?.start_year}
          –
          {(result.definition.baseline_period as { start_year: number; end_year: number })
            ?.end_year}
          ).
        </li>
      </ul>
      {mk && mk.trend !== 'insufficient_data' && (
        <p>
          Mann–Kendall test: <strong>{mk.trend.replace('_', ' ')}</strong>
          {mk.p_value !== null && ` (p = ${mk.p_value})`}
          {mk.sens_slope_per_year !== null &&
            `, Sen's slope ${mk.sens_slope_per_year} events/year (n = ${mk.n})`}
          .
        </p>
      )}
      {s.caveats.length > 0 && (
        <>
          <h3>Caveats</h3>
          <ul>
            {s.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}
      <p className="hint">
        Descriptive statistics from the retrieved dataset only; they do not by themselves
        establish causation.
      </p>
    </section>
  );
}
