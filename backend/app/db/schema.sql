CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    operator TEXT NOT NULL,
    address TEXT NOT NULL,
    region_code TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS stations_geom_gix ON stations USING gist (geom);

CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    place_type TEXT NOT NULL CHECK (place_type IN ('station', 'province', 'district', 'subdistrict')),
    region_code TEXT,
    geom GEOMETRY(Point, 4326) NOT NULL,
    bbox GEOMETRY(Polygon, 4326),
    source TEXT NOT NULL,
    source_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS places_geom_gix ON places USING gist (geom);
CREATE INDEX IF NOT EXISTS places_bbox_gix ON places USING gist (bbox);
CREATE INDEX IF NOT EXISTS places_type_idx ON places (place_type);

ALTER TABLE places ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS place_aliases (
    id BIGSERIAL PRIMARY KEY,
    place_id TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ko',
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (place_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS place_aliases_lookup_idx ON place_aliases (normalized_alias, priority);
CREATE INDEX IF NOT EXISTS place_aliases_place_idx ON place_aliases (place_id);

ALTER TABLE place_aliases ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS connectors (
    id TEXT PRIMARY KEY,
    station_id TEXT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    connector_type TEXT NOT NULL,
    max_kw NUMERIC(6, 1) NOT NULL,
    current_type TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    status_updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS connectors_station_idx ON connectors (station_id);
CREATE INDEX IF NOT EXISTS connectors_status_idx ON connectors (status);

CREATE TABLE IF NOT EXISTS status_events (
    id BIGSERIAL PRIMARY KEY,
    connector_id TEXT NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_file_hash TEXT
);

CREATE INDEX IF NOT EXISTS status_events_connector_time_idx ON status_events (connector_id, observed_at DESC);
