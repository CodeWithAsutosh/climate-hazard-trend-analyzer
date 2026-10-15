import type { AnalysisRequestBody, AnalysisResult, ApiError } from '../types/analysis';

const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export class AnalysisApiError extends Error {
  status: number;
  code: string;
  details: { field: string; message: string }[];
  requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details: { field: string; message: string }[] = [],
    requestId?: string,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export function friendlyMessage(err: unknown): string {
  if (err instanceof AnalysisApiError) {
    if (err.status === 429) return 'Rate limit reached. Please wait a minute and try again.';
    if (err.status === 502 || err.status === 503)
      return 'Weather data provider is temporarily unavailable. Please try again later.';
    if (err.status === 422 || err.status === 400) {
      const first = err.details?.[0];
      return first
        ? `Invalid input (${first.field}): ${first.message}`
        : 'Some inputs are invalid. Please review the highlighted fields.';
    }
    if (err.status === 413) return 'Request is too large. Please shorten the analysis period.';
    return err.message || 'Analysis failed. Please try again.';
  }
  if (err instanceof TypeError) return 'Cannot reach the analysis server. Is the backend running?';
  return 'An unexpected error occurred. Please try again.';
}

function parseError(status: number, payload: unknown): AnalysisApiError {
  const fallback = 'Analysis failed. Please try again.';
  if (payload && typeof payload === 'object' && 'error' in payload) {
    const e = (payload as { error: ApiError }).error;
    return new AnalysisApiError(
      status,
      typeof e.code === 'string' ? e.code : 'request_failed',
      typeof e.message === 'string' ? e.message : fallback,
      Array.isArray(e.details) ? e.details : [],
      typeof e.request_id === 'string' ? e.request_id : undefined,
    );
  }
  return new AnalysisApiError(status, 'request_failed', fallback);
}

export async function postHeatwaveAnalysis(
  body: AnalysisRequestBody,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  const res = await fetch(`${BASE}/api/v1/analysis/heatwaves`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  const contentType = res.headers.get('content-type') ?? '';
  const payload: unknown = contentType.includes('application/json')
    ? await res.json().catch(() => null)
    : null;
  if (!res.ok) throw parseError(res.status, payload);
  return payload as AnalysisResult;
}

export async function getHealth(signal?: AbortSignal): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/v1/health`, { signal });
  if (!res.ok) throw new Error(`health check failed: ${res.status}`);
  return (await res.json()) as { status: string };
}
