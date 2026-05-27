import { describe, expect, it } from 'vitest';
import {
  bboxFromViewState,
  getBboxFitViewState,
  getStationFocusViewState,
  getStationScreenPosition,
  toBboxParam,
} from './geo';
import type { ChargerFeature, ViewState } from '../types/charger';

const SEOUL_VIEW: ViewState = {
  longitude: 126.978,
  latitude: 37.5665,
  zoom: 11,
  pitch: 0,
  bearing: 0,
};

const STATION: ChargerFeature = {
  type: 'Feature',
  geometry: { type: 'Point', coordinates: [127.0412865, 37.5171756] },
  properties: {
    charger_id: 'station-1',
    charger_name: 'Station 1',
    operator: 'Operator',
    connector_type: 'DC Combo',
    max_kw: 200,
    address: 'Address',
    status: 'available',
    status_updated_at: '2026-05-27T00:00:00+09:00',
  },
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

describe('getStationFocusViewState', () => {
  it('centers and zooms the map around a selected station', () => {
    const viewState = getStationFocusViewState(STATION, SEOUL_VIEW);

    expect(viewState.longitude).toBe(127.0412865);
    expect(viewState.latitude).toBe(37.5171756);
    expect(viewState.zoom).toBeGreaterThan(SEOUL_VIEW.zoom);
    expect(viewState.pitch).toBe(0);
    expect(viewState.bearing).toBe(0);
  });
});

describe('getStationScreenPosition', () => {
  it('projects the selected station to the viewport center after focusing', () => {
    const viewState = getStationFocusViewState(STATION, SEOUL_VIEW);
    const position = getStationScreenPosition(STATION, viewState, { width: 2048, height: 1024 });

    expect(position).toEqual({ x: 1024, y: 512 });
  });
});

describe('getBboxFitViewState', () => {
  it('centers the map on the provided search bbox', () => {
    const viewState = getBboxFitViewState(
      { west: 129.02, south: 35.08, east: 129.08, north: 35.14 },
      { width: 2048, height: 1024 },
      SEOUL_VIEW,
    );

    expect(viewState.longitude).toBeCloseTo(129.05);
    expect(viewState.latitude).toBeCloseTo(35.11);
    expect(viewState.zoom).toBeGreaterThan(SEOUL_VIEW.zoom);
    expect(viewState.pitch).toBe(SEOUL_VIEW.pitch);
    expect(viewState.bearing).toBe(SEOUL_VIEW.bearing);
  });
});
