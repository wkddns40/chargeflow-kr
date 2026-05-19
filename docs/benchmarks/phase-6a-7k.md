# Phase 6A 7k Benchmark

Date: 2026-05-19

## Scope

This benchmark records the first ChargeFlow KR scalability target: 7,000 synthetic Korean EV charger stations. It validates the fixture generator, bbox API path, deck.gl render path, and DOM marker ban before moving to larger data or MVT work.

This is a local development smoke benchmark, not a production performance claim.

## Dataset

- Fixture: `backend/fixtures/synthetic-stations-7k.geojson`.
- Source label: `synthetic-stations-7k`.
- Feature count: 7,000.
- Fixture size: 3,939,959 bytes.
- Frontend static demo fixture remains `frontend/public/sample-chargers.json` with 3 features.
- The 7k fixture is served by the backend only. Frontend source/static files do not import or fetch `synthetic-stations-7k.geojson` directly.

Generate and validate:

```powershell
python backend\scripts\generate_synthetic_stations.py --count 7000 --seed 42
python -m json.tool backend\fixtures\synthetic-stations-7k.geojson > $null
```

## Backend API Latency

Method:

```powershell
cd D:\fleet\chargeflow-kr\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003
curl.exe -s -o response.json -w "%{http_code} %{time_total}" "http://127.0.0.1:8003/api/stations?bbox=126,33,128,38&limit=50"
curl.exe -s -o response.json -w "%{http_code} %{time_total}" "http://127.0.0.1:8003/api/stations?bbox=124.5,33,131.9,38.7&limit=2000"
```

Results are from 5 local requests after `/healthz` was ready:

| Query | HTTP | Features | Limit | Min | Median | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `bbox=126,33,128,38&limit=50` | 200 | 50 | 50 | 5.8 ms | 7.2 ms | 95.1 ms |
| `bbox=124.5,33,131.9,38.7&limit=2000` | 200 | 2,000 | 2,000 | 48.3 ms | 74.8 ms | 93.5 ms |

## Frontend Render Smoke

Default path:

- Vite dev root returned HTTP 200.
- `/sample-chargers.json` returned a GeoJSON `FeatureCollection` with 3 features.
- Static demo behavior remains unchanged when `VITE_ENABLE_VIEWPORT_STATIONS=false`.

Experimental path:

- `VITE_ENABLE_VIEWPORT_STATIONS=true` routes `MapShell` layer data through `useViewportStations`.
- The bbox API returned 50 features from `synthetic-stations-7k` in local smoke.
- `MapShell` still renders stations through deck.gl `ScatterplotLayer`.
- 1.9 README review added live-demo and feature wording without screenshot references.
- No screenshot files were created or replaced because no existing README screenshot paths exist and the default user-visible demo remains the 3-feature static smoke path.
- 1.9 local demo smoke confirmed default Vite still serves `sample-chargers.json` with 3 features, and experimental backend smoke still returns 50 bbox-filtered features from `synthetic-stations-7k`.
- ABRP-inspired design check remains documented in `docs/phase-6a-scale-map.md`; no ABRP-owned assets, screenshots, logos, or proprietary copy were added.

## DOM Marker Ban

Verification:

```powershell
rg -n "Marker|document\.createElement|appendChild" frontend/src --glob "*.tsx"
rg -n "synthetic-stations-7k" frontend/src frontend/public
```

Results:

- No frontend TSX matches for DOM marker patterns.
- No frontend source/static reference to `synthetic-stations-7k`.
- Station rendering remains `MapShell` -> deck.gl `ScatterplotLayer`.

## Verification

```powershell
cd D:\fleet\chargeflow-kr\frontend
npm run test
npm run typecheck
npm run build

cd D:\fleet\chargeflow-kr\backend
.venv\Scripts\python.exe -m pytest
```

Observed:

- Frontend tests: 3 files, 10 tests passed.
- Frontend typecheck: passed.
- Frontend build: passed with existing dependency eval/chunk-size warnings.
- Backend pytest: 26 passed.

## Known Limitations

- `/api/stations` currently scans an in-process GeoJSON fixture; PostGIS query path comes later.
- No MVT endpoint, clustering, cache layer, or tile pre-generation yet.
- No automated browser pixel/performance capture yet.
- No 100k or 1M target yet; those wait for ingestion and tile maturity.
