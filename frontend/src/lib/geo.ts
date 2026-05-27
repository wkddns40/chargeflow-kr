import type { ChargerFeature, ViewState } from '../types/charger';

const WEB_MERCATOR_TILE_SIZE = 512;
const WEB_MERCATOR_LAT_LIMIT = 85.051129;
const STATION_FOCUS_ZOOM = 16.5;

export type BboxBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type ViewportSize = {
  width: number;
  height: number;
};

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

export function getStationFocusViewState(feature: ChargerFeature, currentViewState: ViewState): ViewState {
  const [longitude, latitude] = feature.geometry.coordinates;
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
    return currentViewState;
  }

  return {
    ...currentViewState,
    longitude,
    latitude,
    zoom: Math.max(currentViewState.zoom, STATION_FOCUS_ZOOM),
    pitch: 0,
    bearing: 0,
  };
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function worldSizeForZoom(zoom: number): number {
  return WEB_MERCATOR_TILE_SIZE * 2 ** zoom;
}

function lngLatToWorld(longitude: number, latitude: number, zoom: number): [number, number] {
  const worldSize = worldSizeForZoom(zoom);
  const clampedLat = clamp(latitude, -WEB_MERCATOR_LAT_LIMIT, WEB_MERCATOR_LAT_LIMIT);
  const sinLat = Math.sin((clampedLat * Math.PI) / 180);
  const x = ((longitude + 180) / 360) * worldSize;
  const y = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * worldSize;
  return [x, y];
}

function worldToLngLat(x: number, y: number, zoom: number): [number, number] {
  const worldSize = worldSizeForZoom(zoom);
  const longitude = (x / worldSize) * 360 - 180;
  const latitude = (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / worldSize))) * 180) / Math.PI;
  return [longitude, latitude];
}

export function bboxFromViewState(viewState: ViewState, viewport: ViewportSize): BboxBounds {
  if (viewport.width <= 0 || viewport.height <= 0) {
    throw new Error('viewport width and height must be positive');
  }

  const zoom = clamp(viewState.zoom, 0, 24);
  const worldSize = worldSizeForZoom(zoom);
  const [centerX, centerY] = lngLatToWorld(viewState.longitude, viewState.latitude, zoom);
  const westX = clamp(centerX - viewport.width / 2, 0, worldSize);
  const eastX = clamp(centerX + viewport.width / 2, 0, worldSize);
  const northY = clamp(centerY - viewport.height / 2, 0, worldSize);
  const southY = clamp(centerY + viewport.height / 2, 0, worldSize);

  const [west, north] = worldToLngLat(westX, northY, zoom);
  const [east, south] = worldToLngLat(eastX, southY, zoom);
  return { west, south, east, north };
}

export function toBboxParam(bounds: BboxBounds): string {
  return [bounds.west, bounds.south, bounds.east, bounds.north].map((value) => value.toFixed(6)).join(',');
}
