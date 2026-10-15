import type { AnalysisResult } from '../types/analysis';

export default function QualityPanel({ result }: { result: AnalysisResult }) {
  const q = result.quality;
  const def = result.definition as Record<string, unknown>;
  return (
    <section aria-label="Data quality and methodology">
      <h2>Data quality &amp; methodology</h2>
      {q.warnings.length > 0 ? (
        <div role="alert" className="warnings">
          <h3>Warnings ({q.warnings.length})</h3>
          <ul>
            {q.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>No data-quality warnings for this analysis.</p>
      )}
      <dl className="meta">
        <dt>Missing days (total)</dt>
        <dd>{q.missing_days}</dd>
        <dt>Cache</dt>
        <dd>{result.cache.status === 'hit' ? 'served from cache' : 'freshly computed'}</dd>
        <dt>Source</dt>
        <dd>{String(result.source.attribution ?? result.source.provider ?? 'unknown')}</dd>
      </dl>
      <h3>Methodology</h3>
      <ul>
        <li>Variable: daily maximum temperature.</li>
        <li>
          Heatwave: ≥ {String(def.minimum_consecutive_days ?? 3)} consecutive valid days
          with tmax strictly above the region 95th-percentile threshold.
        </li>
        <li>Threshold is constant year-round (non-seasonal), computed by linear interpolation.</li>
        <li>Missing or invalid days break a run and are never interpolated.</li>
        <li>Each event is assigned to the year of its start date.</li>
        <li>
          Trend: ordinary-least-squares slope on annual counts; percentage change compares
          late-half vs early-half means. Undefined when the early mean is zero.
        </li>
      </ul>
      <h3>Coverage by year</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Year</th>
              <th>Coverage</th>
              <th>Sufficient</th>
            </tr>
          </thead>
          <tbody>
            {q.coverage_by_year.map((c) => (
              <tr key={c.year}>
                <td>{c.year}</td>
                <td>{(c.coverage * 100).toFixed(1)}%</td>
                <td>{c.sufficient ? 'yes' : 'no'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
