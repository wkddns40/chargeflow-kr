# Phase 6D Route Planner Design

Phase 6D adds a route-aware charging plan MVP for ChargeFlow KR. The first target is not full navigation. It is a backend-owned recommendation path that ranks charging stop candidates from a route corridor, vehicle profile, station data, and imported availability freshness.

This document starts with task 4.1.1: route planner MVP scope. Later 4.1 tasks will add UI assumptions, explicit weather and traffic exclusions, vehicle and route schemas, SoC estimates, charger penalty rules, and dependency review.

## MVP Scope

The MVP answers one question:

```text
Given a route polyline, vehicle state, and local charger dataset, which charging stops should be considered first?
```

Included:

- Accept a route shape from a local fixture or typed request payload.
- Accept a vehicle profile with battery capacity, current SoC, target arrival SoC, consumption, and connector preference.
- Search charger candidates near the route corridor using local station data.
- Estimate whether candidates are reachable with a simple deterministic energy model.
- Rank candidates by reachability, connector fit, charging power, imported availability, freshness, and fallback usefulness.
- Return a structured recommendation response that the frontend or LLM shell can display without inventing route facts.
- Keep route planning deterministic and testable with local fixtures.

Deferred:

- Turn-by-turn navigation.
- External route API calls.
- Live traffic, weather, elevation, road grade, tolls, and speed profiles.
- Real-time charger polling.
- Reservation, pricing, payment, and wait-time integrations.
- Multi-day trip planning and user account persistence.
- Frontend route drawing or trip editing UI beyond later smoke hooks.

## Product Boundary

The MVP is a charger-stop recommender, not a navigation app. It may say that a charger is a good candidate along a provided route. It must not claim that it found the fastest driving route, current traffic conditions, exact arrival time, or live charger occupancy.

Route geometry is input data. Backend route planner code should treat it as trusted local fixture data or validated request data, then operate only inside the local dataset boundary already established by Phase 6A and Phase 6B.

## ABRP-Inspired Route Planning UI Assumptions

Reference checked: ABRP official home page, 2026-05-22. The relevant product pattern is destination-first EV planning with vehicle-aware charging stops, charger filtering, route alternatives, and live-data reliability features. ChargeFlow KR should borrow the planning shape only, not ABRP branding, copy, screenshots, or assets.

Future route-planning UI assumptions:

- Keep the map as the primary workspace, with route and charging stops visible together.
- Start with compact origin, destination, vehicle, departure SoC, and target arrival SoC inputs.
- Show recommended charging stops as both map callouts and an ordered stop list.
- For each stop, surface why it was selected: reachability, connector fit, power, availability/freshness, and fallback value.
- Make constraints visible as controls, not hidden settings: connector preference, minimum power, maximum detour/corridor width, and target SoC.
- Show local-data limitations near the plan result, especially no live traffic, no weather, no real-time polling, and no external route API.
- Support later "apply to map" behavior from LLM search without allowing the assistant to invent route facts.
- Preserve dense operational layout; avoid marketing hero sections and decorative route storytelling.

## Weather and Traffic Exclusions

Phase 6D must keep weather and traffic out of the MVP calculation.

Excluded inputs:

- live traffic speed,
- incident and congestion feeds,
- weather forecasts,
- wind speed or wind direction,
- road temperature,
- precipitation,
- elevation-sensitive weather adjustments.

Route planner code may accept a static route polyline and static distance estimates. It must not fetch, model, cache, or infer traffic or weather conditions. If future tests need deterministic examples, they should use fixed fixture values that are named as artificial route metadata, not live traffic or weather.

Response text must not claim:

- fastest route under current traffic,
- weather-adjusted energy consumption,
- real-time rerouting,
- live ETA,
- live road condition awareness.

The only allowed near-term energy estimate is a simple vehicle-profile calculation from route distance, battery capacity, SoC, and consumption assumptions. Any traffic or weather integration needs a later task with its own data source, failure mode, privacy review, and tests.

## Vehicle Profile Schema

Route planner requests should include one vehicle profile object. It represents the planning assumptions for a single trip, not a saved user vehicle.

```json
{
  "battery_kwh": 77.4,
  "current_soc": 0.64,
  "target_arrival_soc": 0.15,
  "consumption_kwh_per_km": 0.18,
  "preferred_connector_types": ["DC Combo"],
  "max_charging_kw": 180
}
```

Fields:

