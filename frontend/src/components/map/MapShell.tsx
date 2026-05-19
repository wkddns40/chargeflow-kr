import { useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl/maplibre';
import { ScatterplotLayer } from '@deck.gl/layers';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { ChargerFeature, ViewState } from '../../types/charger';
import { INITIAL_VIEW_STATE, MAP_STYLE_URL } from '../../constants/viewport';
import { getValidData, type ViewportSize } from '../../lib/geo';
import { isViewportStationsFlagEnabled, useViewportStations } from '../../hooks/useViewportStations';

type MapShellProps = {
  stations: ChargerFeature[];
};

const STATUS_COLORS: Record<ChargerFeature['properties']['status'], [number, number, number, number]> = {
  available: [36, 160, 95, 220],
  occupied: [241, 170, 59, 220],
  offline: [202, 73, 65, 220],
  unknown: [112, 122, 138, 200],
};

export function MapShell({ stations }: MapShellProps) {
  const shellRef = useRef<HTMLDivElement | null>(null);
  const [viewState, setViewState] = useState<ViewState>(INITIAL_VIEW_STATE);
  const [viewportSize, setViewportSize] = useState<ViewportSize>({ width: 1024, height: 768 });
  const [selected, setSelected] = useState<ChargerFeature | null>(null);
  const viewportStationsEnabled = isViewportStationsFlagEnabled(import.meta.env.VITE_ENABLE_VIEWPORT_STATIONS);
  const viewportStations = useViewportStations({
    viewState,
    viewport: viewportSize,
    enabled: viewportStationsEnabled,
  });
  const layerStations = viewportStations.enabled ? viewportStations.stations : stations;
  const validStations = useMemo(() => getValidData(layerStations), [layerStations]);
  const dataMode = viewportStations.enabled ? 'Viewport API' : import.meta.env.VITE_DEMO_MODE === 'false' ? 'API' : 'Static demo';

  useEffect(() => {
    if (!viewportStationsEnabled || !shellRef.current) return;

    const updateViewportSize = () => {
      const rect = shellRef.current?.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) {
        setViewportSize({ width: rect.width, height: rect.height });
      }
    };

    updateViewportSize();
    const observer = new ResizeObserver(updateViewportSize);
    observer.observe(shellRef.current);
    return () => observer.disconnect();
  }, [viewportStationsEnabled]);

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
        onClick: ({ object }: { object?: ChargerFeature | null }) => setSelected(object ?? null),
      }),
    [validStations],
  );

  return (
    <div ref={shellRef} className="map-shell">
      <DeckGL
        layers={[stationLayer]}
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
  );
}
