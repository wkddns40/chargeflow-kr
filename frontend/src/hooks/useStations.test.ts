import { describe, expect, it } from 'vitest';
import { buildStationsUrl } from './useStations';

describe('buildStationsUrl', () => {
  it('keeps the static demo path by default', () => {
    expect(buildStationsUrl(true, 'http://localhost:8000')).toBe('/sample-chargers.json');
  });

  it('builds the API path when demo mode is disabled', () => {
    expect(buildStationsUrl(false, 'http://localhost:8000/')).toBe('http://localhost:8000/api/stations');
  });
});
