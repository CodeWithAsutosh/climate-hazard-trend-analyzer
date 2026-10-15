import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import MapPicker, { isValidPoint } from '../src/components/MapPicker';

describe('isValidPoint', () => {
  it('accepts in-range finite coordinates', () => {
    expect(isValidPoint(20, 85)).toBe(true);
    expect(isValidPoint(-90, -180)).toBe(true);
  });

  it('rejects out-of-range, null, and non-finite values', () => {
    expect(isValidPoint(91, 0)).toBe(false);
    expect(isValidPoint(0, 181)).toBe(false);
    expect(isValidPoint(null, 0)).toBe(false);
    expect(isValidPoint(0, Number.NaN)).toBe(false);
  });
});

describe('MapPicker resilience', () => {
  it('degrades gracefully when the map cannot initialize (jsdom)', () => {
    // Leaflet requires layout APIs jsdom lacks; the boundary must keep the
    // form usable instead of crashing. Real map behavior is covered by E2E.
    render(<MapPicker latitude={20} longitude={85} onPick={vi.fn()} />);
    expect(screen.getByTestId('map-fallback')).toBeInTheDocument();
  });
});
