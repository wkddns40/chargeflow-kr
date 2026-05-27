import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  buildChargerSearchUrl,
  buildNaturalLanguageChargerSearchUrl,
  fetchChargerSearch,
  fetchNaturalLanguageChargerSearch,
  isLlmSearchFlagEnabled,
  isNaturalLanguageSearchResult,
} from './llmSearch';
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

describe('buildNaturalLanguageChargerSearchUrl', () => {
  it('builds a relative natural-language search endpoint by default', () => {
    expect(buildNaturalLanguageChargerSearchUrl('')).toBe('/api/search/chargers/nl');
  });

  it('builds an absolute natural-language search endpoint from the API base URL', () => {
    expect(buildNaturalLanguageChargerSearchUrl('http://localhost:8000/')).toBe(
      'http://localhost:8000/api/search/chargers/nl',
    );
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

describe('fetchNaturalLanguageChargerSearch', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts the free-text message to the backend endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        type: 'search_results',
        input: {
          message: 'Gangnam Station nearby fast chargers',
          parser: 'deterministic-v1',
          place_phrase: 'Gangnam Station',
          command: COMMAND,
        },
        query: {},
        features: [],
        explanation: { applied_filters: [], data_freshness: 'synthetic-snapshot' },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await fetchNaturalLanguageChargerSearch(
      'Gangnam Station nearby fast chargers',
      'http://localhost:8000',
    );

    expect(isNaturalLanguageSearchResult(response)).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/search/chargers/nl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'Gangnam Station nearby fast chargers' }),
    });
  });

  it('returns clarification responses without treating them as search results', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          type: 'clarification_required',
          message: 'Search needs a place. Try: Gangnam Station nearby chargers.',
          missing_fields: ['place'],
        }),
      }),
    );

    const response = await fetchNaturalLanguageChargerSearch('nearby fast chargers');

    expect(isNaturalLanguageSearchResult(response)).toBe(false);
    expect(response.type).toBe('clarification_required');
  });

  it('throws on a failed natural-language backend response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400 }));

    await expect(fetchNaturalLanguageChargerSearch('reserve a charger')).rejects.toThrow(
      'Natural-language charger search failed: 400',
    );
  });
});
