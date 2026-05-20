import type { ChargerFeature } from '../types/charger';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const LLM_SEARCH_FLAG = import.meta.env.VITE_ENABLE_LLM_SEARCH ?? 'false';

export type ChargerSearchFilters = {
  min_kw?: number;
  status?: ChargerFeature['properties']['status'];
  connector_type?: string;
};

export type ChargerSearchCommand = {
  intent: 'find_chargers';
  place: string;
  radius_m: number;
  filters: ChargerSearchFilters;
  sort: 'distance' | 'power' | 'availability';
};

export type ChargerSearchResponse = {
  query: Record<string, unknown>;
  features: ChargerFeature[];
  explanation: {
    applied_filters: string[];
    data_freshness: string;
    source?: string;
    result_limit?: number;
  };
};

export function isLlmSearchFlagEnabled(flagValue: string | undefined): boolean {
  return flagValue === 'true';
}

export function buildChargerSearchUrl(apiBaseUrl = API_BASE_URL): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  return `${baseUrl}/api/search/chargers`;
}

export async function fetchChargerSearch(
  command: ChargerSearchCommand,
  apiBaseUrl = API_BASE_URL,
): Promise<ChargerSearchResponse> {
  const response = await fetch(buildChargerSearchUrl(apiBaseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  });

  if (!response.ok) {
    throw new Error(`Charger search failed: ${String(response.status)}`);
  }

  return response.json() as Promise<ChargerSearchResponse>;
}

export const llmSearchEnabled = isLlmSearchFlagEnabled(LLM_SEARCH_FLAG);