| Field | Type | Required | Unit | Notes |
| --- | --- | --- | --- | --- |
| `battery_kwh` | number | yes | kWh | Usable battery capacity for range math. |
| `current_soc` | number | yes | ratio | Current battery state of charge, expressed as `0.0` to `1.0`. |
| `target_arrival_soc` | number | yes | ratio | Minimum desired SoC at destination or next required stop. |
| `consumption_kwh_per_km` | number | yes | kWh/km | Static consumption assumption for MVP energy estimates. |
| `preferred_connector_types` | string array | yes | n/a | Connector allowlist matched against local connector values, such as `DC Combo`, `CHAdeMO`, or `AC Type 2`. |
| `max_charging_kw` | number | yes | kW | Vehicle-side charging cap used when comparing station power. |

Validation notes for later 4.2 implementation:

- `battery_kwh`, `consumption_kwh_per_km`, and `max_charging_kw` must be positive.
- `current_soc` and `target_arrival_soc` must be between `0.0` and `1.0`.
- `target_arrival_soc` may be greater than `current_soc`; that should make some routes unreachable rather than fail schema validation.
- `preferred_connector_types` must contain at least one supported local connector type.
- Unknown connector values should fail validation with a typed error, not silently degrade to all connectors.

## Route Request and Response Schema

Future route planner endpoint:

```text
POST /api/routes/charging-plan
```

Request shape:

```json
{
  "route": {
    "id": "fixture-seoul-daejeon",
    "polyline": [
      [126.9780, 37.5665],
      [127.0276, 37.4979],
      [127.3845, 36.3504]
    ],
    "distance_km": 165.2
  },
  "vehicle": {
    "battery_kwh": 77.4,
    "current_soc": 0.64,
    "target_arrival_soc": 0.15,
    "consumption_kwh_per_km": 0.18,
    "preferred_connector_types": ["DC Combo"],
    "max_charging_kw": 180
  },
  "constraints": {
    "corridor_width_km": 3.0,
    "max_results": 5
  }
}
```

Request fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `route.id` | string | no | Fixture or caller-provided route identifier for traceability. |
| `route.polyline` | array of `[lon, lat]` | yes | Ordered EPSG:4326 route coordinates. Must contain at least two points. |
| `route.distance_km` | number | yes | Static route distance used by MVP energy estimate. |
| `vehicle` | object | yes | Vehicle profile schema from this document. |
| `constraints.corridor_width_km` | number | no | Search width around the route. Backend default is `3.0` km. |
| `constraints.max_results` | integer | no | Maximum recommendation count returned after sorting. |

### Route polyline fixture shape

Small deterministic route fixtures for 4.3 live under `backend/fixtures/routes/` and use one route object per file. The shape mirrors `route` in the request payload without vehicle or constraint fields:

```json
{
  "id": "fixture-seoul-daejeon",
  "distance_km": 165.2,
  "polyline": [
    [126.978, 37.5665],
    [127.0276, 37.4979],
    [127.3845, 36.3504]
  ]
}
```

Fixture fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | string | yes | Stable fixture identifier used in tests and response traceability. |
| `distance_km` | number | yes | Positive static route distance; not provider-fetched or traffic-aware. |
| `polyline` | array of `[lon, lat]` | yes | Ordered EPSG:4326 route coordinates. Must contain at least two points. |

The typed backend shape is `RoutePolylineFixture` in `backend/route_corridor.py`. Fixtures must not include traffic, weather, external provider IDs, credentials, or route quality claims.

### Route corridor width config

The MVP backend default is `DEFAULT_CORRIDOR_WIDTH_KM = 3.0` in `backend/route_corridor.py`. This keeps route candidate search narrow enough for deterministic local fixtures while still covering chargers close to Korean expressway and arterial-road routes.

The value is a local planning assumption, not a provider-derived route quality signal. Later endpoint code may accept `constraints.corridor_width_km`, but omitted values should use this default.

### Approximate corridor distance logic

`backend/route_corridor.py` calculates station distance from the route by projecting lon/lat coordinates into a local kilometer plane and measuring the shortest distance to each polyline segment. Corridor inclusion is inclusive: `distance_to_route_km(point, polyline) <= corridor_width_km`.

This is deterministic local geometry for MVP candidate filtering. It is not turn-by-turn routing, travel-time estimation, or provider-grade road-network distance.

Candidate filtering uses `filter_candidates_by_route_corridor(features, polyline, corridor_width_km)`. It returns GeoJSON station feature copies inside the corridor and adds `properties.distance_from_route_km` for later ranking. Input features are not mutated.

### Numeric precision assumptions

All route-corridor helper inputs are EPSG:4326 lon/lat floats and all computed distances are kilometers. The MVP uses a local equirectangular projection per segment calculation; this is acceptable for deterministic Korean route fixtures and kilometer-scale corridor filtering, but not for global geodesic accuracy.

Helpers should keep full float precision internally and should not round `distance_from_route_km`. Endpoint/response code may round later for display. Tests that assert exact geometry behavior should use explicit tolerances; current route-corridor tests use `1e-9` km for deterministic equality checks.

