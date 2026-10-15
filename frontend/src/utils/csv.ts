import type { AnalysisResult } from '../types/analysis';

function cell(v: unknown): string {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function analysisToCsv(result: AnalysisResult): string {
  const lines: string[] = [];
  lines.push('# Climate Hazard Trend Analyzer — heatwave analysis export');
  const region = result.region as Record<string, unknown>;
  lines.push(`# region,${cell(JSON.stringify(region))}`);
  lines.push(`# period,${result.period.start_year}-${result.period.end_year}`);
  lines.push(`# threshold_c,${cell(result.threshold_c)}`);
  lines.push(`# trend,${cell(result.summary.direction)}`);
  lines.push(
    `# change_percent,${cell(
      result.summary.change_percent_calculable ? result.summary.change_percent : 'not calculable',
    )}`,
  );
  const mk = result.summary.mann_kendall as
    | { trend: string; p_value: number | null }
    | undefined;
  if (mk) lines.push(`# mann_kendall,${cell(mk.trend)},p=${cell(mk.p_value)}`);
  lines.push(
    'year,event_count,total_heatwave_days,mean_duration_days,max_duration_days,mean_intensity_c,max_intensity_c,coverage_fraction,sufficient_coverage',
  );
  for (const a of result.annual) {
    lines.push(
      [
        a.year,
        a.event_count,
        a.total_heatwave_days,
        cell(a.mean_duration_days),
        cell(a.max_duration_days),
        cell(a.mean_intensity_c),
        cell(a.max_intensity_c),
        a.coverage_fraction,
        a.sufficient_coverage ? 'yes' : 'no',
      ].join(','),
    );
  }
  return lines.join('\n') + '\n';
}

export function downloadCsv(result: AnalysisResult): void {
  const csv = analysisToCsv(result);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `heatwave-${result.period.start_year}-${result.period.end_year}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
