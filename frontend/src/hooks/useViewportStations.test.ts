import { describe, expect, it } from 'vitest';
import {
  DEFAULT_VIEWPORT_STATION_LIMIT,
  buildViewportStationsQueryConfig,
  buildViewportStationsUrl,
  isViewportStationsFlagEnabled,
} from './useViewportStations';
import type { ViewState } from '../types/charger';

const VIEW_STATE: ViewState = {
  longitude: 126.978,
  latitude: 37.5665,
  zoom: 11,
  pitch: 0,
  bearing: 0,
};

describe('isViewportStationsFlagEnabled', () => {
  it('enables only the explicit true value', () => {
    expect(isViewportStationsFlagEnabled('true')).toBe(true);
    expect(isViewportStationsFlagEnabled('false')).toBe(false);
    expect(isViewportStationsFlagEnabled(undefined)).toBe(false);
  });
});

describe('buildViewportStationsUrl', () => {
  it('constructs the stations endpoint URL with bbox and limit', () => {
    const url = buildViewportStationsUrl('http://localhost:8000/', '126.000000,33.000000,128.000000,38.000000', 50);

    expect(url).toBe(
      'http://localhost:8000/api/stations?bbox=126.000000%2C33.000000%2C128.000000%2C38.000000&limit=50',
    );
  });

  it('uses a relative URL when no API base URL is configured', () => {
    const url = buildViewportStationsUrl('', '126.000000,33.000000,128.000000,38.000000', 50);

    expect(url).toBe('/api/stations?bbox=126.000000%2C33.000000%2C128.000000%2C38.000000&limit=50');
  });
});

describe('buildViewportStationsQueryConfig', () => {
  it('is disabled by default when the experimental flag is false', () => {
    const config = buildViewportStationsQueryConfig({
      viewState: VIEW_STATE,
      viewport: { width: 1024, height: 768 },
      enabled: false,
      apiBaseUrl: 'http://localhost:8000',
    });

    expect(config.enabled).toBe(false);
    expect(config.limit).toBe(DEFAULT_VIEWPORT_STATION_LIMIT);
    expect(config.url).toContain('/api/stations?bbox=');
    expect(config.queryKey[0]).toBe('viewport-stations');
  });

  it('honors enabled flag and limit overrides', () => {
    const config = buildViewportStationsQueryConfig({
      viewState: VIEW_STATE,
      viewport: { width: 1024, height: 768 },
      enabled: true,
      limit: 75,
      apiBaseUrl: 'http://localhost:8000',
    });

    expect(config.enabled).toBe(true);
    expect(config.limit).toBe(75);
    expect(config.url).toContain('limit=75');
  });
});
