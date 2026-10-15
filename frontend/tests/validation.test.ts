import { describe, expect, it } from 'vitest';
import { DEFAULTS, validate } from '../src/components/RegionForm';

describe('RegionForm.validate', () => {
  it('accepts valid point input', () => {
    const { errors, body } = validate(DEFAULTS);
    expect(errors).toEqual({});
    expect(body?.region).toEqual({ type: 'point', latitude: 20, longitude: 85 });
    expect(body?.hazard).toBe('heatwave');
  });

  it('rejects latitude out of range', () => {
    const { errors, body } = validate({ ...DEFAULTS, latitude: '91' });
    expect(body).toBeNull();
    expect(errors.latitude).toMatch(/-90/);
  });

  it('rejects non-numeric coordinates', () => {
    const { errors, body } = validate({ ...DEFAULTS, longitude: 'abc' });
    expect(body).toBeNull();
    expect(errors.longitude).toBeDefined();
  });

  it('rejects reversed year range', () => {
    const { errors, body } = validate({ ...DEFAULTS, startYear: '2020', endYear: '1990' });
    expect(body).toBeNull();
    expect(errors.endYear).toMatch(/≥ start year/);
  });

  it('rejects excessively long periods', () => {
    const { errors, body } = validate({ ...DEFAULTS, startYear: '1940', endYear: '2020' });
    expect(body).toBeNull();
    expect(errors.endYear).toMatch(/≤ 60/);
  });

  it('rejects short baselines', () => {
    const { errors, body } = validate({ ...DEFAULTS, baselineStart: '2019', baselineEnd: '2020' });
    expect(body).toBeNull();
    expect(errors.baselineEnd).toMatch(/≥ 5/);
  });

  it('rejects oversized bounding boxes', () => {
    const { errors, body } = validate({
      ...DEFAULTS,
      regionMode: 'bbox',
      minLat: '0',
      maxLat: '10',
      minLon: '0',
      maxLon: '10',
    });
    expect(body).toBeNull();
    expect(errors.maxLat ?? errors.maxLon).toBeDefined();
  });

  it('accepts a valid bbox', () => {
    const { errors, body } = validate({ ...DEFAULTS, regionMode: 'bbox' });
    expect(errors).toEqual({});
    expect(body?.region.type).toBe('bbox');
  });
});
