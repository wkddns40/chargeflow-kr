import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ChargerFeature, FeatureCollection } from '../types/charger';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function fetchStations(): Promise<FeatureCollection> {
  const url = DEMO_MODE ? '/sample-chargers.json' : `${API_BASE_URL}/api/stations`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Station fetch failed: ${String(response.status)}`);
  }
  return response.json() as Promise<FeatureCollection>;
}

export function useStations(): {
  stations: ChargerFeature[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
} {
  const query = useQuery({ queryKey: ['stations', DEMO_MODE], queryFn: fetchStations });
  const stations = useMemo<ChargerFeature[]>(() => query.data?.features ?? [], [query.data]);

  return {
    stations,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
  };
}
