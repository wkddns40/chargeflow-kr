import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  RoutePlannerApiError,
  buildChargingPlanUrl,
  fetchChargingPlan,
  isRoutePlannerApiError,
  isRoutePlannerFlagEnabled,
} from './routePlanner';
import type { RouteChargingPlanRequest } from './routePlanner';

const REQUEST: RouteChargingPlanRequest = {
  route: {
    id: 'fixture-seoul-daejeon',
    polyline: [
      [126.978, 37.5665],
      [127.3845, 36.3504],
    ],
    distance_km: 165.2,
  },
  vehicle: {
    battery_kwh: 77.4,
    current_soc: 0.64,
    target_arrival_soc: 0.15,
    consumption_kwh_per_km: 0.18,
    preferred_connector_types: ['DC Combo'],
    max_charging_kw: 180,
  },
  constraints: {
    corridor_width_km: 3,
    max_results: 5,
  },
};

describe('isRoutePlannerFlagEnabled', () => {
  it('enables only the explicit true value', () => {
    expect(isRoutePlannerFlagEnabled('true')).toBe(true);
    expect(isRoutePlannerFlagEnabled('false')).toBe(false);
    expect(isRoutePlannerFlagEnabled(undefined)).toBe(false);
  });
});

describe('buildChargingPlanUrl', () => {
  it('builds a relative route planner endpoint by default', () => {
    expect(buildChargingPlanUrl('')).toBe('/api/routes/charging-plan');
  });

  it('builds an absolute route planner endpoint from the API base URL', () => {
    expect(buildChargingPlanUrl('http://localhost:8000/')).toBe('http://localhost:8000/api/routes/charging-plan');
  });
});

describe('fetchChargingPlan', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts the typed route planner request to the backend endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        route_id: 'fixture-seoul-daejeon',
        summary: {
          distance_km: 165.2,
          estimated_energy_kwh: 29.736,
          start_soc: 0.64,
          target_arrival_soc: 0.15,
          minimum_required_soc: 0.534,
          reachable_without_stop: true,
        },
        recommendations: [],
        meta: {
          source: 'local-dataset',
          limitations: ['No live traffic or weather is used.'],
        },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await fetchChargingPlan(REQUEST, 'http://localhost:8000');

    expect(response.meta.limitations).toContain('No live traffic or weather is used.');
    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/routes/charging-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(REQUEST),
    });
  });

  it('throws on a failed backend response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400 }));

    await expect(fetchChargingPlan(REQUEST)).rejects.toThrow('Route planner failed: 400');
  });

  it('preserves backend graph error details on failed responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          detail: [{ node: 'validate_route_request', message: 'request.route is required', code: 'missing_route' }],
        }),
      }),
    );

    let thrown: unknown;
    try {
      await fetchChargingPlan(REQUEST);
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(RoutePlannerApiError);
    expect(isRoutePlannerApiError(thrown)).toBe(true);
    if (isRoutePlannerApiError(thrown)) {
      expect(thrown.status).toBe(400);
      expect(thrown.detail).toEqual([
        { node: 'validate_route_request', message: 'request.route is required', code: 'missing_route' },
      ]);
    }
  });
});
