export type ChargerProperties = {
  charger_id: string;
  charger_name: string;
  operator: string;
  connector_type: string;
  max_kw: number;
  address: string;
  status: 'available' | 'occupied' | 'offline' | 'unknown';
  status_updated_at: string;
};

export type ChargerFeature = {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: ChargerProperties;
};

export type FeatureCollection = {
  type: 'FeatureCollection';
  features: ChargerFeature[];
};

export type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
};
