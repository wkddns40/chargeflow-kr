# ChargeFlow KR

Production-oriented Korean EV charging intelligence platform.

ChargeFlow KR is the next-generation successor to EV-STATION. It keeps the proven React, MapLibre, and deck.gl map foundation, then rebuilds the data path around PostGIS, viewport queries, vector tiles, file-dataset ingestion, and later natural-language spatial search.

Korean README: [README.ko.md](README.ko.md)

## Scope

- Large-scale Korean charger visualization.
- PostGIS-first station and connector model.
- Viewport-aware station APIs.
- MVT-ready map rendering path.
- File-dataset ingestion for login-free public datasets.
- Future LLM spatial search and route-aware planning.

## Repository Layout

```text
chargeflow-kr/
  frontend/        React + Vite + MapLibre + deck.gl
  backend/         FastAPI + PostGIS-oriented API skeleton
  docs/            Architecture and migration notes
  docker-compose.yml
```

## Local Development

```bash
docker compose up -d db

cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

Frontend defaults to `VITE_DEMO_MODE=true`, reading `frontend/public/sample-chargers.json`.

## Live Demo

No production live demo is published for ChargeFlow KR yet.

Local demo modes:

- Default static smoke: `VITE_DEMO_MODE=true`, using `frontend/public/sample-chargers.json`.
- Experimental viewport API: run the FastAPI backend, then set `VITE_ENABLE_VIEWPORT_STATIONS=true` and `VITE_API_BASE_URL=http://localhost:8000`.

The committed 7k benchmark fixture is not bundled into the frontend. It is served through the backend `/api/stations?bbox=...&limit=...` path.

## Features

- Map-first Korean EV charger view using React, MapLibre, and deck.gl `ScatterplotLayer`.
- Static smoke dataset for fast local frontend startup.
- Synthetic 7k benchmark fixture for bbox API and rendering checks.
- Viewport-aware station API path behind `VITE_ENABLE_VIEWPORT_STATIONS`.
- PostGIS-oriented backend schema for stations, connectors, and status events.
- Login-free public file dataset ingestion plan.

Generate the synthetic benchmark fixture:

```bash
python backend/scripts/generate_synthetic_stations.py --count 7000 --seed 42
```

## Success Targets

- Render 7,000 chargers interactively.
- Keep initial map load under 3 seconds on a mid-range laptop.
- Support viewport queries before full dataset downloads.
- Preserve source and snapshot metadata for availability answers.

## Origin

Selected map, type, and geo utility code was migrated from [EV-STATION](https://github.com/wkddns40/ev-station). EV-STATION remains the portfolio dashboard; ChargeFlow KR is the product-scale successor.
