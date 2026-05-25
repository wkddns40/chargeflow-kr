import type { ChargerFeature } from '../types/charger';
import type { RouteChargingPlanResponse } from './routePlanner';

export function getRouteRecommendationStationIds(result: RouteChargingPlanResponse | null): string[] {
  return result?.recommendations.map((recommendation) => recommendation.station_id) ?? [];
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
