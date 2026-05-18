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
