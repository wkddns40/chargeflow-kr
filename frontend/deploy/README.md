# Frontend Demo Deployment

Deploy this package as a Vercel project with `frontend/` as the project root.

## Vercel Settings

Use these project settings:

```text
Framework Preset: Vite
Install Command: npm ci
Build Command: npm run build:demo
Output Directory: dist
```

`vercel.json` stores the same build settings for the frontend project.

## Demo Environment

Set these Vercel environment variables for the public synthetic snapshot demo:

```text
VITE_DEMO_MODE=false
VITE_ENABLE_VIEWPORT_STATIONS=true
VITE_ENABLE_LLM_SEARCH=true
VITE_ENABLE_ROUTE_PLANNER=true
VITE_API_BASE_URL=https://<backend-demo-origin>
```

`VITE_API_BASE_URL` must point to the deployed FastAPI backend. Do not set it to `localhost` in Vercel.

The committed `.env.demo` file contains only non-secret feature flags. Vercel should still own the backend origin through `VITE_API_BASE_URL`.

With `VITE_ENABLE_VIEWPORT_STATIONS=true`, the map summary displays `Viewport API` as the data mode and fetches station rows from `/api/stations`.

## Local Static Smoke

Keep local static smoke mode on `.env.example`:

```text
VITE_DEMO_MODE=true
VITE_ENABLE_VIEWPORT_STATIONS=false
VITE_ENABLE_LLM_SEARCH=false
VITE_ENABLE_ROUTE_PLANNER=false
```

Run it with:

```bash
npm run dev
```

## Local DB Demo Build

For a local production-style build against a local backend:

```powershell
$env:VITE_API_BASE_URL='http://localhost:8000'
npm run build:demo
```

Then preview the built app:

```bash
npm run preview
```
