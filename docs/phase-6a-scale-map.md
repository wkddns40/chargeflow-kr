# Phase 6A Scale Map Design

## Scope

Phase 6A makes ChargeFlow KR credible for a 10,000-station Korean charger map. It keeps the current MapLibre and deck.gl rendering path, then moves production data access toward PostGIS-backed viewport APIs and later vector tiles.

Out of scope:

- 100k or 1M station targets.
- Weather features.
- Traffic features.
- LLM search.
- Route planning.
- Public-data OpenAPI application, API credentials, or real-time polling.

<!--
Deferred: public-data OpenAPI application, ServiceKey handling, real-time status polling.
Current phase uses login-free file downloads only.
-->

## Current Architecture

Current repo state:

- `frontend/src/components/map/MapShell.tsx` owns the map-first UI. It renders `DeckGL`, `react-map-gl/maplibre` `Map`, and one deck.gl `ScatterplotLayer`.
- `frontend/src/hooks/useStations.ts` chooses demo data from `/sample-chargers.json` unless `VITE_DEMO_MODE=false`, then fetches `${VITE_API_BASE_URL}/api/stations`.
- `frontend/src/types/charger.ts` defines the current `ChargerFeature` GeoJSON contract used by the frontend and backend response.
- `frontend/public/sample-chargers.json` is a tiny static smoke fixture. It is demo-only and must not become the production data path.
- `backend/app/api/stations.py` already sketches `GET /api/stations` with optional `bbox=west,south,east,north` and `limit`.
- `backend/app/db/schema.sql` creates `stations`, `connectors`, and `status_events` with a GiST index on `stations.geom`.
- `docker-compose.yml` starts local PostGIS and loads `backend/app/db/schema.sql`.
- `docs/ARCHITECTURE.md` documents the current MVP and target station API / MVT / typed search direction.

Current render path:

```text
useStations()
  -> FeatureCollection
  -> MapShell valid station memo
  -> deck.gl ScatterplotLayer
  -> <DeckGL layers={[stationLayer]}>
  -> <Map mapStyle={OpenFreeMap Liberty}>
```

Current limitation:

- Demo fetch can still load a full GeoJSON file.
- `/api/stations` has bbox shape but no automated benchmark fixture yet.
- No MVT tile endpoint exists yet.
- No 10k benchmark result exists yet.

## Target Architecture

Phase 6A target path:

```mermaid
flowchart LR
    browser[Browser] --> app[React + MapLibre + deck.gl]
    app --> bbox[GET /api/stations?bbox=&limit=]
    app --> tiles[Future GET /tiles/stations/{z}/{x}/{y}.mvt]
    bbox --> pg[(Postgres + PostGIS)]
    tiles --> pg
    importer[Login-free file import] --> pg
```

Rendering rules:

- Use deck.gl only for station rendering.
- Do not add DOM marker components.
- Low and mid zoom can use aggregation or MVT later.
- High zoom can keep point layers plus selected-station detail panels.
- Client filtering is allowed only for small already-loaded viewport results.
- Large dataset filtering belongs in SQL, bbox APIs, or GPU-friendly layer props.

## 10k Benchmark Target

First benchmark target:

- Generate 10,000 synthetic station features.
- Load station rows into local PostGIS or a fixture-driven dev path.
- Query by bbox with `limit`.
- Render returned viewport results through deck.gl.
- Keep initial map load under 3 seconds on a mid-range laptop.
- Keep pan/zoom responsive enough for manual smoke, with no DOM marker path.

Do not expand this phase to 100k or 1M points. Those targets need tile and ingestion maturity first.

## DOM Marker Ban

Forbidden patterns for station rendering:

- `Marker` from map libraries.
- `document.createElement` marker creation.
- `appendChild` marker insertion.
- React components that render one DOM node per station on the map.

Allowed:

- deck.gl `ScatterplotLayer`.
- deck.gl `IconLayer`.
- deck.gl `MVTLayer`.
- deck.gl aggregation layers such as `ScreenGridLayer`, `HeatmapLayer`, or `HexagonLayer`.

## Bbox API Contract

Endpoint:

```text
GET /api/stations?bbox=west,south,east,north&limit=1000
```

Rules:

- Coordinates use EPSG:4326 longitude/latitude.
- `bbox` is required for production-scale queries.
- Boundary points are included.
- `limit` has a safe default and hard maximum.
- Invalid bbox returns HTTP 400 with clear error JSON.
- Response remains a GeoJSON `FeatureCollection` for Phase 6A JSON APIs.
- Later MVT endpoints can serve display tiles while JSON endpoints serve selected-station details.

Response shape:

```json
{
  "type": "FeatureCollection",
  "features": [],
  "meta": {
    "count": 0,
    "limit": 1000,
    "source": "synthetic-10k",
    "snapshot_date": "2026-05-19"
  }
}
```

## Synthetic Data Generator Contract

Add a generator in a later Phase 6A task:

```text
backend/scripts/generate_synthetic_stations.py
```

Required behavior:

- Default count: 10,000.
- Fixed seed for deterministic output.
- CLI flags: `--count`, `--seed`, `--out`.
- Output defaults to `backend/fixtures/synthetic-stations-10k.geojson`.
- Coordinates stay inside South Korea bounds.
- Regional distribution:
  - Seoul metro: 50%.
  - Other metro areas: 35%.
  - Jeju: 15%.
- Properties stay compatible with `frontend/src/types/charger.ts`.
- `frontend/public/sample-chargers.json` is never overwritten.

## Login-Free Dataset Import Contract

Near-term real data uses login-free public file downloads only.

Primary import target:

- Korea Environment Corporation EV charger location/operation file dataset.
- Use as station and connector master seed.
- Store source metadata, snapshot date, and raw file hash.

Storage rules for later implementation:

- Raw downloads go under `backend/data/raw/`.
- Raw downloads are not committed.
- Small sanitized fixtures may go under `backend/fixtures/`.
- Import code must preserve source and snapshot metadata so UI answers can cite freshness.

Deferred:

- Public-data API key application.
- ServiceKey handling.
- Real-time charger status polling.
- Partner or OCPI integrations.

## ABRP-Inspired Frontend Direction

ABRP is a product reference for interaction priorities, not branding or pixel copying.

Phase 6A frontend-facing work must stay:

- map-first,
- operational and dense,
- focused on charger availability, connector capability, and source freshness,
- restrained in styling,
- built around panels and controls for charger planning rather than marketing sections.

ABRP-inspired design check for Phase 6A:

- Map remains the primary viewport.
- Panels summarize loaded stations and selected charger facts.
- Future controls should expose source, snapshot date, status, connector type, and power.
- No ABRP logos, proprietary text, screenshots, or visual assets are copied.

## Verification Checklist

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\phase-6a-scale-map.md
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6a-scale-map.md -Pattern "10k|DOM|bbox|deck.gl|login-free"
cd D:\fleet\chargeflow-kr\frontend
npm run build
cd D:\fleet\chargeflow-kr\backend
.venv\Scripts\python.exe -m pytest
```

Scope review:

- No 100k or 1M implementation work.
- No weather or traffic features.
- No LLM search.
- No route planner.
- No public-data OpenAPI credentials or polling.
- No DOM marker rendering path.
