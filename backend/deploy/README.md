# Backend Demo Deployment

This package runs the synthetic snapshot demo API as a Dockerized FastAPI service.

## Runtime

Build from the `backend/` directory:

```bash
docker build -t chargeflow-kr-api:demo .
```

Run command used by the image:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```text
DATABASE_URL=postgresql://...
CORS_ORIGINS_RAW=https://<frontend-demo-origin>
PORT=8000
```

`PORT` is usually injected by the web service platform. Use `8000` for local image smoke tests.

Local image smoke:

```bash
docker run --rm -p 8000:8000 \
  -e PORT=8000 \
  -e DATABASE_URL=postgresql://chargeflow:chargeflow@host.docker.internal:5432/chargeflow \
  -e CORS_ORIGINS_RAW=http://localhost:3000 \
  chargeflow-kr-api:demo
```

Then verify:

```bash
curl http://localhost:8000/healthz
```

## Release DB Command

Run schema application and synthetic seed as a release job or manual one-shot command. Do not run this from the web process startup path.

From a backend checkout:

```bash
python scripts/deploy_demo_db.py
```

From the backend image:

```bash
docker run --rm \
  -e DATABASE_URL=postgresql://... \
  chargeflow-kr-api:demo \
  python scripts/deploy_demo_db.py
```

The command applies `app/db/schema.sql` and then seeds `fixtures/synthetic-stations-7k.geojson` through `scripts/seed_demo_db.py`. Both operations are repeatable for the same fixture and hash.

Useful release flags:

```bash
python scripts/deploy_demo_db.py --skip-schema
python scripts/deploy_demo_db.py --skip-seed
python scripts/deploy_demo_db.py --fixture fixtures/synthetic-stations-7k.geojson
```

Managed Postgres must have PostGIS available. If the provider requires extension setup outside app credentials, enable PostGIS before running this command.
