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

export type NaturalLanguageChargerSearchResponse = ChargerSearchResponse & {
  type: 'search_results';
  input: {
    message: string;
    parser: string;
    place_phrase: string;
    command: ChargerSearchCommand;
  };
};

export type PlaceCandidate = {
  place_id: string;
  name: string;
  place_type: 'station' | 'province' | 'district' | 'subdistrict';
  lon: number;
  lat: number;
  bbox?: {
    west: number;
    south: number;
    east: number;
    north: number;
  };
  region_code?: string;
  matched_alias?: string;
};

export type ChargerSearchClarificationResponse = {
  type: 'clarification_required';
  message: string;
  missing_fields: string[];
  candidates?: PlaceCandidate[];
  command?: ChargerSearchCommand;
};

export type NaturalLanguageSearchResponse =
  | NaturalLanguageChargerSearchResponse
  | ChargerSearchClarificationResponse;

export function isLlmSearchFlagEnabled(flagValue: string | undefined): boolean {
  return flagValue === 'true';
}

export function buildChargerSearchUrl(apiBaseUrl = API_BASE_URL): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  return `${baseUrl}/api/search/chargers`;
}

export function buildNaturalLanguageChargerSearchUrl(apiBaseUrl = API_BASE_URL): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  return `${baseUrl}/api/search/chargers/nl`;
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

export async function fetchNaturalLanguageChargerSearch(
  message: string,
  apiBaseUrl = API_BASE_URL,
): Promise<NaturalLanguageSearchResponse> {
  const response = await fetch(buildNaturalLanguageChargerSearchUrl(apiBaseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`Natural-language charger search failed: ${String(response.status)}`);
  }

  return response.json() as Promise<NaturalLanguageSearchResponse>;
}

export function isNaturalLanguageSearchResult(
  response: NaturalLanguageSearchResponse | undefined,
): response is NaturalLanguageChargerSearchResponse {
  return response?.type === 'search_results';
}

export const llmSearchEnabled = isLlmSearchFlagEnabled(LLM_SEARCH_FLAG);