Response shape:

```json
{
  "route_id": "fixture-seoul-daejeon",
  "summary": {
    "distance_km": 165.2,
    "estimated_energy_kwh": 29.74,
    "start_soc": 0.64,
    "target_arrival_soc": 0.15,
    "minimum_required_soc": 0.38,
    "reachable_without_stop": true
  },
  "recommendations": [
    {
      "station_id": "CFL-SYN-01234",
      "name": "Synthetic Seoul Fast Charger",
      "connector_type": "DC Combo",
      "max_kw": 150,
      "distance_from_route_km": 0.8,
      "route_distance_km": 42.5,
      "estimated_arrival_soc": 0.54,
      "score": 0.91,
      "reasons": [
        "connector_match",
        "reachable",
        "high_power",
        "fresh_availability"
      ]
    }
  ],
  "meta": {
    "source": "local-dataset",
    "snapshot_date": "2026-05-19",
    "freshness_label": "fresh",
    "limitations": [
      "Route geometry is provided input, not generated by an external route API.",
      "No live traffic or weather is used."
    ]
  }
}
```

Response rules:

- `summary` contains deterministic energy and SoC estimates from static request inputs.
- `recommendations` are ordered by the later stop optimizer score.
- `reasons` must use a small allowlist so UI and LLM summaries can explain results without inventing facts.
- `meta.limitations` must be preserved by frontend and assistant responses.
- Errors should be typed validation errors for invalid route geometry, vehicle profile, constraints, or empty local data.

## Simple SoC Estimate Model

The MVP uses a deterministic distance-based estimate only. It does not include speed, traffic, weather, elevation, battery temperature, charging curve, accessory load, or regenerative braking.

Whole-route estimate:

```text
estimated_energy_kwh = route.distance_km * vehicle.consumption_kwh_per_km
soc_delta = estimated_energy_kwh / vehicle.battery_kwh
estimated_arrival_soc = vehicle.current_soc - soc_delta
minimum_required_soc = vehicle.target_arrival_soc + soc_delta
reachable_without_stop = estimated_arrival_soc >= vehicle.target_arrival_soc
```

Candidate-stop estimate:

```text
candidate_energy_kwh = candidate.route_distance_km * vehicle.consumption_kwh_per_km
candidate_soc_delta = candidate_energy_kwh / vehicle.battery_kwh
candidate_estimated_arrival_soc = vehicle.current_soc - candidate_soc_delta
candidate_reachable = candidate_estimated_arrival_soc >= vehicle.target_arrival_soc
```

Rules:

- Clamp display values to `0.0` through `1.0`, but keep internal validation strict so impossible routes can still be detected.
- Treat `target_arrival_soc` as the safety floor for destination and candidate-stop reachability until a later charger-arrival SoC field exists.
- If `estimated_arrival_soc` is below `target_arrival_soc`, return recommendations with `reachable_without_stop=false` instead of pretending the route is impossible to analyze.
- `minimum_required_soc` is a planning threshold, not a vehicle reading.
- Round response values for display only; tests should compare deterministic numeric values with explicit tolerance.

## Charger Penalty Rules

Stop optimizer scoring starts from a local candidate list and applies deterministic penalties. The exact numeric weights belong in 4.4, but the rule order is defined here.

Hard filters:

- Exclude candidates outside the route corridor.
- Exclude candidates missing valid coordinates.
- Exclude candidates with no connector compatible with `preferred_connector_types`.

Penalty inputs:

| Condition | Rule |
| --- | --- |
| `candidate_reachable=false` | Apply the largest penalty; include only as fallback when no reachable candidate exists. |
| Connector mismatch | Exclude by default. If a later fallback mode allows mismatch, mark reason `connector_mismatch_fallback`. |
| Lower station power | Penalize chargers below `min(vehicle.max_charging_kw, station.max_kw)` preference; do not reward power above vehicle cap. |
| Stale availability | Penalize stale imported status using Phase 6B freshness rules. |
| Unknown availability | Penalize below fresh `available`, but above confirmed `offline`. |
| Confirmed `occupied` | Penalize below `available`; keep visible when route coverage is sparse. |
| Confirmed `offline` | Apply severe penalty; include only as fallback with clear reason. |
| Larger route detour | Penalize higher `distance_from_route_km`. |
| Duplicate station cluster | Penalize near-duplicate stops from the same station or very close coordinates after the best connector candidate is selected. |

Reason allowlist:

