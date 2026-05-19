# ChargeFlow KR

한국 전기차 충전소 인텔리전스 플랫폼입니다.

ChargeFlow KR은 EV-STATION의 차세대 후속 프로젝트입니다. React, MapLibre, deck.gl 기반 지도 구조는 유지하고, 데이터 경로는 PostGIS, viewport query, vector tile, 파일 데이터셋 ingestion, 이후 자연어 공간 검색을 기준으로 다시 설계합니다.

English README: [README.md](README.md)

## 범위

- 한국 충전소 대규모 시각화.
- PostGIS 중심 station / connector 모델.
- viewport-aware station API.
- MVT-ready map rendering path.
- 로그인 없는 공공 파일 데이터셋 ingestion.
- 향후 LLM 공간 검색 및 경로 기반 계획.

## 저장소 구조

```text
chargeflow-kr/
  frontend/        React + Vite + MapLibre + deck.gl
  backend/         FastAPI + PostGIS-oriented API skeleton
  docs/            Architecture and migration notes
  docker-compose.yml
```

## 로컬 개발

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

frontend 기본값은 `VITE_DEMO_MODE=true`이며 `frontend/public/sample-chargers.json`을 읽습니다.

## Live Demo

아직 ChargeFlow KR용 production live demo는 배포하지 않았습니다.

로컬 데모 모드:

- 기본 static smoke: `VITE_DEMO_MODE=true`, `frontend/public/sample-chargers.json` 사용.
- 실험적 viewport API: FastAPI backend를 실행한 뒤 `VITE_ENABLE_VIEWPORT_STATIONS=true`, `VITE_API_BASE_URL=http://localhost:8000` 설정.

커밋된 7k benchmark fixture는 frontend bundle에 포함하지 않습니다. backend `/api/stations?bbox=...&limit=...` 경로로만 제공합니다.

## Features

- React, MapLibre, deck.gl `ScatterplotLayer` 기반 한국 충전소 지도.
- 빠른 로컬 frontend 구동용 static smoke dataset.
- bbox API와 rendering 확인용 synthetic 7k benchmark fixture.
- `VITE_ENABLE_VIEWPORT_STATIONS` 뒤에 둔 viewport-aware station API path.
- stations, connectors, status events를 위한 PostGIS-oriented backend schema.
- 로그인 없는 공공 파일 데이터셋 ingestion plan.

synthetic benchmark fixture 생성:

```bash
python backend/scripts/generate_synthetic_stations.py --count 7000 --seed 42
```

## 성공 목표

- 충전소 7,000개를 인터랙티브하게 렌더링.
- 중급 노트북 기준 초기 지도 로드 3초 미만.
- 전체 dataset 다운로드 전에 viewport query 지원.
- 충전 가능 여부 답변에서 source와 snapshot metadata 보존.

## 출처

일부 map, type, geo utility code는 [EV-STATION](https://github.com/wkddns40/ev-station)에서 이식했습니다. EV-STATION은 portfolio dashboard로 유지하고, ChargeFlow KR은 product-scale successor로 진행합니다.
