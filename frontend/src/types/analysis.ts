export type RegionInput =
  | { type: 'point'; latitude: number; longitude: number }
  | {
      type: 'bbox';
      min_lat: number;
      max_lat: number;
      min_lon: number;
      max_lon: number;
    };

export interface AnalysisRequestBody {
  region: RegionInput;
  hazard: 'heatwave';
  start_year: number;
  end_year: number;
  baseline_start_year: number;
  baseline_end_year: number;
}

export interface AnnualRow {
  year: number;
  event_count: number;
  total_heatwave_days: number;
  mean_duration_days: number | null;
  max_duration_days: number | null;
  mean_intensity_c: number | null;
  max_intensity_c: number | null;
  coverage_fraction: number;
  sufficient_coverage: boolean;
}

export interface TrendSummary {
  direction: 'increasing' | 'decreasing' | 'no_clear_trend' | 'insufficient_data';
  slope_events_per_year: number | null;
  method: string;
  early_period: { start_year: number; end_year: number; mean_events: number } | null;
  late_period: { start_year: number; end_year: number; mean_events: number } | null;
  change_percent: number | null;
  change_percent_calculable: boolean;
  caveats: string[];
  mann_kendall?: {
    trend: 'increasing' | 'decreasing' | 'no_trend' | 'insufficient_data';
    s: number | null;
    p_value: number | null;
    alpha: number;
    n: number;
    sens_slope_per_year: number | null;
  };
}

export interface AnalysisResult {
  hazard: string;
  region: Record<string, unknown>;
  period: { start_year: number; end_year: number };
  definition: Record<string, unknown>;
  threshold_c: number | null;
  baseline_observations?: number;
  annual: AnnualRow[];
  summary: TrendSummary;
  quality: {
    coverage_by_year: { year: number; coverage: number; sufficient: boolean }[];
    missing_days: number;
    warnings: string[];
    normalization?: Record<string, unknown>;
  };
  source: Record<string, unknown>;
  cache: { status: string; key?: string };
}

export interface ApiError {
  code: string;
  message: string;
  details?: { field: string; message: string }[];
  request_id?: string;
}
