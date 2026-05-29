# ChargeFlow KR

한국 전기차 충전 인프라를 PostGIS, FastAPI, React 지도 UI로 탐색하는 대시보드.

ChargeFlow KR은 [EV-STATION](https://github.com/wkddns40/ev-station)의 차세대 프로젝트입니다. 기존 MapLibre + deck.gl 지도 기반은 유지하되, 데이터 경로를 PostGIS viewport query, 7k synthetic snapshot, 자연어 충전소 검색, 경로 기반 충전 계획으로 확장합니다.

[![CI](https://github.com/wkddns40/chargeflow-kr/actions/workflows/ci.yml/badge.svg)](https://github.com/wkddns40/chargeflow-kr/actions/workflows/ci.yml)
[![Live demo](https://img.shields.io/badge/demo-chargeflow--kr.vercel.app-blue?logo=vercel)](https://chargeflow-kr.vercel.app/)
[![API](https://img.shields.io/badge/API-chargeflow--kr--api.vercel.app-111827?logo=fastapi)](https://chargeflow-kr-api.vercel.app/healthz)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178c6?logo=typescript)](frontend/tsconfig.json)
[![Vite](https://img.shields.io/badge/Vite-8.x-646cff?logo=vite)](frontend/vite.config.ts)

> 한국어 README가 기본 문서입니다. 기존 `README.ko.md`는 이 문서로 통합되었습니다.

## 목차

- [라이브 데모](#라이브-데모)
- [기능](#기능)
- [기술 스택](#기술-스택)
- [아키텍처](#아키텍처)
- [로컬 개발](#로컬-개발)
- [스크립트 목록](#스크립트-목록)
- [프로젝트 구조](#프로젝트-구조)
- [데이터와 배포](#데이터와-배포)
- [출처](#출처)
- [라이선스](#라이선스)

## 라이브 데모

**👉 [chargeflow-kr.vercel.app](https://chargeflow-kr.vercel.app/)** — Supabase PostGIS에 적재한 synthetic 7k 충전소 데이터를 FastAPI가 viewport 단위로 제공하는 데모입니다.

- API health: [chargeflow-kr-api.vercel.app/healthz](https://chargeflow-kr-api.vercel.app/healthz)
- Frontend data mode: `Viewport API`
- Backend source: `synthetic-stations-7k`

![ChargeFlow KR 라이브 지도](docs/screenshots/01-live-map.png)

프로덕션 프론트엔드 빌드 환경:

```text
VITE_DEMO_MODE=false
VITE_ENABLE_VIEWPORT_STATIONS=true
VITE_ENABLE_LLM_SEARCH=true
VITE_ENABLE_ROUTE_PLANNER=true
VITE_API_BASE_URL=https://chargeflow-kr-api.vercel.app
```

## 기능

| | |
|---|---|
| PostGIS viewport query | 현재 지도 bbox 기준으로 충전소를 가져옵니다. 7k fixture 전체를 프론트 bundle에 넣지 않고 `/api/stations?bbox=...&limit=...`로 조회합니다. |
| 지도 시각화 | React, MapLibre, deck.gl `ScatterplotLayer`로 충전소 상태와 출력 규모를 지도 위에 렌더링합니다. |
| 명령형 충전소 검색 | `POST /api/search/chargers`가 장소, 반경, 출력, 상태, 커넥터 조건을 검증된 command로 받아 후보 충전소를 반환합니다. |
| 자유 채팅 검색 | `POST /api/search/chargers/nl`이 자연어를 OpenAI Responses API 또는 deterministic fallback으로 command로 변환한 뒤 검색합니다. |
| 경로 기반 충전 계획 | frontend deterministic fixture의 route polyline을 `POST /api/routes/charging-plan`으로 보내고, backend가 route corridor 주변 충전 후보를 점수화합니다. 외부 route API나 임의 polyline 생성은 사용하지 않습니다. |
| API 메타데이터 | `/api/stations`는 `count`/`limit`/`source`, search는 `data_freshness`/`source`/`result_limit`, route planner는 `limitations`와 조건부 `snapshot_date`/`freshness_label`을 반환합니다. |
| 배포 분리 | Vercel frontend와 Vercel FastAPI backend를 분리하고, backend만 DB credentials를 소유합니다. |

## 기술 스택

| 레이어 | 도구 |
|---|---|
| 프론트엔드 | React 18, TypeScript 6 strict, Vite 8 |
| 지도 | MapLibre GL, `react-map-gl`, deck.gl |
| 데이터 패칭 | TanStack Query, viewport-aware API client |
| 백엔드 | FastAPI, Pydantic Settings, psycopg 3 |
| 데이터베이스 | Supabase Postgres + PostGIS |
| 검색/계획 로직 | local command schema, OpenAI structured parser, DB-backed place resolver, route corridor, LangGraph route planner |
| 테스트 | Vitest 4, pytest 9, FastAPI TestClient |
| CI/CD | GitHub Actions, Vercel production deployments |
| 호스팅 | Vercel frontend, Vercel Python serverless API |

## 아키텍처

### 런타임 데이터 흐름

```mermaid
flowchart LR
    user["사용자 브라우저"] -->|HTTPS| frontend["Vercel Frontend<br/>React + Vite SPA"]
    frontend -->|MapLibre style/tiles| tiles["OpenFreeMap / OSM tiles"]
    frontend -->|GET /api/stations?bbox&limit| api["Vercel FastAPI<br/>api/index.py"]
    frontend -->|POST /api/search/chargers| api
    frontend -->|POST /api/search/chargers/nl| api
    frontend -->|POST /api/routes/charging-plan| api

    api -->|optional NL parse| openai["OpenAI Responses API<br/>gpt-4o-mini"]
    api -->|psycopg<br/>PostGIS bbox query| db[(Supabase Postgres<br/>PostGIS)]
    api -->|validated JSON| frontend
    frontend -->|render| deck["deck.gl WebGL layers"]
    deck --> map["지도 마커 / 경로 / 상세 패널"]
```

프론트엔드 서버가 API를 대신 호출하는 구조가 아니라, 브라우저에서 실행되는 SPA가 `VITE_API_BASE_URL`의 backend origin으로 직접 `fetch`합니다. 따라서 production backend는 frontend origin을 CORS로 허용해야 합니다.

### 배포 흐름

```mermaid
flowchart TD
    push["main push / force push"] --> actions["GitHub Actions<br/>Vercel Production Deploy"]
    actions --> frontendBuild["Frontend<br/>vercel pull / build / deploy"]
    actions --> backendBuild["Backend<br/>setup Python + uv<br/>vercel pull / build / deploy"]

    frontendBuild --> frontendProd["Vercel Production<br/>chargeflow-kr"]
    backendBuild --> backendProd["Vercel Production<br/>chargeflow-kr-api"]

    disabled["Vercel Git auto-deploy OFF<br/>Preview auto-deploy 제외"] -.-> frontendProd
    disabled -.-> backendProd
```

### 기능별 흐름

| 기능 | Frontend | Backend | External | DB |
|---|---|---|---|---|
| 지도 viewport 조회 | bbox 계산 후 `/api/stations` 호출 | bbox 검증, limit 정규화 | OpenFreeMap tiles | `stations`, `connectors` PostGIS bbox query |
| typed search | `/api/search/chargers` 호출 | command validation, place resolver, 필터링 | 없음 | bbox prefilter |
| free-text chat | `/api/search/chargers/nl` 호출 | OpenAI parser fallback 포함, resolver, clarification 처리 | OpenAI Responses API | bbox prefilter |
| route planner | deterministic fixture polyline 선택 | route corridor bbox 계산, 충전 후보 점수화 | 없음 | route 주변 station fetch |
| 지도 렌더 | deck.gl `ScatterplotLayer`, `PathLayer` | 없음 | MapLibre/OpenFreeMap | 없음 |

관련 문서:

- [아키텍처 메모](docs/ARCHITECTURE.md) - 최신 런타임 데이터 흐름, 배포 구조, 기능별 책임 경계를 정리합니다.
- [DB-backed demo deployment](docs/demo-db-backed-deployment.md)
- [EV-STATION 마이그레이션](docs/MIGRATION_FROM_EV_STATION.md)
- [Phase 6A scale map](docs/phase-6a-scale-map.md)
- [Phase 6C LLM search](docs/phase-6c-llm-search.md)
- [Phase 6D route planner](docs/phase-6d-route-planner.md)

## 로컬 개발

백엔드:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH='.'
$env:DATABASE_URL='postgresql://chargeflow:chargeflow@localhost:5432/chargeflow'
uvicorn app.main:app --reload
```

프론트엔드:

```powershell
cd frontend
npm ci
npm run dev
```

기본 로컬 프론트엔드 설정은 `frontend/.env.example`을 따릅니다.

```text
VITE_DEMO_MODE=true
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_VIEWPORT_STATIONS=false
VITE_ENABLE_LLM_SEARCH=false
VITE_ENABLE_ROUTE_PLANNER=false
```

DB-backed 로컬 모드는 FastAPI backend를 먼저 실행한 뒤 아래 값을 켭니다.

```powershell
$env:VITE_DEMO_MODE='false'
$env:VITE_ENABLE_VIEWPORT_STATIONS='true'
$env:VITE_ENABLE_LLM_SEARCH='true'
$env:VITE_ENABLE_ROUTE_PLANNER='true'
$env:VITE_API_BASE_URL='http://localhost:8000'
npm run dev
```

## 스크립트 목록

| 명령 | 효과 |
|---|---|
| `cd frontend && npm run dev` | Vite 개발 서버 실행 |
| `cd frontend && npm run test` | Vitest 테스트 실행 |
| `cd frontend && npm run typecheck` | TypeScript `tsc --noEmit` |
| `cd frontend && npm run build` | 프론트엔드 프로덕션 빌드 |
| `cd frontend && npm run build:demo` | Vercel demo용 빌드 |
| `cd frontend && npm run preview` | 빌드 결과 로컬 preview |
| `cd backend && pytest` | 백엔드 pytest 실행 |
| `cd backend && uvicorn app.main:app --reload` | FastAPI 개발 서버 실행 |
| `python backend/scripts/generate_synthetic_stations.py --count 7000 --seed 42` | synthetic 7k fixture 생성 |
| `cd backend && python scripts/deploy_demo_db.py` | schema 적용 + synthetic fixture seed |
| `cd backend && python scripts/seed_demo_db.py` | synthetic fixture만 seed |

## 프로젝트 구조

```text
chargeflow-kr/
├── frontend/
│   ├── src/
│   │   ├── components/map/       # 지도 셸
│   │   ├── components/search/    # 검색 assistant 패널
│   │   ├── components/route/     # 경로 계획 패널
│   │   ├── hooks/                # station loading hooks
│   │   ├── lib/                  # geo, search, route planner client
│   │   └── types/                # charger domain types
│   ├── public/
│   │   └── sample-chargers.json  # 정적 smoke fixture
│   ├── deploy/README.md          # Vercel frontend 배포 가이드
│   └── package.json
├── backend/
│   ├── api/index.py              # Vercel Python function entrypoint
│   ├── app/
│   │   ├── api/                  # health, stations, search, routes endpoints
│   │   ├── core/                 # runtime settings
│   │   ├── db/                   # PostGIS schema + repository
│   │   └── schemas/              # response/request schemas
│   ├── fixtures/                 # synthetic station fixture
│   ├── scripts/                  # DB deploy/seed/generator scripts
│   ├── tests/                    # pytest suite
│   ├── deploy/README.md          # backend 배포 가이드
│   └── vercel.json               # Vercel API rewrite
├── docs/
│   ├── screenshots/              # README 캡처
│   ├── phase-6a-scale-map.md
│   ├── phase-6b-file-status.md
│   ├── phase-6c-llm-search.md
│   └── phase-6d-route-planner.md
├── .github/workflows/ci.yml      # frontend + backend CI
├── docker-compose.yml            # local Postgres/PostGIS
└── LICENSE                       # MIT
```

## 데이터와 배포

- 프론트엔드는 synthetic 7k fixture를 직접 bundle하지 않습니다.
- Supabase PostGIS의 `stations`, `connectors`, `status_events`가 충전소/상태 demo API source입니다.
- `places`, `place_aliases`는 typed search와 free-text chat의 DB-backed place resolver source입니다.
- Vercel frontend는 `VITE_API_BASE_URL`로 FastAPI backend origin만 참조합니다.
- CORS origin은 production frontend인 `https://chargeflow-kr.vercel.app`로 제한됩니다.

## 출처

지도, 타입, 일부 geo utility의 출발점은 [EV-STATION](https://github.com/wkddns40/ev-station)입니다. EV-STATION은 기존 대시보드로 보존하고, ChargeFlow KR은 PostGIS-first 제품형 successor로 진행합니다.

## 라이선스

MIT — [`LICENSE`](LICENSE) 참조.
