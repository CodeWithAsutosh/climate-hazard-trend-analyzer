import { useCallback, useRef, useState } from 'react';
import { friendlyMessage, postHeatwaveAnalysis } from '../api/client';
import type { AnalysisRequestBody, AnalysisResult } from '../types/analysis';
import { downloadCsv } from '../utils/csv';
import InsightSummary from '../components/InsightSummary';
import QualityPanel from '../components/QualityPanel';
import RegionForm from '../components/RegionForm';
import { DurationIntensityChart, EventsChart } from '../components/TrendChart';

type Status = 'idle' | 'loading' | 'success' | 'error';

export default function AnalyzerPage() {
  const [status, setStatus] = useState<Status>('idle');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string>('');
  const [errorKind, setErrorKind] = useState<string>('');
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(
    async (body: AnalysisRequestBody) => {
      if (status === 'loading') return; // duplicate-submission prevention
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setStatus('loading');
      setError('');
      setErrorKind('');
      try {
        const data = await postHeatwaveAnalysis(body, ctrl.signal);
        if (!data || !Array.isArray(data.annual)) throw new Error('Malformed analysis response.');
        setResult(data);
        setStatus('success');
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        const msg = friendlyMessage(e);
        setError(msg);
        setErrorKind(e instanceof Error && 'status' in e ? String((e as { status: number }).status) : '');
        setStatus('error');
      }
    },
    [status],
  );

  const retry = () => {
    setStatus('idle');
    setError('');
  };

  return (
    <main className="container">
      <header>
        <h1>Climate Hazard Trend Analyzer</h1>
        <p>
          Explore historical heatwave frequency, duration, and intensity for a region and
          period. A heatwave is ≥ 3 consecutive days with daily maximum temperature{' '}
          <em>above</em> the region&apos;s 95th-percentile threshold.
        </p>
      </header>

      <div className="layout">
        <div className="controls">
          <RegionForm loading={status === 'loading'} onSubmit={submit} />
        </div>
        <div className="results" aria-live="polite">
          {status === 'idle' && !result && (
            <div className="state" data-testid="empty-state">
              <h2>No analysis yet</h2>
              <p>Choose a region and period, then select “Analyze heatwaves”.</p>
            </div>
          )}
          {status === 'loading' && (
            <div className="state" data-testid="loading-state" role="status">
              <h2>Analyzing…</h2>
              <p>Fetching historical weather and detecting heatwave events.</p>
              <div className="spinner" aria-hidden="true" />
            </div>
          )}
          {status === 'error' && (
            <div className="state error" data-testid="error-state" role="alert">
              <h2>Analysis failed</h2>
              <p>{error}</p>
              {errorKind === '429' && <p>Tip: results are cached — repeating the same query is cheap.</p>}
              <button type="button" onClick={retry}>
                Try again
              </button>
            </div>
          )}
          {status === 'success' && result && (
            <div data-testid="results">
              {result.annual.length === 0 ? (
                <div className="state" data-testid="empty-results">
                  <h2>No annual rows returned</h2>
                  <p>The analysis completed but produced no yearly data.</p>
                </div>
              ) : (
                <>
                  <div className="results-bar">
                    <button type="button" onClick={() => result && downloadCsv(result)}>
                      Export CSV
                    </button>
                  </div>
                  <EventsChart annual={result.annual} />
                  <DurationIntensityChart annual={result.annual} />
                  <InsightSummary result={result} />
                  <QualityPanel result={result} />
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <footer>
        <p>
          Weather data by Open-Meteo.com (CC-BY 4.0). Methodology and limitations are
          disclosed above; trends are descriptive, not causal claims.
        </p>
      </footer>
    </main>
  );
}
