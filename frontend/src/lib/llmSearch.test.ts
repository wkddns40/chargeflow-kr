import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildChargerSearchUrl, fetchChargerSearch, isLlmSearchFlagEnabled } from './llmSearch';
import type { ChargerSearchCommand } from './llmSearch';

const COMMAND: ChargerSearchCommand = {
  intent: 'find_chargers',
  place: 'Gangnam Station',
  radius_m: 2000,
  filters: {
    min_kw: 100,
    status: 'available',
    connector_type: 'DC',
  },
  sort: 'distance',
};

describe('isLlmSearchFlagEnabled', () => {
  it('enables only the explicit true value', () => {
    expect(isLlmSearchFlagEnabled('true')).toBe(true);
    expect(isLlmSearchFlagEnabled('false')).toBe(false);
    expect(isLlmSearchFlagEnabled(undefined)).toBe(false);
  });
});

describe('buildChargerSearchUrl', () => {
  it('builds a relative typed search endpoint by default', () => {
    expect(buildChargerSearchUrl('')).toBe('/api/search/chargers');
  });

  it('builds an absolute typed search endpoint from the API base URL', () => {
    expect(buildChargerSearchUrl('http://localhost:8000/')).toBe('http://localhost:8000/api/search/chargers');
  });
});

describe('fetchChargerSearch', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts the typed command to the backend endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: {},
        features: [],
        explanation: { applied_filters: [], data_freshness: 'file-snapshot' },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await fetchChargerSearch(COMMAND, 'http://localhost:8000');

    expect(response.explanation.data_freshness).toBe('file-snapshot');
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/search/chargers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(COMMAND),
    });
  });

  it('throws on a failed backend response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400 }));

    await expect(fetchChargerSearch(COMMAND)).rejects.toThrow('Charger search failed: 400');
  });
});
