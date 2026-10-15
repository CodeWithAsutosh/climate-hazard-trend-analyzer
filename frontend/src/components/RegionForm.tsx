import { useState } from 'react';
import type { AnalysisRequestBody, RegionInput } from '../types/analysis';
import MapPicker from './MapPicker';

export interface FormValues {
  regionMode: 'point' | 'bbox';
  latitude: string;
  longitude: string;
  minLat: string;
  maxLat: string;
  minLon: string;
  maxLon: string;
  startYear: string;
  endYear: string;
  baselineStart: string;
  baselineEnd: string;
}

export const DEFAULTS: FormValues = {
  regionMode: 'point',
  latitude: '20.0',
  longitude: '85.0',
  minLat: '19.0',
  maxLat: '21.0',
  minLon: '84.0',
  maxLon: '86.0',
  startYear: '1990',
  endYear: '2020',
  baselineStart: '1991',
  baselineEnd: '2020',
};

export function validate(values: FormValues): {
  errors: Record<string, string>;
  body: AnalysisRequestBody | null;
} {
  const errors: Record<string, string> = {};
  const num = (s: string): number | null => {
    if (s.trim() === '') return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  };
  let region: RegionInput | null = null;
  if (values.regionMode === 'point') {
    const lat = num(values.latitude);
    const lon = num(values.longitude);
    if (lat === null || lat < -90 || lat > 90)
      errors.latitude = 'Latitude must be a number between -90 and 90.';
    if (lon === null || lon < -180 || lon > 180)
      errors.longitude = 'Longitude must be a number between -180 and 180.';
    if (!errors.latitude && !errors.longitude)
      region = { type: 'point', latitude: lat as number, longitude: lon as number };
  } else {
    const minLat = num(values.minLat);
    const maxLat = num(values.maxLat);
    const minLon = num(values.minLon);
    const maxLon = num(values.maxLon);
    if (minLat === null || minLat < -90 || minLat > 90) errors.minLat = 'Min latitude: -90 to 90.';
    if (maxLat === null || maxLat < -90 || maxLat > 90) errors.maxLat = 'Max latitude: -90 to 90.';
    if (minLon === null || minLon < -180 || minLon > 180) errors.minLon = 'Min longitude: -180 to 180.';
    if (maxLon === null || maxLon < -180 || maxLon > 180) errors.maxLon = 'Max longitude: -180 to 180.';
    if (!errors.minLat && !errors.maxLat && minLat !== null && maxLat !== null) {
      if (minLat >= maxLat) errors.maxLat = 'Max latitude must exceed min latitude.';
      else if (maxLat - minLat > 5) errors.maxLat = 'Latitude span must be ≤ 5°.';
    }
    if (!errors.minLon && !errors.maxLon && minLon !== null && maxLon !== null) {
      if (minLon >= maxLon) errors.maxLon = 'Max longitude must exceed min longitude.';
      else if (maxLon - minLon > 5) errors.maxLon = 'Longitude span must be ≤ 5°.';
    }
    if (Object.keys(errors).length === 0 && minLat !== null && maxLat !== null && minLon !== null && maxLon !== null) {
      if ((maxLat - minLat) * (maxLon - minLon) > 25)
        errors.maxLon = 'Bounding-box area must be ≤ 25 deg².';
      else region = { type: 'bbox', min_lat: minLat, max_lat: maxLat, min_lon: minLon, max_lon: maxLon };
    }
  }

  const currentYear = new Date().getFullYear();
  const sy = num(values.startYear);
  const ey = num(values.endYear);
  const bs = num(values.baselineStart);
  const be = num(values.baselineEnd);
  if (sy === null || !Number.isInteger(sy) || sy < 1940 || sy > currentYear)
    errors.startYear = `Start year must be an integer, 1940–${currentYear}.`;
  if (ey === null || !Number.isInteger(ey) || ey < 1940 || ey > currentYear)
    errors.endYear = `End year must be an integer, 1940–${currentYear}.`;
  if (!errors.startYear && !errors.endYear && sy !== null && ey !== null) {
    if (sy > ey) errors.endYear = 'End year must be ≥ start year.';
    else if (ey - sy + 1 > 60) errors.endYear = 'Analysis period must be ≤ 60 years.';
  }
  if (bs === null || !Number.isInteger(bs) || bs < 1940 || bs > currentYear)
    errors.baselineStart = `Baseline start must be an integer, 1940–${currentYear}.`;
  if (be === null || !Number.isInteger(be) || be < 1940 || be > currentYear)
    errors.baselineEnd = `Baseline end must be an integer, 1940–${currentYear}.`;
  if (!errors.baselineStart && !errors.baselineEnd && bs !== null && be !== null) {
    if (bs > be) errors.baselineEnd = 'Baseline end must be ≥ baseline start.';
    else if (be - bs + 1 < 5) errors.baselineEnd = 'Baseline must span ≥ 5 years.';
  }

  if (Object.keys(errors).length > 0 || region === null) return { errors, body: null };
  return {
    errors,
    body: {
      region,
      hazard: 'heatwave',
      start_year: sy as number,
      end_year: ey as number,
      baseline_start_year: bs as number,
      baseline_end_year: be as number,
    },
  };
}

