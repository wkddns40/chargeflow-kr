import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ChargerFeature, FeatureCollection, ViewState } from '../types/charger';
import { bboxFromViewState, toBboxParam, type ViewportSize } from '../lib/geo';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const VIEWPORT_STATIONS_FLAG = import.meta.env.VITE_ENABLE_VIEWPORT_STATIONS ?? 'false';

export const DEFAULT_VIEWPORT_STATION_LIMIT = 2000;

export type ViewportStationsInput = {
  viewState: ViewState;
  viewport: ViewportSize;
  enabled?: boolean;
  limit?: number;
  apiBaseUrl?: string;
};

export type ViewportStationsQueryConfig = {
  bbox: string;
  enabled: boolean;
  limit: number;
  queryKey: readonly ['viewport-stations', string, number, string];
  url: string;
};

export function isViewportStationsFlagEnabled(flagValue: string | undefined): boolean {
  return flagValue === 'true';
}

export function buildViewportStationsUrl(apiBaseUrl: string, bbox: string, limit: number): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  const searchParams = new URLSearchParams({ bbox, limit: String(limit) });
  return `${baseUrl}/api/stations?${searchParams.toString()}`;
}

export function buildViewportStationsQueryConfig({
  viewState,
  viewport,
  enabled = isViewportStationsFlagEnabled(VIEWPORT_STATIONS_FLAG),
  limit = DEFAULT_VIEWPORT_STATION_LIMIT,
  apiBaseUrl = API_BASE_URL,
}: ViewportStationsInput): ViewportStationsQueryConfig {
  const bbox = toBboxParam(bboxFromViewState(viewState, viewport));
  const url = buildViewportStationsUrl(apiBaseUrl, bbox, limit);
  return {
    bbox,
    enabled,
    limit,
    queryKey: ['viewport-stations', bbox, limit, apiBaseUrl] as const,
    url,
  };
}

async function fetchViewportStations(url: string): Promise<FeatureCollection> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Viewport station fetch failed: ${String(response.status)}`);
  }
  return response.json() as Promise<FeatureCollection>;
}

export function useViewportStations(input: ViewportStationsInput): {
  bbox: string;
  enabled: boolean;
  error: unknown;
  isError: boolean;
  isFetching: boolean;
  isLoading: boolean;
  stations: ChargerFeature[];
} {
  const config = useMemo(
    () => buildViewportStationsQueryConfig(input),
    [input.apiBaseUrl, input.enabled, input.limit, input.viewState, input.viewport],
  );
  const query = useQuery({
    queryKey: config.queryKey,
    queryFn: () => fetchViewportStations(config.url),
    enabled: config.enabled,
  });
  const stations = useMemo<ChargerFeature[]>(() => query.data?.features ?? [], [query.data]);

  return {
    bbox: config.bbox,
    enabled: config.enabled,
    error: query.error,
    isError: query.isError,
    isFetching: query.isFetching,
    isLoading: query.isLoading,
    stations,
  };
}
