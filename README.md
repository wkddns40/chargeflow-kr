# ChargeFlow KR

Production-oriented Korean EV charging intelligence platform.

ChargeFlow KR is the next-generation successor to EV-STATION. It keeps the proven React, MapLibre, and deck.gl map foundation, then rebuilds the data path around PostGIS, viewport queries, vector tiles, file-dataset ingestion, and later natural-language spatial search.

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
