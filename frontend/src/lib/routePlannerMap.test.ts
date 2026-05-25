import { describe, expect, it } from 'vitest';
import type { ChargerFeature } from '../types/charger';
import {
  getRouteFitViewState,
  getRoutePathLayerData,
  getRouteRecommendationStationIds,
  matchRouteRecommendationStations,
} from './routePlannerMap';
import type { RouteChargingPlanResponse, RoutePlannerRoute } from './routePlanner';

const STATION_A: ChargerFeature = {
  type: 'Feature',
  geometry: { type: 'Point', coordinates: [126.978, 37.5665] },
  properties: {
    charger_id: 'CFL-SYN-001',
    charger_name: 'Station A',
    operator: 'ChargeFlow',
    connector_type: 'DC Combo',
    max_kw: 150,
    address: 'Seoul',
    status: 'available',
    status_updated_at: '2026-05-19T00:00:00Z',
  },
};

const STATION_B: ChargerFeature = {
  ...STATION_A,
  geometry: { type: 'Point', coordinates: [127.0276, 37.4979] },
  properties: {
    ...STATION_A.properties,
    charger_id: 'CFL-SYN-002',
    charger_name: 'Station B',
  },
};

const PLAN_RESULT: RouteChargingPlanResponse = {
  route_id: 'fixture-seoul-daejeon',
  summary: {
    distance_km: 165.2,
    estimated_energy_kwh: 29.736,
    start_soc: 0.64,
    target_arrival_soc: 0.15,
    minimum_required_soc: 0.534,
    reachable_without_stop: true,
  },
  recommendations: [
    {
      station_id: 'CFL-SYN-002',
      name: 'Station B',
      connector_type: 'DC Combo',
      max_kw: 150,
      distance_from_route_km: 0.8,
      route_distance_km: 42.5,
      estimated_arrival_soc: 0.54,
      score: 0.91,
      reasons: ['connector_match'],
    },
    {
      station_id: 'CFL-SYN-999',
      name: 'Missing station',
      connector_type: 'DC Combo',
      max_kw: 150,
      distance_from_route_km: 1.2,
      route_distance_km: 80,
      estimated_arrival_soc: 0.42,
      score: 0.7,
      reasons: ['fallback'],
    },
  ],
  meta: {
    source: 'local-dataset',
    limitations: ['No live traffic or weather is used.'],
  },
};

describe('getRouteRecommendationStationIds', () => {
  it('extracts recommendation station IDs in backend order', () => {
    expect(getRouteRecommendationStationIds(PLAN_RESULT)).toEqual(['CFL-SYN-002', 'CFL-SYN-999']);
  });

  it('returns an empty list without a plan result', () => {
    expect(getRouteRecommendationStationIds(null)).toEqual([]);
  });
});

describe('matchRouteRecommendationStations', () => {
  it('matches loaded frontend stations by charger ID and skips missing IDs', () => {
    const matches = matchRouteRecommendationStations([STATION_A, STATION_B], getRouteRecommendationStationIds(PLAN_RESULT));

    expect(matches).toEqual([STATION_B]);
  });
});

describe('getRoutePathLayerData', () => {
  it('returns path layer data from a valid provided route', () => {
    const pathData = getRoutePathLayerData({
      id: 'fixture-seoul-daejeon',
      distance_km: 165.2,
      polyline: [
        [126.978, 37.5665],
        [127.0276, 37.4979],
      ],
    });

    expect(pathData).toEqual([
      {
        id: 'fixture-seoul-daejeon',
        path: [
          [126.978, 37.5665],
          [127.0276, 37.4979],
        ],
      },
    ]);
  });

  it('does not create a path for missing or incomplete routes', () => {
    expect(getRoutePathLayerData(null)).toEqual([]);
    expect(getRoutePathLayerData({ distance_km: 1, polyline: [[126.978, 37.5665]] })).toEqual([]);
  });
});

describe('getRouteFitViewState', () => {
  const fallback = {
    longitude: 127.0517,
    latitude: 37.5187,
    zoom: 11.8,
    pitch: 0,
    bearing: 0,
  };

  it('centers and zooms the map around the provided route bounds', () => {
    const viewState = getRouteFitViewState(
      {
        id: 'fixture-seoul-daejeon',
        distance_km: 165.2,
        polyline: [
          [126.978, 37.5665],
          [127.0276, 37.4979],
          [127.3845, 36.3504],
        ],
      },
      { width: 1024, height: 768 },
      fallback,
    );

    expect(viewState.longitude).toBeCloseTo((126.978 + 127.3845) / 2);
    expect(viewState.latitude).toBeCloseTo((36.3504 + 37.5665) / 2);
    expect(viewState.zoom).toBeLessThan(fallback.zoom);
    expect(viewState.pitch).toBe(fallback.pitch);
    expect(viewState.bearing).toBe(fallback.bearing);
  });

  it('keeps the fallback view for incomplete routes or invalid viewports', () => {
    const route: RoutePlannerRoute = { distance_km: 1, polyline: [[126.978, 37.5665]] };
    const completeRoute: RoutePlannerRoute = {
      distance_km: 1,
      polyline: [
        [126.978, 37.5665],
        [127.0276, 37.4979],
      ],
    };

    expect(getRouteFitViewState(route, { width: 1024, height: 768 }, fallback)).toBe(fallback);
    expect(getRouteFitViewState(completeRoute, { width: 0, height: 768 }, fallback)).toBe(fallback);
  });
});
