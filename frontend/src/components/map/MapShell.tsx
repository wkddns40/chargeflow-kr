import { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map } from 'react-map-gl/maplibre';
import { ScatterplotLayer } from '@deck.gl/layers';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { ChargerFeature, ViewState } from '../../types/charger';
import { INITIAL_VIEW_STATE, MAP_STYLE_URL } from '../../constants/viewport';
import { getValidData } from '../../lib/geo';

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
  const [viewState, setViewState] = useState<ViewState>(INITIAL_VIEW_STATE);
  const [selected, setSelected] = useState<ChargerFeature | null>(null);
  const validStations = useMemo(() => getValidData(stations), [stations]);

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
    <div className="map-shell">
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
            <dd>{import.meta.env.VITE_DEMO_MODE === 'false' ? 'API' : 'Static demo'}</dd>
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
