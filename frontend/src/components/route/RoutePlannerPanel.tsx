import { FormEvent, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  fetchChargingPlan,
  type RouteChargingPlanRequest,
  type RouteChargingPlanResponse,
  type RoutePlannerRoute,
} from '../../lib/routePlanner';
import {
  formatRoutePlannerReason,
  formatRoutePlannerScore,
  formatRoutePlannerSoc,
  getRoutePlannerErrorMessages,
  getRoutePlannerLimitations,
  getRoutePlannerMetaRows,
  hasFallbackReason,
} from '../../lib/routePlannerDisplay';

type RoutePlannerPanelProps = {
  onApplyRecommendations?: (result: RouteChargingPlanResponse) => void;
  onClearRecommendations?: () => void;
};

const ROUTE_OPTIONS: Array<RoutePlannerRoute & { label: string }> = [
  {
    id: 'fixture-seoul-daejeon',
    label: 'Seoul-Daejeon',
    distance_km: 165.2,
    polyline: [
      [126.978, 37.5665],
      [127.0276, 37.4979],
      [127.3845, 36.3504],
    ],
  },
];

const CONNECTOR_OPTIONS = ['DC Combo', 'DC', 'CHAdeMO', 'AC Type 2'] as const;

export function RoutePlannerPanel({ onApplyRecommendations, onClearRecommendations }: RoutePlannerPanelProps = {}) {
  const [routeId, setRouteId] = useState(ROUTE_OPTIONS[0].id ?? '');
  const [batteryKwh, setBatteryKwh] = useState(77.4);
  const [currentSocPercent, setCurrentSocPercent] = useState(64);
  const [targetSocPercent, setTargetSocPercent] = useState(15);
  const [consumptionKwhPerKm, setConsumptionKwhPerKm] = useState(0.18);
  const [connectorType, setConnectorType] = useState<(typeof CONNECTOR_OPTIONS)[number]>('DC Combo');
  const [maxChargingKw, setMaxChargingKw] = useState(180);
  const [corridorWidthKm, setCorridorWidthKm] = useState(3);
  const [maxResults, setMaxResults] = useState(5);

  const selectedRoute = useMemo(
    () => ROUTE_OPTIONS.find((route) => route.id === routeId) ?? ROUTE_OPTIONS[0],
    [routeId],
  );

  const mutation = useMutation({
    mutationFn: (request: RouteChargingPlanRequest) => fetchChargingPlan(request),
    onSuccess: (data) => onApplyRecommendations?.(data),
  });

  function buildRequest(): RouteChargingPlanRequest {
    return {
      route: {
        id: selectedRoute.id,
        polyline: selectedRoute.polyline,
        distance_km: selectedRoute.distance_km,
      },
      vehicle: {
        battery_kwh: batteryKwh,
        current_soc: currentSocPercent / 100,
        target_arrival_soc: targetSocPercent / 100,
        consumption_kwh_per_km: consumptionKwhPerKm,
        preferred_connector_types: [connectorType],
        max_charging_kw: maxChargingKw,
      },
      constraints: {
        corridor_width_km: corridorWidthKm,
        max_results: maxResults,
      },
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate(buildRequest());
  }

  return (
    <aside className="route-planner-panel" aria-label="Route planner">
      <div className="assistant-heading">
        <p className="eyebrow">Route planner</p>
        <button
          type="button"
          onClick={() => {
            mutation.reset();
            onClearRecommendations?.();
          }}
        >
          Clear
        </button>
      </div>

      <form className="assistant-form" onSubmit={handleSubmit}>
        <label>
          <span>Route</span>
          <select value={routeId} onChange={(event) => setRouteId(event.target.value)}>
            {ROUTE_OPTIONS.map((route) => (
              <option key={route.id} value={route.id}>
                {route.label}
              </option>
            ))}
          </select>
        </label>

        <div className="assistant-grid">
          <label>
            <span>Battery kWh</span>
            <input
              min="1"
              max="250"
              step="0.1"
              type="number"
              value={batteryKwh}
              onChange={(event) => setBatteryKwh(Number(event.target.value))}
            />
          </label>
          <label>
            <span>Max kW</span>
            <input
              min="1"
              max="500"
              step="1"
              type="number"
              value={maxChargingKw}
              onChange={(event) => setMaxChargingKw(Number(event.target.value))}
            />
          </label>
        </div>

        <div className="assistant-grid">
          <label>
            <span>Start SoC %</span>
            <input
              min="0"
              max="100"
              step="1"
              type="number"
              value={currentSocPercent}
              onChange={(event) => setCurrentSocPercent(Number(event.target.value))}
            />
          </label>
          <label>
            <span>Target SoC %</span>
            <input
              min="0"
              max="100"
              step="1"
              type="number"
              value={targetSocPercent}
              onChange={(event) => setTargetSocPercent(Number(event.target.value))}
            />
          </label>
        </div>

        <label>
          <span>Consumption kWh/km</span>
          <input
            min="0.01"
            max="1"
            step="0.01"
            type="number"
            value={consumptionKwhPerKm}
            onChange={(event) => setConsumptionKwhPerKm(Number(event.target.value))}
          />
        </label>

        <div className="assistant-grid">
          <label>
            <span>Connector</span>
            <select
              value={connectorType}
              onChange={(event) => setConnectorType(event.target.value as (typeof CONNECTOR_OPTIONS)[number])}
            >
              {CONNECTOR_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Results</span>
            <input
              min="1"
              max="20"
              step="1"
              type="number"
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
            />
          </label>
        </div>

        <label>
          <span>Corridor km</span>
          <input
            min="0.1"
            max="20"
            step="0.1"
            type="number"
            value={corridorWidthKm}
            onChange={(event) => setCorridorWidthKm(Number(event.target.value))}
          />
        </label>

        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Planning...' : 'Plan'}
        </button>
      </form>

      {mutation.isError && <RoutePlanError error={mutation.error} />}
      {mutation.data && <RoutePlanResult result={mutation.data} />}
    </aside>
  );
}

function RoutePlanError({ error }: { error: unknown }) {
  return (
    <div className="route-plan-error">
      <p className="assistant-message">Route plan failed.</p>
      <ul>
        {getRoutePlannerErrorMessages(error).map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  );
}

function RoutePlanResult({ result }: { result: RouteChargingPlanResponse }) {
  return (
    <div className="route-plan-results">
      <dl>
        <div>
          <dt>Distance</dt>
          <dd>{result.summary.distance_km.toFixed(1)} km</dd>
        </div>
        <div>
          <dt>Energy</dt>
          <dd>{result.summary.estimated_energy_kwh.toFixed(1)} kWh</dd>
        </div>
        <div>
          <dt>Arrival SoC</dt>
          <dd>{formatEstimatedArrivalSoc(result.summary)}</dd>
        </div>
        <div>
          <dt>Reachable</dt>
          <dd>{result.summary.reachable_without_stop ? 'Yes' : 'No'}</dd>
        </div>
      </dl>

      {result.recommendations.length === 0 ? (
        <p className="assistant-message">No local matches.</p>
      ) : (
        <ol>
          {result.recommendations.slice(0, 5).map((recommendation) => (
            <li
              key={recommendation.station_id}
              className={hasFallbackReason(recommendation.reasons) ? 'route-plan-fallback' : undefined}
            >
              <strong>{recommendation.name}</strong>
              <span>
                {recommendation.max_kw} kW / {recommendation.connector_type}
              </span>
              <span>
                {recommendation.route_distance_km.toFixed(1)} km route /{' '}
                {recommendation.distance_from_route_km.toFixed(1)} km detour
              </span>
              <span>
                Arrival {formatRoutePlannerSoc(recommendation.estimated_arrival_soc)} / score{' '}
                {formatRoutePlannerScore(recommendation.score)}
              </span>
              <div className="route-plan-reasons">
                {recommendation.reasons.map((reason) => (
                  <span key={reason}>{formatRoutePlannerReason(reason)}</span>
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}

      <dl className="route-plan-meta">
        {getRoutePlannerMetaRows(result.meta).map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <ul>
        {getRoutePlannerLimitations(result.meta).map((limitation) => (
          <li key={limitation}>{limitation}</li>
        ))}
      </ul>
    </div>
  );
}

function formatPercent(value: number): string {
  return formatRoutePlannerSoc(value);
}

function formatEstimatedArrivalSoc(summary: RouteChargingPlanResponse['summary']): string {
  const socDelta = summary.minimum_required_soc - summary.target_arrival_soc;
  return formatPercent(summary.start_soc - socDelta);
}
