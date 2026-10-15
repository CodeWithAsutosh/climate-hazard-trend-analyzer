import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AnnualRow } from '../types/analysis';

function toCountSeries(annual: AnnualRow[]) {
  return annual.map((a) => ({
    year: a.year,
    events: a.event_count,
    days: a.total_heatwave_days,
  }));
}

function toDurationSeries(annual: AnnualRow[]) {
  return annual.map((a) => ({
    year: a.year,
    meanDuration: a.mean_duration_days,
    maxDuration: a.max_duration_days,
    meanIntensity: a.mean_intensity_c,
  }));
}

export function EventsChart({ annual }: { annual: AnnualRow[] }) {
  const data = toCountSeries(annual).slice(0, 120);
  return (
    <figure>
      <figcaption>Annual heatwave frequency and total heatwave days</figcaption>
      <div style={{ width: '100%', height: 300 }} role="img" aria-label="Bar chart of annual heatwave event counts and total heatwave days">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="events" name="Heatwave events" fill="#c2410c" />
            <Line type="monotone" dataKey="days" name="Heatwave days" stroke="#1d4ed8" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Data table (chart alternative)</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th>Events</th>
                <th>Heatwave days</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.year}>
                  <td>{d.year}</td>
                  <td>{d.events}</td>
                  <td>{d.days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

export function DurationIntensityChart({ annual }: { annual: AnnualRow[] }) {
  const data = toDurationSeries(annual).slice(0, 120);
  return (
    <figure>
      <figcaption>Duration and intensity by year</figcaption>
      <div style={{ width: '100%', height: 300 }} role="img" aria-label="Line chart of mean and max heatwave duration and mean intensity">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" tick={{ fontSize: 12 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="meanDuration" name="Mean duration (days)" stroke="#15803d" dot={false} connectNulls />
            <Line yAxisId="left" type="monotone" dataKey="maxDuration" name="Max duration (days)" stroke="#65a30d" dot={false} connectNulls />
            <Line yAxisId="right" type="monotone" dataKey="meanIntensity" name="Mean intensity (°C above threshold)" stroke="#b91c1c" dot={false} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
