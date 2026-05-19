import { describe, expect, it } from 'vitest';
import { bboxFromViewState, toBboxParam } from './geo';
import type { ViewState } from '../types/charger';

const SEOUL_VIEW: ViewState = {
  longitude: 126.978,
  latitude: 37.5665,
  zoom: 11,
  pitch: 0,
  bearing: 0,
};

describe('toBboxParam', () => {
  it('serializes bbox values with six decimals', () => {
    expect(toBboxParam({ west: 126, south: 33.1, east: 128.1234567, north: 38.7654321 })).toBe(
      '126.000000,33.100000,128.123457,38.765432',
    );
  });
});

describe('bboxFromViewState', () => {
  it('computes a bbox that contains the viewport center', () => {
    const bbox = bboxFromViewState(SEOUL_VIEW, { width: 1024, height: 768 });

    expect(bbox.west).toBeLessThan(SEOUL_VIEW.longitude);
    expect(bbox.east).toBeGreaterThan(SEOUL_VIEW.longitude);
    expect(bbox.south).toBeLessThan(SEOUL_VIEW.latitude);
    expect(bbox.north).toBeGreaterThan(SEOUL_VIEW.latitude);
  });

  it('rejects empty viewport dimensions', () => {
    expect(() => bboxFromViewState(SEOUL_VIEW, { width: 0, height: 768 })).toThrow('viewport width');
  });
});
