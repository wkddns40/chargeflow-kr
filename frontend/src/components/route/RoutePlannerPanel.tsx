import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  fetchChargingPlan,
  type RouteChargingPlanRequest,
  type RouteChargingPlanResponse,
  type RoutePlannerRoute,
} from '../../lib/routePlanner';
import {
  resolveRouteFixture,
  ROUTE_FIXTURES,
  type RoutePlannerFixture,
} from '../../lib/routePlannerFixtures';
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
  onApplyPlan?: (result: RouteChargingPlanResponse, route: RoutePlannerRoute) => void;
  onSelectRecommendation?: (stationId: string) => void;
  onClearRecommendations?: () => void;
};

const CONNECTOR_OPTIONS = ['DC Combo', 'DC', 'CHAdeMO', 'AC Type 2'] as const;
const DEFAULT_ROUTE_FIXTURE = ROUTE_FIXTURES[0];
const UNSUPPORTED_ROUTE_MESSAGE = '지원 fixture 없음';

export function RoutePlannerPanel({
  onApplyPlan,
  onSelectRecommendation,
  onClearRecommendations,
}: RoutePlannerPanelProps = {}) {
  const [origin, setOrigin] = useState(DEFAULT_ROUTE_FIXTURE.origin);
  const [destination, setDestination] = useState(DEFAULT_ROUTE_FIXTURE.destination);
  const [batteryKwh, setBatteryKwh] = useState(77.4);
  const [currentSocPercent, setCurrentSocPercent] = useState(64);
  const [targetSocPercent, setTargetSocPercent] = useState(15);
  const [consumptionKwhPerKm, setConsumptionKwhPerKm] = useState(0.18);
  const [connectorType, setConnectorType] = useState<(typeof CONNECTOR_OPTIONS)[number]>('DC Combo');
  const [maxChargingKw, setMaxChargingKw] = useState(180);
  const [corridorWidthKm, setCorridorWidthKm] = useState(3);
  const [maxResults, setMaxResults] = useState(5);
  const [unsupportedRouteMessage, setUnsupportedRouteMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (request: RouteChargingPlanRequest) => fetchChargingPlan(request),
    onSuccess: (data, request) => onApplyPlan?.(data, request.route),
  });

  function buildRequest(selectedRoute: RoutePlannerFixture): RouteChargingPlanRequest {
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

    const selectedRoute = resolveRouteFixture(origin, destination);
    if (!selectedRoute) {
      mutation.reset();
      onClearRecommendations?.();
      setUnsupportedRouteMessage(UNSUPPORTED_ROUTE_MESSAGE);
      return;
    }

    setUnsupportedRouteMessage(null);
    mutation.mutate(buildRequest(selectedRoute));
  }

  function handleClear() {
    mutation.reset();
    setOrigin(DEFAULT_ROUTE_FIXTURE.origin);
    setDestination(DEFAULT_ROUTE_FIXTURE.destination);
    setUnsupportedRouteMessage(null);
    onClearRecommendations?.();
  }

  return (
    <aside className="route-planner-panel" aria-label="Route planner">
      <div className="assistant-heading">
        <p className="eyebrow">Route planner</p>
        <button type="button" onClick={handleClear}>
          Clear
        </button>
      </div>

      <form className="assistant-form" onSubmit={handleSubmit}>
        <div className="assistant-grid">
          <label>
            <span>Origin</span>
            <input
              type="text"
              value={origin}
              onFocus={() => {
                setOrigin('');
                setUnsupportedRouteMessage(null);
              }}
              onChange={(event) => {
                setOrigin(event.target.value);
                setUnsupportedRouteMessage(null);
              }}
            />
          </label>
          <label>
            <span>Destination</span>
            <input
              type="text"
              value={destination}
              onFocus={() => {
                setDestination('');
                setUnsupportedRouteMessage(null);
              }}
              onChange={(event) => {
                setDestination(event.target.value);
                setUnsupportedRouteMessage(null);
              }}
            />
          </label>
        </div>

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

      {unsupportedRouteMessage && <p className="assistant-message">{unsupportedRouteMessage}</p>}
      {mutation.isError && <RoutePlanError error={mutation.error} />}
      {mutation.data && <RoutePlanResult result={mutation.data} onSelectRecommendation={onSelectRecommendation} />}
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

function RoutePlanResult({
  result,
  onSelectRecommendation,
}: {
  result: RouteChargingPlanResponse;
  onSelectRecommendation?: (stationId: string) => void;
}) {
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
              <button
                type="button"
                className="route-plan-stop-button"
                onClick={() => onSelectRecommendation?.(recommendation.station_id)}
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
              </button>
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
