import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ChargerFeature, FeatureCollection } from '../types/charger';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export type StationsQueryOptions = {
  enabled?: boolean;
};

export function buildStationsUrl(demoMode = DEMO_MODE, apiBaseUrl = API_BASE_URL): string {
  if (demoMode) return '/sample-chargers.json';
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  return `${baseUrl}/api/stations`;
}

async function fetchStations(url: string): Promise<FeatureCollection> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Station fetch failed: ${String(response.status)}`);
  }
  return response.json() as Promise<FeatureCollection>;
}

export function useStations({ enabled = true }: StationsQueryOptions = {}): {
  stations: ChargerFeature[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
} {
  const url = buildStationsUrl();
  const query = useQuery({ queryKey: ['stations', DEMO_MODE, url], queryFn: () => fetchStations(url), enabled });
  const stations = useMemo<ChargerFeature[]>(() => query.data?.features ?? [], [query.data]);

  return {
    stations,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
  };
}