- `connector_match`
- `reachable`
- `unreachable_fallback`
- `high_power`
- `low_power_penalty`
- `fresh_availability`
- `aging_availability`
- `stale_availability_penalty`
- `unknown_availability_penalty`
- `occupied_penalty`
- `offline_fallback`
- `short_detour`
- `long_detour_penalty`
- `cluster_duplicate_penalty`

Rules:

- Penalties must be deterministic for identical inputs.
- Availability penalties use imported snapshot state only; no live polling claims.
- Reachable candidates sort before fallback candidates unless a later explicit emergency mode changes this.
- The response must expose enough `reasons` for UI and LLM summaries to explain ranking without exposing private scoring constants.
- Fallback inclusion is allowed to avoid empty responses, but fallback rows must be labeled clearly.

## External Route API Dependency Review

Last reviewed: 2026-05-22.

Phase 6D does not require an external route provider. The route planner accepts route geometry as input and ranks charging stops against local station/status data.

Reviewed provider classes not used:

- Google Maps Directions API
- Mapbox Directions API
- Naver Maps Directions API
- Kakao Mobility route APIs
- Tmap route APIs
- OSRM hosted services
- OpenRouteService
- GraphHopper
- Valhalla hosted services

Repo search result:

- No route-provider SDK or API client is present.
- No backend route provider environment variable is present.
- No route planner code performs outbound route requests.
- Existing outbound-style frontend calls only target local ChargeFlow KR APIs or OpenFreeMap map tiles.

Allowed MVP behavior:

- Accept `route.polyline` from a local fixture or validated request payload.
- Accept `route.distance_km` as static caller-provided input.
- Use local bbox/corridor and station/status data for charger candidate selection.

Disallowed MVP behavior:

- Fetch route geometry from external APIs.
- Infer live route alternatives from model memory.
- Store third-party route API credentials.
- Add route-provider SDK dependencies.
- Claim traffic-aware or provider-generated route quality.

If a future route API is added, it needs a new task with provider selection, credential handling, request caching, quota/error behavior, privacy review, and tests.

## Dependencies

Required existing pieces:

- `GET /api/stations` and station query helpers from Phase 6A.
- Local station fixture or later PostGIS station data.
- Status-event snapshot and freshness rules from Phase 6B.
- Typed LLM/search safety rules from Phase 6C for any assistant-facing route query.

New implementation work starts in later 4.x tasks:

- `backend/vehicle_profile.py`
- route corridor filtering helper
- stop optimizer helper
- backend tests for reachability, corridor inclusion, and deterministic ordering

## Non-Goals

The MVP must not expand into:

- public-data API credential work,
- external map routing providers,
- weather or traffic integrations,
- a full ABRP clone,
- frontend-heavy trip planning UI before backend contracts exist.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "MVP Scope|External route API|traffic|weather|vehicle profile|route corridor"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "ABRP|origin|destination|charging stops|ordered stop list|apply to map"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Weather and Traffic Exclusions|live traffic speed|weather forecasts|live ETA|weather-adjusted"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Vehicle Profile Schema|battery_kwh|current_soc|target_arrival_soc|consumption_kwh_per_km|preferred_connector_types|max_charging_kw"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Route Request and Response Schema|POST /api/routes/charging-plan|polyline|distance_km|recommendations|meta.limitations"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Simple SoC Estimate Model|estimated_energy_kwh|soc_delta|estimated_arrival_soc|reachable_without_stop|candidate_reachable"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Charger Penalty Rules|Hard filters|candidate_reachable=false|stale_availability_penalty|offline_fallback|fallback"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "External Route API Dependency Review|No route-provider SDK|route.polyline|route.distance_km|Disallowed MVP behavior|credential handling"
rg -n "route API|external route|Directions|directions|OSRM|OpenRouteService|GraphHopper|Google Maps|Mapbox Directions|Naver|Kakao|Tmap|Valhalla|routing provider|route provider" D:\fleet\chargeflow-kr --glob "!frontend/node_modules/**" --glob "!backend/.venv/**" --glob "!backend/.pytest_cache/**"
```

Pass conditions:

- Document exists.
- MVP scope defines charger-stop recommendation, not full navigation.
- ABRP-inspired route planning UI assumptions are documented without copying ABRP assets.
- External route APIs are deferred.
- Weather and traffic exclusions are explicit and forbid live traffic, forecasts, live ETA, and weather-adjusted consumption.
- Vehicle profile schema documents fields, units, and validation notes for later implementation.
- Route request and response schema documents endpoint shape, route fields, recommendation fields, and response limitations.
- Simple SoC estimate model documents deterministic route and candidate formulas without weather or traffic inputs.
- Charger penalty rules define hard filters, penalty inputs, reason allowlist, and fallback labeling.
- External route API dependency review confirms route providers are not required and remain deferred.
- Later schema and optimizer work remains explicitly deferred.
