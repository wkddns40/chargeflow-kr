import type { ChargerFeature } from '../types/charger';
import type { ViewState } from '../types/charger';
import type { RouteChargingPlanResponse, RouteCoordinate, RoutePlannerRoute } from './routePlanner';

export type RoutePathLayerData = {
  id: string;
  path: RouteCoordinate[];
};

const WEB_MERCATOR_TILE_SIZE = 512;
const WEB_MERCATOR_LAT_LIMIT = 85.051129;
const ROUTE_FIT_PADDING_PX = 96;
const ROUTE_FIT_MIN_ZOOM = 4;
const ROUTE_FIT_MAX_ZOOM = 12;

export function getRouteRecommendationStationIds(result: RouteChargingPlanResponse | null): string[] {
  return result?.recommendations.map((recommendation) => recommendation.station_id) ?? [];
}

export function getRoutePathLayerData(route: RoutePlannerRoute | null): RoutePathLayerData[] {
  if (!route || route.polyline.length < 2) {
    return [];
  }
  return [
    {
      id: route.id ?? 'provided-route',
      path: route.polyline,
    },
  ];
}

export function getRouteFitViewState(
  route: RoutePlannerRoute,
  viewport: { width: number; height: number },
  fallback: ViewState,
): ViewState {
  if (route.polyline.length < 2 || viewport.width <= 0 || viewport.height <= 0) {
    return fallback;
  }

  const bounds = route.polyline.reduce(
    (acc, [longitude, latitude]) => ({
      west: Math.min(acc.west, longitude),
      south: Math.min(acc.south, latitude),
      east: Math.max(acc.east, longitude),
      north: Math.max(acc.north, latitude),
    }),
    { west: Infinity, south: Infinity, east: -Infinity, north: -Infinity },
  );

  if (!Number.isFinite(bounds.west) || !Number.isFinite(bounds.south)) {
    return fallback;
  }

  const centerLongitude = (bounds.west + bounds.east) / 2;
  const centerLatitude = (bounds.south + bounds.north) / 2;
  const westNorth = lngLatToNormalizedWorld(bounds.west, bounds.north);
  const eastSouth = lngLatToNormalizedWorld(bounds.east, bounds.south);
  const spanX = Math.max(Math.abs(eastSouth[0] - westNorth[0]), Number.EPSILON);
  const spanY = Math.max(Math.abs(eastSouth[1] - westNorth[1]), Number.EPSILON);
  const usableWidth = Math.max(1, viewport.width - ROUTE_FIT_PADDING_PX * 2);
  const usableHeight = Math.max(1, viewport.height - ROUTE_FIT_PADDING_PX * 2);
  const zoomX = Math.log2(usableWidth / (WEB_MERCATOR_TILE_SIZE * spanX));
  const zoomY = Math.log2(usableHeight / (WEB_MERCATOR_TILE_SIZE * spanY));
  const zoom = clamp(Math.min(zoomX, zoomY), ROUTE_FIT_MIN_ZOOM, ROUTE_FIT_MAX_ZOOM);

  return {
    longitude: centerLongitude,
    latitude: centerLatitude,
    zoom: Math.round(zoom * 100) / 100,
    pitch: fallback.pitch,
    bearing: fallback.bearing,
  };
}

export function matchRouteRecommendationStations(
  stations: ChargerFeature[],
  recommendationIds: string[],
): ChargerFeature[] {
  const stationsById = new Map(stations.map((station) => [station.properties.charger_id, station]));
  return recommendationIds.flatMap((stationId) => {
    const station = stationsById.get(stationId);
    return station ? [station] : [];
  });
}

export function findRouteRecommendationStation(stations: ChargerFeature[], stationId: string): ChargerFeature | null {
  return stations.find((station) => station.properties.charger_id === stationId) ?? null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function lngLatToNormalizedWorld(longitude: number, latitude: number): [number, number] {
  const clampedLat = clamp(latitude, -WEB_MERCATOR_LAT_LIMIT, WEB_MERCATOR_LAT_LIMIT);
  const sinLat = Math.sin((clampedLat * Math.PI) / 180);
  return [(longitude + 180) / 360, 0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)];
}
