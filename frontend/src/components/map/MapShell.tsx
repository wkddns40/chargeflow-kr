import { useCallback, useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl/maplibre';
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { ChargerFeature, ViewState } from '../../types/charger';
import { INITIAL_VIEW_STATE, MAP_STYLE_URL, REFERENCE_VIEWPORT_SIZE } from '../../constants/viewport';
import { getStationFocusViewState, getValidData } from '../../lib/geo';
import type { RouteChargingPlanResponse, RoutePlannerRoute } from '../../lib/routePlanner';
import {
  findRouteRecommendationStation,
  getRouteFitViewState,
  getRoutePathLayerData,
  getRouteRecommendationStationIds,
  matchRouteRecommendationStations,
  type RoutePathLayerData,
} from '../../lib/routePlannerMap';
import { isViewportStationsFlagEnabled, useViewportStations } from '../../hooks/useViewportStations';
import { SearchAssistantPanel } from '../search/SearchAssistantPanel';
import { RoutePlannerPanel } from '../route/RoutePlannerPanel';

type MapShellProps = {
  stations: ChargerFeature[];
  assistantSearchEnabled?: boolean;
  routePlannerEnabled?: boolean;
};

type StageTransform = {
  scale: number;
  x: number;
  y: number;
};

const STATUS_COLORS: Record<ChargerFeature['properties']['status'], [number, number, number, number]> = {
  available: [36, 160, 95, 220],
  occupied: [241, 170, 59, 220],
  offline: [202, 73, 65, 220],
  unknown: [112, 122, 138, 200],
};

function getStageTransform(): StageTransform {
  if (typeof window === 'undefined') {
    return { scale: 1, x: 0, y: 0 };
  }

  const scale = Math.min(
    window.innerWidth / REFERENCE_VIEWPORT_SIZE.width,
    window.innerHeight / REFERENCE_VIEWPORT_SIZE.height,
  );
  return {
    scale,
    x: (window.innerWidth - REFERENCE_VIEWPORT_SIZE.width * scale) / 2,
    y: (window.innerHeight - REFERENCE_VIEWPORT_SIZE.height * scale) / 2,
  };
}

export function MapShell({ stations, assistantSearchEnabled = false, routePlannerEnabled = false }: MapShellProps) {
  const [viewState, setViewState] = useState<ViewState>(INITIAL_VIEW_STATE);
  const [stageTransform, setStageTransform] = useState<StageTransform>(getStageTransform);
  const [selected, setSelected] = useState<ChargerFeature | null>(null);
  const [assistantResults, setAssistantResults] = useState<ChargerFeature[] | null>(null);
  const [routePlanResult, setRoutePlanResult] = useState<RouteChargingPlanResponse | null>(null);
  const [routePlanRoute, setRoutePlanRoute] = useState<RoutePlannerRoute | null>(null);
  const viewportStationsEnabled = isViewportStationsFlagEnabled(import.meta.env.VITE_ENABLE_VIEWPORT_STATIONS);
  const viewportStations = useViewportStations({
    viewState,
    viewport: REFERENCE_VIEWPORT_SIZE,
    enabled: viewportStationsEnabled,
  });
  const baseStations = viewportStations.enabled ? viewportStations.stations : stations;
  const layerStations = assistantResults ?? baseStations;
  const validBaseStations = useMemo(() => getValidData(baseStations), [baseStations]);
  const validStations = useMemo(() => getValidData(layerStations), [layerStations]);
  const routeRecommendationIds = useMemo(() => getRouteRecommendationStationIds(routePlanResult), [routePlanResult]);
  const routeRecommendationStations = useMemo(
    () => matchRouteRecommendationStations(validBaseStations, routeRecommendationIds),
    [routeRecommendationIds, validBaseStations],
  );
  const visibleRouteRecommendationStations = useMemo(
    () => (assistantResults ? [] : routeRecommendationStations),
    [assistantResults, routeRecommendationStations],
  );
  const routePathData = useMemo(() => getRoutePathLayerData(routePlanRoute), [routePlanRoute]);
  const dataMode = viewportStations.enabled ? 'Viewport API' : import.meta.env.VITE_DEMO_MODE === 'false' ? 'API' : 'Static demo';
  const rightPanelsEnabled = assistantSearchEnabled || routePlannerEnabled;
  const handleFocusStation = useCallback((station: ChargerFeature) => {
    setAssistantResults([station]);
    setSelected(station);
    setViewState((currentViewState) => getStationFocusViewState(station, currentViewState));
  }, []);
  const handleSelectRouteRecommendation = useCallback(
    (stationId: string) => {
      const station = findRouteRecommendationStation(routeRecommendationStations, stationId);
      if (station) {
        handleFocusStation(station);
      }
    },
    [handleFocusStation, routeRecommendationStations],
  );

  useEffect(() => {
    const updateStageScale = () => {
      setStageTransform(getStageTransform());
    };

    updateStageScale();
    window.addEventListener('resize', updateStageScale);
    return () => window.removeEventListener('resize', updateStageScale);
  }, []);

  const stationLayer = useMemo(
    () =>
      new ScatterplotLayer<ChargerFeature>({
        id: 'station-points',
        data: validStations,
        pickable: true,
        radiusUnits: 'pixels',
        getRadius: (station: ChargerFeature) => Math.max(5, Math.min(13, station.properties.max_kw / 18)),
        getPosition: (station: ChargerFeature) => station.geometry.coordinates,
        getFillColor: (station: ChargerFeature) => STATUS_COLORS[station.properties.status],
        onClick: ({ object }: { object?: ChargerFeature | null }) => {
          if (object) {
            handleFocusStation(object);
          }
        },
      }),
    [handleFocusStation, validStations],
  );
  const routePathLayer = useMemo(
    () =>
      new PathLayer<RoutePathLayerData>({
        id: 'route-plan-path',
        data: routePathData,
        getPath: (route: RoutePathLayerData) => route.path,
        getColor: () => [14, 165, 233, 230],
        getWidth: () => 5,
        widthUnits: 'pixels',
        rounded: true,
        jointRounded: true,
        capRounded: true,
      }),
    [routePathData],
  );
  const routeRecommendationLayer = useMemo(
    () =>
      new ScatterplotLayer<ChargerFeature>({
        id: 'route-recommendation-points',
        data: visibleRouteRecommendationStations,
        pickable: true,
        radiusUnits: 'pixels',
        stroked: true,
        filled: true,
        lineWidthUnits: 'pixels',
        getLineWidth: () => 3,
        getRadius: () => 16,
        getPosition: (station: ChargerFeature) => station.geometry.coordinates,
        getFillColor: () => [37, 99, 235, 90],
        getLineColor: () => [37, 99, 235, 245],
        onClick: ({ object }: { object?: ChargerFeature | null }) => {
          if (object) {
            handleFocusStation(object);
          }
        },
      }),
    [handleFocusStation, visibleRouteRecommendationStations],
  );
  const layers = useMemo(
    () => [
      ...(routePathData.length > 0 ? [routePathLayer] : []),
      stationLayer,
      ...(visibleRouteRecommendationStations.length > 0 ? [routeRecommendationLayer] : []),
    ],
    [
      routePathData.length,
      routePathLayer,
      routeRecommendationLayer,
      stationLayer,
      visibleRouteRecommendationStations.length,
    ],
  );

  return (
    <div className="map-shell-frame">
      <div
        className={`map-shell${rightPanelsEnabled ? ' right-panels-enabled' : ''}`}
        style={{
          transform: `translate(${stageTransform.x}px, ${stageTransform.y}px) scale(${stageTransform.scale})`,
        }}
      >
        <DeckGL
          layers={layers}
          viewState={viewState}
          onViewStateChange={({ viewState: nextViewState }: { viewState: ViewState }) => setViewState(nextViewState)}
          controller={{ dragPan: true, scrollZoom: true, doubleClickZoom: false, dragRotate: false }}
        >
          <Map reuseMaps mapStyle={MAP_STYLE_URL} />
        </DeckGL>

        <aside className="summary-panel">
          <p className="eyebrow">ChargeFlow KR</p>
          <h1>Korean charger intelligence map</h1>
          <dl>
            <div>
              <dt>Loaded stations</dt>
              <dd>{validStations.length.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Data mode</dt>
              <dd>{dataMode}</dd>
            </div>
          </dl>
        </aside>

        {rightPanelsEnabled && (
          <div className="right-panel-stack">
            {assistantSearchEnabled && (
              <SearchAssistantPanel
                onApplyResults={(features) => {
                  setAssistantResults(features);
                  setSelected(null);
                }}
                onSelectResult={handleFocusStation}
                onClearResults={() => {
                  setAssistantResults(null);
                  setSelected(null);
                }}
              />
            )}
            {routePlannerEnabled && (
              <RoutePlannerPanel
                onApplyPlan={(result, route) => {
                  setRoutePlanResult(result);
                  setRoutePlanRoute(route);
                  setViewState((currentViewState) =>
                    getRouteFitViewState(route, REFERENCE_VIEWPORT_SIZE, currentViewState),
                  );
                }}
                onSelectRecommendation={handleSelectRouteRecommendation}
                onClearRecommendations={() => {
                  setRoutePlanResult(null);
                  setRoutePlanRoute(null);
                }}
              />
            )}
          </div>
        )}

        {selected && (
          <aside className="detail-panel">
            <button type="button" aria-label="Close station details" onClick={() => setSelected(null)}>
              x
            </button>
            <p className="eyebrow">{selected.properties.operator}</p>
            <h2>{selected.properties.charger_name}</h2>
            <p>{selected.properties.address}</p>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{selected.properties.status}</dd>
              </div>
              <div>
                <dt>Power</dt>
                <dd>{selected.properties.max_kw} kW</dd>
              </div>
              <div>
                <dt>Connector</dt>
                <dd>{selected.properties.connector_type}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{selected.properties.status_updated_at}</dd>
              </div>
            </dl>
          </aside>
        )}
      </div>
    </div>
  );
}
