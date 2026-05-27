import type { ChargerFeature, ViewState } from '../types/charger';

const WEB_MERCATOR_TILE_SIZE = 512;
const WEB_MERCATOR_LAT_LIMIT = 85.051129;
const BBOX_FIT_PADDING_PX = 160;
const BBOX_FIT_MIN_ZOOM = 5;
const BBOX_FIT_MAX_ZOOM = 15.5;
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

export type ScreenPosition = {
  x: number;
  y: number;
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

export function getStationScreenPosition(
  feature: ChargerFeature,
  viewState: ViewState,
  viewport: ViewportSize,
): ScreenPosition | null {
  const [longitude, latitude] = feature.geometry.coordinates;
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
    return null;
  }

  const zoom = clamp(viewState.zoom, 0, 24);
  const [centerX, centerY] = lngLatToWorld(viewState.longitude, viewState.latitude, zoom);
  const [pointX, pointY] = lngLatToWorld(longitude, latitude, zoom);

  return {
    x: viewport.width / 2 + pointX - centerX,
    y: viewport.height / 2 + pointY - centerY,
  };
}

export function getBboxFitViewState(bounds: BboxBounds, viewport: ViewportSize, fallback: ViewState): ViewState {
  if (viewport.width <= 0 || viewport.height <= 0 || !isValidBounds(bounds)) {
    return fallback;
  }

  const centerLongitude = (bounds.west + bounds.east) / 2;
  const centerLatitude = (bounds.south + bounds.north) / 2;
  const westNorth = lngLatToNormalizedWorld(bounds.west, bounds.north);
  const eastSouth = lngLatToNormalizedWorld(bounds.east, bounds.south);
  const spanX = Math.max(Math.abs(eastSouth[0] - westNorth[0]), Number.EPSILON);
  const spanY = Math.max(Math.abs(eastSouth[1] - westNorth[1]), Number.EPSILON);
  const usableWidth = Math.max(1, viewport.width - BBOX_FIT_PADDING_PX * 2);
  const usableHeight = Math.max(1, viewport.height - BBOX_FIT_PADDING_PX * 2);
  const zoomX = Math.log2(usableWidth / (WEB_MERCATOR_TILE_SIZE * spanX));
  const zoomY = Math.log2(usableHeight / (WEB_MERCATOR_TILE_SIZE * spanY));
  const zoom = clamp(Math.min(zoomX, zoomY), BBOX_FIT_MIN_ZOOM, BBOX_FIT_MAX_ZOOM);

  return {
    longitude: centerLongitude,
    latitude: centerLatitude,
    zoom: Math.round(zoom * 100) / 100,
    pitch: fallback.pitch,
    bearing: fallback.bearing,
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

function lngLatToNormalizedWorld(longitude: number, latitude: number): [number, number] {
  const [x, y] = lngLatToWorld(longitude, latitude, 0);
  return [x / WEB_MERCATOR_TILE_SIZE, y / WEB_MERCATOR_TILE_SIZE];
}

function isValidBounds(bounds: BboxBounds): boolean {
  return (
    Number.isFinite(bounds.west) &&
    Number.isFinite(bounds.south) &&
    Number.isFinite(bounds.east) &&
    Number.isFinite(bounds.north) &&
    bounds.west <= bounds.east &&
    bounds.south <= bounds.north
  );
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
