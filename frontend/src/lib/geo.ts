import type { ChargerFeature } from '../types/charger';

export function getValidData(features: ChargerFeature[]): ChargerFeature[] {
  return features.filter((feature) => {
    const [lng, lat] = feature.geometry.coordinates;
    return Number.isFinite(lng) && Number.isFinite(lat) && lng !== 0 && lat !== 0;
  });
}

export function getLatestDataPoint(features: ChargerFeature[]): ChargerFeature | null {
  if (features.length === 0) return null;
  return features.reduce((prev, curr) =>
    prev.properties.status_updated_at > curr.properties.status_updated_at ? prev : curr,
  );
}

export function buildPaths(features: ChargerFeature[]): [number, number][] {
  return features.reduce<[number, number][]>((acc, curr) => {
    const last = acc[acc.length - 1];
    const [lng, lat] = curr.geometry.coordinates;
    if (!last || last[0] !== lng || last[1] !== lat) {
      acc.push([lng, lat]);
    }
    return acc;
  }, []);
}

export function toBboxParam(bounds: { west: number; south: number; east: number; north: number }): string {
  return [bounds.west, bounds.south, bounds.east, bounds.north].map((value) => value.toFixed(6)).join(',');
}
