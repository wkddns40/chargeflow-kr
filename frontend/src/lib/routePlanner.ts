const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const ROUTE_PLANNER_FLAG = import.meta.env.VITE_ENABLE_ROUTE_PLANNER ?? 'false';

export type RouteCoordinate = [number, number];

export type RoutePlannerRoute = {
  id?: string;
  polyline: RouteCoordinate[];
  distance_km: number;
};

export type RoutePlannerVehicle = {
  battery_kwh: number;
  current_soc: number;
  target_arrival_soc: number;
  consumption_kwh_per_km: number;
  preferred_connector_types: string[];
  max_charging_kw: number;
};

export type RoutePlannerConstraints = {
  corridor_width_km?: number;
  max_results?: number;
};

export type RouteChargingPlanRequest = {
  route: RoutePlannerRoute;
  vehicle: RoutePlannerVehicle;
  constraints?: RoutePlannerConstraints;
  reference_time?: string;
};

export type RoutePlannerSummary = {
  distance_km: number;
  estimated_energy_kwh: number;
  start_soc: number;
  target_arrival_soc: number;
  minimum_required_soc: number;
  reachable_without_stop: boolean;
};

export type RoutePlannerRecommendation = {
  station_id: string;
  name: string;
  connector_type: string;
  max_kw: number;
  distance_from_route_km: number;
  route_distance_km: number;
  estimated_arrival_soc: number;
  score: number;
  reasons: string[];
};

export type RoutePlannerResponseMeta = {
  source: string;
  limitations: string[];
  snapshot_date?: string | null;
  freshness_label?: string | null;
};

export type RouteChargingPlanResponse = {
  route_id: string;
  summary: RoutePlannerSummary;
  recommendations: RoutePlannerRecommendation[];
  meta: RoutePlannerResponseMeta;
};

export function isRoutePlannerFlagEnabled(flagValue: string | undefined): boolean {
  return flagValue === 'true';
}

export function buildChargingPlanUrl(apiBaseUrl = API_BASE_URL): string {
  const baseUrl = apiBaseUrl.replace(/\/$/, '');
  return `${baseUrl}/api/routes/charging-plan`;
}

export async function fetchChargingPlan(
  request: RouteChargingPlanRequest,
  apiBaseUrl = API_BASE_URL,
): Promise<RouteChargingPlanResponse> {
  const response = await fetch(buildChargingPlanUrl(apiBaseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Route planner failed: ${String(response.status)}`);
  }

  return response.json() as Promise<RouteChargingPlanResponse>;
}

export const routePlannerEnabled = isRoutePlannerFlagEnabled(ROUTE_PLANNER_FLAG);