interface Props {
  initial?: Partial<FormValues>;
  loading: boolean;
  onSubmit: (body: AnalysisRequestBody) => void;
}

export default function RegionForm({ initial, loading, onSubmit }: Props) {
  const [values, setValues] = useState<FormValues>({ ...DEFAULTS, ...initial });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState(false);

  const set = (k: keyof FormValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setValues((v) => ({ ...v, [k]: e.target.value }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const { errors: errs, body } = validate(values);
    setErrors(errs);
    setTouched(true);
    if (body) onSubmit(body);
  };

  const field = (
    key: keyof FormValues,
    label: string,
    extra?: { type?: string; min?: string; max?: string; step?: string },
  ) => (
    <div className="field">
      <label htmlFor={`f-${key}`}>{label}</label>
      <input
        id={`f-${key}`}
        type={extra?.type ?? 'text'}
        inputMode="decimal"
        value={values[key]}
        onChange={set(key)}
        aria-invalid={touched && errors[key] ? true : undefined}
        aria-describedby={touched && errors[key] ? `f-${key}-err` : undefined}
      />
      {touched && errors[key] && (
        <p className="field-error" id={`f-${key}-err`} role="alert">
          {errors[key]}
        </p>
      )}
    </div>
  );

  return (
    <form onSubmit={submit} noValidate aria-label="Analysis parameters">
      <fieldset>
        <legend>Region</legend>
        <div className="field">
          <label htmlFor="f-regionMode">Location mode</label>
          <select id="f-regionMode" value={values.regionMode} onChange={set('regionMode')}>
            <option value="point">Single point (latitude / longitude)</option>
            <option value="bbox">Custom bounding box</option>
          </select>
        </div>
        {values.regionMode === 'point' ? (
          <>
            <div className="grid2">
              {field('latitude', 'Latitude (-90 to 90)')}
              {field('longitude', 'Longitude (-180 to 180)')}
            </div>
            <MapPicker
              latitude={values.latitude.trim() === '' ? null : Number(values.latitude)}
              longitude={
                values.longitude.trim() === '' ? null : Number(values.longitude)
              }
              onPick={(lat, lon) =>
                setValues((v) => ({
                  ...v,
                  latitude: String(lat),
                  longitude: String(lon),
                }))
              }
            />
          </>
        ) : (
          <>
            <div className="grid2">
              {field('minLat', 'Min latitude')}
              {field('maxLat', 'Max latitude')}
            </div>
            <div className="grid2">
              {field('minLon', 'Min longitude')}
              {field('maxLon', 'Max longitude')}
            </div>
            <p className="hint">
              Bounding boxes are limited to a 5° × 5° span (≤ 25 deg²) and are analysed
              via the box centroid grid cell.
            </p>
          </>
        )}
      </fieldset>

      <fieldset>
        <legend>Hazard</legend>
        <div className="field">
          <label htmlFor="f-hazard">Hazard type</label>
          <select id="f-hazard" value="heatwave" disabled aria-describedby="hazard-hint">
            <option value="heatwave">Heatwave (default)</option>
          </select>
          <p className="hint" id="hazard-hint">
            Heatwave is currently the only supported hazard type.
          </p>
        </div>
      </fieldset>

      <fieldset>
        <legend>Period</legend>
        <div className="grid2">
          {field('startYear', 'Start year')}
          {field('endYear', 'End year')}
        </div>
        <div className="grid2">
          {field('baselineStart', 'Baseline start (for 95th percentile)')}
          {field('baselineEnd', 'Baseline end')}
        </div>
        <p className="hint">Default baseline 1991–2020. Analysis period ≤ 60 years.</p>
      </fieldset>

      <button type="submit" disabled={loading} aria-busy={loading}>
        {loading ? 'Analyzing…' : 'Analyze heatwaves'}
      </button>
    </form>
  );
}
