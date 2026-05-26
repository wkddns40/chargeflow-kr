# DB-Backed Demo Deployment Runbook

This runbook covers the first public ChargeFlow KR synthetic snapshot demo.

Public wording:

- Demo name: `synthetic snapshot demo`
- Data source: deterministic synthetic 7k charger snapshot
- Availability wording: snapshot-derived availability from seeded mock rows
- Do not claim real-time availability for this demo

Use live/current availability wording only after a real ingestion or polling path updates the database on a defined cadence, exposes freshness metadata, and passes public smoke checks.

## Topology

```text
User browser
  -> Vercel CDN / Vite SPA
  -> FastAPI backend
  -> Managed Postgres + PostGIS
  -> seeded synthetic 7k snapshot
```

The browser never connects directly to Postgres.

Deployment units:

| Unit | Responsibility |
| --- | --- |
| Vercel frontend | Serve Vite SPA, call backend through `VITE_API_BASE_URL`, show `Viewport API` data mode. |
| FastAPI backend | Serve `/healthz`, `/api/stations`, `/api/search/chargers`, and `/api/routes/charging-plan`. |
| Managed PostGIS | Store `stations`, `connectors`, and `status_events` rows. |
| Release seed job | Apply schema and seed synthetic rows outside web startup. |

Package docs:

- Backend: [backend/deploy/README.md](../backend/deploy/README.md)
- Frontend: [frontend/deploy/README.md](../frontend/deploy/README.md)

## Environment

Frontend Vercel env:

```text
VITE_DEMO_MODE=false
VITE_ENABLE_VIEWPORT_STATIONS=true
VITE_ENABLE_LLM_SEARCH=true
VITE_ENABLE_ROUTE_PLANNER=true
VITE_API_BASE_URL=https://<backend-demo-origin>
```

Backend env:

```text
DATABASE_URL=postgresql://...
CORS_ORIGINS_RAW=https://<frontend-demo-origin>
PORT=8000
```

Do not add a public-data `ServiceKey`, OpenAPI polling credential, partner key, or OCPI credential for this demo.

## Provision Flow

1. Create managed Postgres.
2. Enable PostGIS.
3. Deploy the backend image or service package.
4. Run the release DB command.
5. Verify DB row counts.
6. Deploy the Vercel frontend with DB-backed demo env.
7. Run backend API smoke checks.
8. Run frontend smoke checks.
9. Update the README live demo section only after public frontend and backend URLs exist.

Release DB command:

```powershell
cd backend
$env:DATABASE_URL='postgresql://...'
python scripts\deploy_demo_db.py
```

Docker release command:

```powershell
docker run --rm `
  -e DATABASE_URL='postgresql://...' `
  chargeflow-kr-api:demo `
  python scripts/deploy_demo_db.py
```

The command applies `app/db/schema.sql` and seeds `fixtures/synthetic-stations-7k.geojson`. Do not run it implicitly on every web process startup.

## DB Smoke

Use managed provider SQL console or `psql`:

```sql
SELECT COUNT(*) AS station_count FROM stations;
SELECT COUNT(*) AS connector_count FROM connectors;
SELECT COUNT(*) AS status_event_count FROM status_events;
SELECT COUNT(*) AS stations_without_geom FROM stations WHERE geom IS NULL;
```

Expected seeded snapshot counts:

```text
station_count=7000
connector_count=7000
status_event_count>=7000
stations_without_geom=0
```

Check fixture source and hash:

```sql
SELECT source, raw_file_hash, COUNT(*) AS rows
FROM status_events
GROUP BY source, raw_file_hash
ORDER BY rows DESC;
```

Expected source:

```text
synthetic-stations-7k
```

## Backend Smoke

Health:

```powershell
curl.exe https://<backend-demo-origin>/healthz
```

Station bbox:

```powershell
curl.exe "https://<backend-demo-origin>/api/stations?bbox=126,33,128,38&limit=50"
```

Search:

```powershell
curl.exe -X POST "https://<backend-demo-origin>/api/search/chargers" `
  -H "Content-Type: application/json" `
  -d '{"intent":"find_chargers","place":"Gangnam Station","radius_m":2000,"filters":{"min_kw":100,"connector_type":"DC"},"sort":"distance"}'
```

Route planner:

```powershell
curl.exe -X POST "https://<backend-demo-origin>/api/routes/charging-plan" `
  -H "Content-Type: application/json" `
  -d '{"route":{"id":"fixture-seoul-daejeon","polyline":[[126.978,37.5665],[127.0276,37.4979],[127.3845,36.3504]],"distance_km":165.2},"vehicle":{"battery_kwh":77.4,"current_soc":0.64,"target_arrival_soc":0.15,"consumption_kwh_per_km":0.18,"preferred_connector_types":["DC Combo"],"max_charging_kw":180},"constraints":{"corridor_width_km":3,"max_results":5}}'
```

Pass criteria:

- `/healthz` returns 200.
- `/api/stations` returns a FeatureCollection with DB-backed features.
- Search returns local DB-backed matches and synthetic snapshot freshness wording.
- Route planner returns deterministic recommendations for `fixture-seoul-daejeon`.

## Frontend Smoke

Open:

```text
https://<frontend-demo-origin>/
```

Pass criteria:

- Map loads.
- Summary panel shows `Data mode` as `Viewport API`.
- Loaded station count changes after pan or zoom.
- Assistant search returns local DB-backed charger results.
- Route planner draws the Seoul-Daejeon route and highlights recommendations.
- Browser network requests go to `https://<backend-demo-origin>/api/...`.
- No request loads `frontend/public/sample-chargers.json`.

## README Update Gate

Do not update the README live demo section until both public URLs exist:

```text
https://<frontend-demo-origin>
https://<backend-demo-origin>
```

When URLs exist, the README wording must say `synthetic snapshot demo` and must not say live, current, or real-time availability for synthetic rows.

## Rollback

Frontend rollback:

- Promote the previous Vercel deployment.
- No DB rollback is required for frontend-only changes.

Backend rollback:

- Roll back to the previous web service revision.
- Keep DB rows unchanged unless the backend revision requires an older schema.

DB rollback:

- Prefer recreating the demo DB or reseeding from `fixtures/synthetic-stations-7k.geojson`.
- Record the fixture source and `raw_file_hash`.
- Do not hand-edit demo rows without recording why.

Emergency fallback:

- Set frontend env to static smoke mode:

```text
VITE_DEMO_MODE=true
VITE_ENABLE_VIEWPORT_STATIONS=false
VITE_ENABLE_LLM_SEARCH=false
VITE_ENABLE_ROUTE_PLANNER=false
```

- Label the fallback publicly as static/local demo behavior, not the DB-backed synthetic snapshot demo.
