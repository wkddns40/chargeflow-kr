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

Route planner endpoint:

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
| `reference_time` | string | no | Optional ISO 8601 datetime for deterministic freshness scoring. If omitted, the endpoint uses the latest local station `status_updated_at` timestamp. |

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

Candidate filtering uses `filter_candidates_by_route_corridor(features, polyline, corridor_width_km, route_total_distance_km=None)`. It returns GeoJSON station feature copies inside the corridor and adds `properties.distance_from_route_km` for later ranking. When `route_total_distance_km` is provided and a feature does not already have `properties.route_distance_km`, it also estimates candidate progress along the provided polyline and scales that progress to the declared route distance. Input features are not mutated.

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
      "No live traffic or weather is used.",
      "Availability and reliability use imported snapshot data, not live polling or historical uptime.",
      "Fallback recommendations may include unreachable or offline chargers and must be labeled clearly."
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

## Stop Optimizer Shape

`backend/stop_optimizer.py` owns the route stop optimizer contract. It receives a normalized route, vehicle, and candidate list from earlier helpers; it returns recommendation rows that can be embedded directly in the route planner response.

Input shape:

```json
{
  "route_id": "fixture-seoul-daejeon",
  "route_distance_km": 165.2,
  "vehicle": {
    "battery_kwh": 77.4,
    "current_soc": 0.64,
    "target_arrival_soc": 0.15,
    "consumption_kwh_per_km": 0.18,
    "preferred_connector_types": ["DC Combo"],
    "max_charging_kw": 180
  },
  "candidates": [
    {
      "station_id": "CFL-SYN-01234",
      "name": "Synthetic Seoul Fast Charger",
      "connector_type": "DC Combo",
      "max_kw": 150,
      "distance_from_route_km": 0.8,
      "route_distance_km": 42.5,
      "status": "available",
      "status_updated_at": "2026-05-19T08:30:00+09:00"
    }
  ],
  "max_results": 5
}
```

Output recommendation shape:

```json
{
  "station_id": "CFL-SYN-01234",
  "name": "Synthetic Seoul Fast Charger",
  "connector_type": "DC Combo",
  "max_kw": 150,
  "distance_from_route_km": 0.8,
  "route_distance_km": 42.5,
  "estimated_arrival_soc": 0.54,
  "score": 0.91,
  "reasons": ["connector_match", "reachable", "high_power", "fresh_availability"]
}
```

Typed backend names:

| Shape | Backend type | Notes |
| --- | --- | --- |
| Candidate input row | `StopCandidate` | Normalized station candidate after route corridor filtering. |
| Reachable segment estimate | `ReachableSegmentEstimate` | Route-prefix energy and SoC estimate for one candidate segment. |
| Optimizer input | `StopOptimizerInput` | Route id, route distance, vehicle profile, candidates, and max result count. |
| Output row | `StopRecommendation` | Recommendation row ordered by later optimizer scoring. |
| Reason values | `OptimizerReason` / `OPTIMIZER_REASON_ALLOWLIST` | Closed reason set for UI and LLM summaries. |

### Reachable segment calculation

For 4.4 optimizer work, a segment means the route prefix from the origin to a candidate charging stop. `StopCandidate.route_distance_km` is the segment distance used by the MVP reachability estimate.

```text
segment_energy_kwh = candidate.route_distance_km * vehicle.consumption_kwh_per_km
segment_soc_delta = segment_energy_kwh / vehicle.battery_kwh
segment_estimated_arrival_soc = vehicle.current_soc - segment_soc_delta
segment_reachable = segment_estimated_arrival_soc >= vehicle.target_arrival_soc
```

`ReachableSegmentEstimate` stores the full calculation result. The optimizer should keep raw float values internally; endpoint response code may round later for display.

The backend implementation entry point is `estimate_reachable_segment(candidate, vehicle)`. It rejects non-finite or negative `candidate.route_distance_km`, then returns the full energy, SoC delta, estimated arrival SoC, target floor, and reachable boolean.

### Target arrival SoC rule

`vehicle.target_arrival_soc` is a hard safety floor for route and candidate reachability checks. A segment is reachable when `estimated_arrival_soc >= target_arrival_soc`; equality is reachable.

The optimizer must not reject a vehicle profile only because `target_arrival_soc` is greater than `current_soc`. That case represents an already-under-target trip state and should make route/candidate segments unreachable unless a later fallback rule intentionally includes them with `unreachable_fallback`.

`target_arrival_soc` is not a charging target, reserve recommendation, or dynamic route policy. It is a single deterministic threshold used by Phase 6D until a later task introduces richer charger-arrival and destination-arrival SoC controls.

The optimizer reachability function still validates `vehicle.current_soc` and `vehicle.target_arrival_soc` as finite values in `[0.0, 1.0]` at its boundary. This duplicates the vehicle profile guard intentionally so later callers cannot bypass the SoC floor rule with a malformed object.

### Charging power score

Charging power is a bounded score component, not the final recommendation score. It compares each candidate charger against the vehicle-side charging cap and must not reward station power that the vehicle cannot use.

```text
effective_charging_kw = min(candidate.max_kw, vehicle.max_charging_kw)
charging_power_score = effective_charging_kw / vehicle.max_charging_kw
```

Rules:

- `vehicle.max_charging_kw` must already be positive from vehicle profile validation.
- `candidate.max_kw` must be finite and positive before optimizer scoring; missing, non-finite, or non-positive values should be rejected or excluded before ranking.
- Clamp only by the vehicle cap. A 350 kW station and a 180 kW station both score `1.0` for a 180 kW vehicle.
- `charging_power_score >= 0.8` adds `high_power`.
- `charging_power_score < 0.5` adds `low_power_penalty`.
- Scores in `[0.5, 0.8)` are neutral for power reasons; other scoring dimensions still decide ordering.
- Keep raw float precision internally. Endpoint display code may round later.

Examples for a vehicle with `max_charging_kw=180`:

| `candidate.max_kw` | `effective_charging_kw` | `charging_power_score` | Reason |
| --- | --- | --- | --- |
| 350 | 180 | `1.0` | `high_power` |
| 180 | 180 | `1.0` | `high_power` |
| 150 | 150 | `0.833333...` | `high_power` |
| 50 | 50 | `0.277777...` | `low_power_penalty` |

### Imported availability score

Availability is a bounded score component based only on the latest imported file snapshot state. It is not live polling and must not imply real-time charger availability.

Status-event selection happens before stop optimizer scoring:

- Select the newest valid status event per connector from imported snapshots.
- Use `observed_at` as `candidate.status_updated_at` when present.
- If the source only has a snapshot-level timestamp, normalize it before candidate construction.
- If no usable timestamp exists, keep `candidate.status_updated_at=null` and treat freshness as `unknown`.
- If the timestamp is in the future relative to the route planner reference time, treat freshness as `unknown`.
- Break ties deterministically with the same precedence used by Phase 6B rollups: newer `observed_at`, then newer import receive time, then connector id.

Freshness labels reuse Phase 6B rules. Age is measured against the route planner reference time, using the request clock in production and a fixed clock in tests.

| Label | Age from `candidate.status_updated_at` |
| --- | --- |
| `fresh` | 0-2 days |
| `aging` | More than 2 days and up to 7 days |
| `stale` | More than 7 days |
| `unknown` | Missing or unusable timestamp |

Availability score table:

| `candidate.status` | Freshness | `availability_score` | Reasons | Inclusion |
| --- | --- | --- | --- | --- |
| `available` | `fresh` | `1.0` | `fresh_availability` | Normal candidate |
| `available` | `aging` | `0.8` | `aging_availability` | Normal candidate |
| `available` | `stale` | `0.45` | `stale_availability_penalty` | Normal candidate, lower confidence |
| `available` | `unknown` | `0.4` | `unknown_availability_penalty` | Normal candidate, lower confidence |
| `occupied` | `fresh` or `aging` | `0.35` | `occupied_penalty` | Keep visible when route coverage is sparse |
| `occupied` | `stale` | `0.25` | `occupied_penalty`, `stale_availability_penalty` | Keep visible when route coverage is sparse |
| `occupied` | `unknown` | `0.25` | `occupied_penalty`, `unknown_availability_penalty` | Keep visible when route coverage is sparse |
| `unknown` | Any | `0.25` | `unknown_availability_penalty` | Keep below known non-offline states |
| `offline` | Any | `0.0` | `offline_fallback` | Fallback only |

Rules:

- `candidate.status` must be one of `available`, `occupied`, `offline`, or `unknown`.
- Future status aliases are normalized before route planner candidates reach the optimizer.
- Stale `available` must not be treated as confidently available.
- Confirmed `offline` must not rank as a normal recommendation; include it only through fallback selection.
- Keep raw float precision internally. Endpoint display code may round later.
- Response metadata should still cite `snapshot_date`, `source`, or freshness labels when available, so UI and LLM summaries do not overstate availability.

### Reliability score input

Reliability is a later weighted score component built from already-normalized optimizer facts. For Phase 6D MVP, reliability does not mean historical uptime or live charger confidence; the current imported snapshot path does not provide enough long-running connector history for that claim.

MVP input bundle:

```json
{
  "availability_score": 1.0,
  "freshness_label": "fresh",
  "availability_fallback_only": false,
  "availability_reasons": ["fresh_availability"],
  "candidate_status": "available",
  "status_updated_at": "2026-05-19T08:30:00+09:00"
}
```

Input fields:

| Field | Source | Required | Notes |
| --- | --- | --- | --- |
| `availability_score` | `AvailabilityScore.score` | yes | Bounded `0.0` to `1.0` snapshot confidence from imported status. |
| `freshness_label` | `AvailabilityScore.freshness_label` | yes | One of `fresh`, `aging`, `stale`, or `unknown`. |
| `availability_fallback_only` | `AvailabilityScore.fallback_only` | yes | Preserves offline/fallback-only handling for final ranking. |
| `availability_reasons` | `AvailabilityScore.reasons` | yes | Existing reason allowlist values exposed for UI and LLM summaries. |
| `candidate_status` | `StopCandidate.status` | yes | Normalized status after alias handling outside the optimizer. |
| `status_updated_at` | `StopCandidate.status_updated_at` | no | Kept for traceability; missing, malformed, or future timestamps must already map to `freshness_label=unknown`. |

Rules:

- Build reliability input only after `score_availability(candidate, reference_time)` succeeds.
- The input object must be serializable and deterministic for identical candidate and reference-time values.
- Do not read live availability, traffic, weather, pricing, or external route-provider data.
- Do not infer station uptime, operator reliability, connector failure rate, or queue prediction from a single imported snapshot.
- Future history-backed fields such as `recent_observation_count`, `recent_available_ratio`, and `last_offline_at` are explicitly deferred until the status-event history is broad enough to support them.

Reliability weighting:

```text
reliability_raw_score = availability_score
reliability_weight = 0.30
reliability_score = 0.0 if availability_fallback_only else reliability_raw_score * reliability_weight
```

Rules:

- `reliability_raw_score` must stay bounded in `[0.0, 1.0]`.
- `reliability_score` is a weighted contribution for later final recommendation ranking, not a standalone normalized confidence value.
- Fallback-only candidates keep their trace fields and reasons, but their weighted reliability contribution is `0.0`.
- Weighting must preserve availability ordering; it must not move `occupied`, `unknown`, or `offline` above `available` candidates by adding extra freshness boosts.

### Stale penalty

Stale penalty is a small additive adjustment for final recommendation ranking. It is separate from `availability_score` and `reliability_score` so the optimizer can explain freshness loss directly without changing the imported availability contract.

Input:

```json
{
  "freshness_label": "stale",
  "availability_fallback_only": false,
  "availability_reasons": ["stale_availability_penalty"]
}
```

Penalty table:

| `freshness_label` | `stale_penalty` | Reasons | Notes |
| --- | --- | --- | --- |
| `fresh` | `0.0` | none | No freshness penalty. |
| `aging` | `0.0` | none | Aging is already reflected in `availability_score`; do not double-penalize. |
| `stale` | `0.12` | `stale_availability_penalty` | Applies to stale imported status regardless of candidate status. |
| `unknown` | `0.08` | `unknown_availability_penalty` | Applies when timestamp quality is not usable. |

Final ranking should subtract the penalty:

```text
stale_adjustment = -stale_penalty
```

Rules:

- Backend implementation entry point is `score_stale_penalty(availability)`.
- The implementation constants are `STALE_AVAILABILITY_PENALTY=0.12` and `UNKNOWN_FRESHNESS_PENALTY=0.08`.
- Build stale penalty only from `AvailabilityScore.freshness_label` and `AvailabilityScore.reasons`.
- Keep penalty values non-negative and deterministic.
- Do not apply a stale penalty to `fresh` or `aging`.
- Do not increase a candidate score through stale penalty logic.
- Do not change `fallback_only`; offline fallback inclusion is still controlled by availability and fallback selection rules.
- Endpoint responses do not need to expose the raw penalty number in MVP, but recommendation reasons must include the matching freshness reason when the penalty is non-zero.

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
| Lower station power | Use `charging_power_score`; add `low_power_penalty` below `0.5` and never reward power above the vehicle cap. |
| Stale availability | Use `availability_score` plus `stale_penalty`; stale `available` remains visible but lower confidence. |
| Unknown availability | Use `availability_score` plus `stale_penalty`; unknown status or freshness ranks below known non-offline states. |
| Confirmed `occupied` | Use `availability_score`; keep visible when route coverage is sparse. |
| Confirmed `offline` | Use `availability_score=0.0`; include only as fallback with clear reason. |
| Reliability input | Build from availability score output and normalized candidate status only; do not claim historical uptime in MVP. |
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

Fallback selection:

- Backend implementation entry point is `select_fallback_candidates(evaluations, max_results=5)`.
- `evaluations` are `(StopCandidate, ReachableSegmentEstimate, AvailabilityScore)` tuples produced by earlier optimizer helpers.
- A primary candidate is `reachability.reachable=true` and `availability.fallback_only=false`.
- If at least one primary candidate exists, fallback selection returns no fallback rows.
- If no primary candidate exists, candidates with `reachability.reachable=false` receive `unreachable_fallback`.
- If no primary candidate exists, candidates with `availability.fallback_only=true` receive `offline_fallback`.
- Fallback rows are capped by `max_results` and ordered deterministically by availability fallback severity, route distance, detour distance, then station id.

Known optimizer limitations:

- Final recommendation score is a deterministic local ranking signal, not a predicted travel time, queue wait, charging duration, price, or arrival ETA.
- Imported status snapshots can be stale or incomplete; `freshness_label` and `reasons` must be shown so UI and assistant summaries do not imply live charger state.
- Fallback rows exist only to avoid an empty result set when no primary candidate is usable. They are not safe stop instructions and must keep `unreachable_fallback` or `offline_fallback` visible.
- The current helper filters connector mismatches before ranking and does not support emergency connector-mismatch fallback.
- Duplicate station cluster handling remains a documented penalty input but is not implemented in the 4.4 helper yet.

## Serializable Route Planner Graph State

`backend/route_planner_graph.py` defines the 4.5 graph state contract and compiled LangGraph entrypoint. The state uses only JSON-safe payloads so graph runs, API responses, tests, and optional checkpointers do not need to serialize dataclasses, tuples, or datetime objects.

State keys:

- `request`: original route planner request payload.
- `route_id`, `route_distance_km`, `route_polyline`: validated route fields.
- `vehicle`: validated vehicle profile payload.
- `route_summary`: deterministic route energy and SoC summary.
- `constraints`: normalized planner constraints.
- `reference_time`: ISO 8601 datetime string with timezone, used for deterministic availability freshness scoring.
- `station_features`: local station data available to the graph.
- `candidate_features`: route-corridor-filtered station features.
- `stop_candidates`: optimizer candidate dictionaries.
- `optimizer_input`: serialized stop optimizer input.
- `optimizer_response`: serialized stop optimizer response.
- `response`: final endpoint-ready response payload.
- `errors`: node-scoped validation or processing errors.

Rules:

- Graph state stores lists, dictionaries, strings, numbers, booleans, and nulls only.
- Helper modules may use tuples and dataclasses internally, but graph nodes must convert them through `to_dict()` before writing state.
- `route_polyline` uses `list[list[float]]`, not coordinate tuples, to keep JSON round-trips stable.
- `errors` entries include the node name, message, and optional machine-readable code.

### `validate_route_request` node

`validate_route_request(state)` reads `state["request"]["route"]` and returns only JSON-safe state updates. It validates the route envelope before any vehicle, station, or optimizer work runs.

Successful update keys:

- `route_id`: stripped `route.id`, or `route-request` when the optional id is missing or blank.
- `route_distance_km`: positive finite route distance.
- `route_polyline`: validated `list[list[float]]` coordinates.
- `errors`: existing errors, unchanged.

Failure behavior:

- Missing request returns `missing_request`.
- Missing route object returns `missing_route`.
- Invalid route id, distance, polyline length, coordinate type, or coordinate bounds returns `invalid_route`.
- Errors are appended as `{node: "validate_route_request", message, code}` and no normalized route fields are written.

### `validate_vehicle_profile` node

`validate_vehicle_profile(state)` reads `state["request"]["vehicle"]` and delegates validation to `VehicleProfile`. It keeps vehicle schema rules in the helper module and stores only `VehicleProfile.to_dict()` output in graph state.

Successful update keys:

- `vehicle`: normalized vehicle payload with connector preferences as a JSON list.
- `errors`: existing errors, unchanged.

Failure behavior:

- Missing request returns `missing_request`.
- Missing vehicle object returns `missing_vehicle`.
- Missing required fields, invalid numeric values, invalid SoC bounds, empty connector preferences, or unsupported connector types return `invalid_vehicle`.
- Errors are appended as `{node: "validate_vehicle_profile", message, code}` and no normalized vehicle field is written.

### `build_route_corridor` node

`build_route_corridor(state)` reads normalized `state["route_polyline"]` from `validate_route_request` and the optional `request.constraints.corridor_width_km`. It builds the JSON-safe corridor payload used by later station-candidate filtering.

Successful update keys:

- `constraints`: normalized `corridor_width_km`, defaulting to `DEFAULT_CORRIDOR_WIDTH_KM` (`3.0`).
- `route_corridor`: `{polyline, corridor_width_km}` with coordinate lists, not tuples.
- `errors`: existing errors, unchanged.

Failure behavior:

- Missing `route_polyline` returns `invalid_corridor`.
- Non-object `request.constraints` returns `invalid_corridor`.
- Non-numeric, non-finite, or negative `constraints.corridor_width_km` returns `invalid_corridor`.
- Errors are appended as `{node: "build_route_corridor", message, code}` and no corridor payload is written.

### `find_station_candidates` node

`find_station_candidates(state)` reads `state["route_corridor"]` and `state["station_features"]`, then delegates geometry filtering to `filter_candidates_by_route_corridor`. It does not load station files or query a database; a previous layer must provide the local station Feature list.

Successful update keys:

- `candidate_features`: station Feature dictionaries inside the route corridor, with `properties.distance_from_route_km` added by the corridor helper.
- `errors`: existing errors, unchanged.

Failure behavior:

- Missing or invalid `route_corridor` returns `invalid_station_candidates`.
- Missing or non-list `station_features` returns `invalid_station_candidates`.
- Invalid GeoJSON station geometry or coordinates from the corridor helper returns `invalid_station_candidates`.
- Errors are appended as `{node: "find_station_candidates", message, code}` and no candidate feature payload is written.

### `estimate_soc` node

`estimate_soc(state)` reads `route_distance_km` and normalized `vehicle`, then delegates route-level energy and SoC math to `estimate_route_soc_summary` in `stop_optimizer.py`. The graph node does not duplicate numeric formulas.

Successful update keys:

- `route_summary`: `StopOptimizerSummary.to_dict()` output with `distance_km`, `estimated_energy_kwh`, `start_soc`, `target_arrival_soc`, `minimum_required_soc`, and `reachable_without_stop`.
- `errors`: existing errors, unchanged.

Failure behavior:

- Missing or invalid `route_distance_km` returns `invalid_soc_estimate`.
- Missing or invalid normalized `vehicle` returns `invalid_soc_estimate`.
- Errors are appended as `{node: "estimate_soc", message, code}` and no route summary payload is written.

### `rank_charging_stops` node

`rank_charging_stops(state)` reads normalized route fields, `vehicle`, `candidate_features`, and `reference_time`. It converts route-corridor-filtered station Features into `StopCandidate` rows, builds `StopOptimizerInput`, and delegates ranking to `build_stop_optimizer_response` in `stop_optimizer.py`.

The graph node does not duplicate scoring, availability freshness, stale penalty, fallback, or recommendation ordering logic.

Successful update keys:

- `stop_candidates`: normalized `StopCandidate.to_dict()` rows built from candidate Feature properties.
- `optimizer_input`: serialized `StopOptimizerInput.to_dict()` payload.
- `optimizer_response`: serialized `StopOptimizerResponse.to_dict()` payload, including `summary` and sorted `recommendations`.
- `errors`: existing errors, unchanged.

Candidate Feature mapping:

- `properties.station_id` is preferred; `properties.charger_id` is accepted for current local station fixtures.
- `properties.name` is preferred; `properties.charger_name` is accepted for current local station fixtures.
- `properties.connector_type`, `max_kw`, `distance_from_route_km`, and `route_distance_km` are required before optimizer ranking.
- `properties.status` defaults to `unknown` when omitted.
- `properties.status_updated_at` is optional; missing values flow to optimizer freshness `unknown`.

Failure behavior:

- Missing or invalid `route_id`, `route_distance_km`, `vehicle`, `candidate_features`, `reference_time`, or `constraints.max_results` returns `invalid_stop_ranking`.
- Empty candidate lists return `invalid_stop_ranking`; empty local data should not silently produce an authoritative-looking route plan.
- Candidate Feature rows missing required optimizer fields return `invalid_stop_ranking`.
- Errors are appended as `{node: "rank_charging_stops", message, code}` and no optimizer payload is written.

### `build_response` node

`build_response(state)` reads serialized `optimizer_response` and wraps it as the endpoint-ready route planner `response`. It does not re-rank recommendations, recompute summary values, or mutate optimizer scoring output.

Successful update keys:

- `response`: optimizer `route_id`, `summary`, and `recommendations`, plus response `meta`.
- `errors`: existing errors, unchanged.

Response metadata:

- `meta.source` comes from candidate or station Feature `properties.source` when present, otherwise defaults to `local-dataset`.
- `meta.snapshot_date` is copied from candidate or station Feature `properties.snapshot_date` when present.
- `meta.freshness_label` is inferred only from optimizer recommendation reasons such as `fresh_availability`, `aging_availability`, `stale_availability_penalty`, or `unknown_availability_penalty`.
- `meta.limitations` always includes the MVP route, traffic, weather, imported availability, and fallback limitations documented in the response schema.

Failure behavior:

- Missing or malformed `optimizer_response` returns `invalid_response`.
- Invalid `optimizer_response.route_id`, `summary`, or `recommendations` returns `invalid_response`.
- Errors are appended as `{node: "build_response", message, code}` and no final response payload is written.

### Graph helper boundary audit

As of 4.5.12, route planner graph nodes remain orchestration-only:

- `estimate_soc` delegates route energy and SoC formulas to `estimate_route_soc_summary`.
- `rank_charging_stops` delegates scoring, availability freshness, reliability weighting, stale penalty, fallback selection, and recommendation ordering to `build_stop_optimizer_response`.
- `build_response` wraps serialized optimizer output and metadata only; it does not recompute summary values or score recommendations.
- Graph validation helpers may still normalize payload fields and reject invalid numbers, but they must not own route energy formulas, score weights, penalty formulas, fallback score caps, or recommendation sort keys.

Regression tests inspect graph node source to keep optimizer scoring helpers out of `route_planner_graph.py`.

As of 4.5.13, route planner graph output is also compared against direct helper composition with the same deterministic route, vehicle, candidate, metadata, and `reference_time` fixture. The regression executes the graph nodes through `build_response`, then independently composes `filter_candidates_by_route_corridor`, `estimate_route_soc_summary`, and `build_stop_optimizer_response`; the final response payload, optimizer payload, route summary, and candidate list must match exactly.

### LangGraph compiled graph

As of 4.5.14, `backend/route_planner_graph.py` exposes `build_route_planner_graph()`. It builds a LangGraph `StateGraph` with the existing deterministic node order:

```text
START
validate_route_request
validate_vehicle_profile
build_route_corridor
find_station_candidates
estimate_soc
rank_charging_stops
build_response
END
```

`backend/requirements.txt` pins `langgraph==1.2.1`. The dependency is now justified because the module contains real orchestration nodes and 4.5.13 proved graph output matches direct helper composition. The compiled graph must not introduce new scoring, SoC math, routing, weather, traffic, or metadata logic; it only wires the existing node functions.

Regression tests invoke the compiled graph and a manual node sequence with the same JSON-safe state fixture, then require identical final state and response payloads.

### Route planner API endpoint

As of 4.5.15, `backend/app/api/routes.py` exposes `POST /api/routes/charging-plan`. The endpoint loads the local station fixture, chooses a deterministic `reference_time`, invokes `build_route_planner_graph()`, and returns only the final graph `response` payload.

Endpoint behavior:

- Caller-provided `reference_time` is passed to the graph for deterministic freshness scoring.
- If `reference_time` is omitted, the endpoint derives it from the latest local station `status_updated_at` timestamp.
- Route-corridor filtering fills missing candidate `route_distance_km` from local polyline progress so raw station fixtures can be ranked.
- Graph validation errors return HTTP 400 with node-scoped error payloads.
- Fixture load or malformed local station data errors return HTTP 500.

The endpoint remains inside MVP boundaries: it does not call external route APIs, infer route alternatives, fetch live traffic/weather, or perform live charger polling.

### Route planner response schema

As of 4.5.16, `backend/app/schemas/route_planner.py` defines the FastAPI response model for `POST /api/routes/charging-plan`. The endpoint still accepts a raw dictionary request so graph nodes own request validation and keep node-scoped HTTP 400 errors. The response is schema-checked before serialization and appears in OpenAPI as `RouteChargingPlanResponse`.

Schema coverage:

- `RoutePlannerSummary` covers route distance, energy estimate, SoC fields, and `reachable_without_stop`.
- `RoutePlannerRecommendation` covers station identity, connector, power, route/detour distance, arrival SoC, score, and reasons.
- `RoutePlannerResponseMeta` covers local source, optional snapshot/freshness labels, and MVP limitations.

### Route planner request schema

As of 4.5.17, `RouteChargingPlanRequest` documents the FastAPI request body for `POST /api/routes/charging-plan` and appears in OpenAPI. It is intentionally pass-through: `route`, `vehicle`, `constraints`, and `reference_time` are accepted without Pydantic numeric or nested type validation so graph nodes continue to own request normalization and node-scoped HTTP 400 errors.

This keeps the endpoint contract discoverable while preserving the graph validation surface:

- malformed or missing `route` still returns `validate_route_request` errors,
- malformed or missing `vehicle` still returns `validate_vehicle_profile` errors,
- malformed constraints still return node-specific graph errors,
- later strict request models can be added only if they preserve these error semantics.

### Frontend route planner client

As of 5.1.1, `frontend/src/lib/routePlanner.ts` defines the frontend route planner request and response contract for `POST /api/routes/charging-plan`. It mirrors the backend JSON shape, builds relative or `VITE_API_BASE_URL`-based endpoint URLs, and posts the typed request with JSON headers.

The first frontend route planner surface is client-only and feature-flagged with `VITE_ENABLE_ROUTE_PLANNER=false` by default. No map route drawing, route editing UI, external routing provider, traffic, weather, pricing, reservation, or live charger polling behavior is added in 5.1.1.

The client preserves `meta.limitations` from the backend response for later UI display. Failed backend responses throw `Route planner failed: <status>` so future panels can show typed local failure states without inventing route facts.

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

LangGraph dependency decision:

- 4.5.3 kept `langgraph` out of `backend/requirements.txt` while the helper chain did not yet need a graph runtime.
- As of 4.5.14, `langgraph==1.2.1` is pinned because `backend/route_planner_graph.py` now contains real orchestration nodes for request validation, corridor building, candidate lookup, SoC estimation, stop ranking, and response assembly.
- The compiled graph remains a wiring layer over existing nodes. It must not duplicate helper math, helper scoring, external routing, weather, traffic, or metadata assembly.
- Graph tests prove the compiled graph output matches both the manual node sequence and the direct helper-composed output.
- As of 4.5.15, the FastAPI route planner endpoint invokes the compiled graph with local station data.
- As of 4.5.16, the route planner endpoint uses a FastAPI response model while graph nodes remain responsible for request validation.
- As of 4.5.17, the endpoint uses a pass-through request model for OpenAPI discoverability without preempting graph validation.
- As of 5.1.1, the frontend has a typed route planner client behind `VITE_ENABLE_ROUTE_PLANNER=false`; it only calls the local backend route planner endpoint.

Implemented backend pieces:

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
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Imported availability score|Reliability score input|Stale penalty|availability_score|freshness_label|stale_penalty|historical uptime"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Charger Penalty Rules|Hard filters|candidate_reachable=false|stale_availability_penalty|offline_fallback|fallback"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Known optimizer limitations|deterministic local ranking signal|not live charger state|not safe stop instructions|Duplicate station cluster"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "External Route API Dependency Review|No route-provider SDK|route.polyline|route.distance_km|Disallowed MVP behavior|credential handling"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "LangGraph dependency decision|langgraph==1.2.1|real orchestration nodes|helper-composed output"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "LangGraph compiled graph|build_route_planner_graph|StateGraph|START|END|manual node sequence"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Route planner API endpoint|POST /api/routes/charging-plan|reference_time|status_updated_at|HTTP 400|HTTP 500"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Route planner response schema|RouteChargingPlanResponse|RoutePlannerRecommendation|OpenAPI|request validation"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Route planner request schema|RouteChargingPlanRequest|pass-through|validate_route_request|validate_vehicle_profile"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Frontend route planner client|VITE_ENABLE_ROUTE_PLANNER|fetchChargingPlan|meta.limitations|Route planner failed"
Select-String -Path D:\fleet\chargeflow-kr\backend\requirements.txt -Pattern "langgraph==1.2.1"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Serializable Route Planner Graph State|JSON-safe payloads|route_polyline|optimizer_response|errors"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "validate_route_request|missing_request|missing_route|invalid_route|route-request"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "validate_vehicle_profile|VehicleProfile.to_dict|missing_vehicle|invalid_vehicle|connector preferences"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "build_route_corridor|DEFAULT_CORRIDOR_WIDTH_KM|route_corridor|corridor_width_km|invalid_corridor"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "find_station_candidates|filter_candidates_by_route_corridor|station_features|candidate_features|invalid_station_candidates"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "estimate_soc|estimate_route_soc_summary|route_summary|minimum_required_soc|invalid_soc_estimate"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "rank_charging_stops|StopOptimizerInput|build_stop_optimizer_response|reference_time|invalid_stop_ranking"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "build_response|optimizer_response|meta.limitations|freshness_label|invalid_response"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "Graph helper boundary audit|orchestration-only|estimate_route_soc_summary|build_stop_optimizer_response|score weights"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6d-route-planner.md -Pattern "4.5.13|direct helper composition|filter_candidates_by_route_corridor|final response payload|candidate list"
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
- Imported availability, reliability input, and stale penalty sections define snapshot-based scoring inputs without live or historical uptime claims.
- Charger penalty rules define hard filters, penalty inputs, reason allowlist, and fallback labeling.
- Known optimizer limitations say ranking is not ETA/live state/safe stop instruction, and mark duplicate cluster handling as deferred.
- External route API dependency review confirms route providers are not required and remain deferred.
- LangGraph dependency decision adds `langgraph==1.2.1` only after real orchestration nodes and helper-equivalence tests exist.
- Serializable route planner graph state uses JSON-safe payloads and keeps helper dataclasses out of persisted graph state.
- `validate_route_request` documents normalized route fields and route validation error codes.
- `validate_vehicle_profile` documents helper-owned vehicle validation and vehicle validation error codes.
- `build_route_corridor` documents default corridor width, route corridor payload, and corridor validation error codes.
- `find_station_candidates` documents corridor-filtered station feature output and station candidate error codes.
- `estimate_soc` documents helper-owned SoC math, route summary output, and SoC estimate error codes.
- `rank_charging_stops` documents helper-owned ranking, optimizer payload outputs, deterministic `reference_time`, and stop ranking error codes.
- `build_response` documents endpoint-ready response assembly, metadata limitations, and final response error codes.
- Graph helper boundary audit confirms numeric math and scoring remain in helper modules, not graph nodes.
- Graph output matches direct helper-composed output for the deterministic route/candidate fixture.
- Compiled LangGraph output matches the manual node sequence for the deterministic route/candidate fixture.
- Route planner API endpoint invokes the compiled graph, returns final response payloads, derives deterministic reference time when omitted, and maps graph errors to HTTP 400.
- Route planner response schema is enforced by FastAPI and appears in OpenAPI without taking request validation away from graph nodes.
- Route planner request schema appears in OpenAPI without taking request validation away from graph nodes.
- Frontend route planner client builds `/api/routes/charging-plan`, posts the typed request, keeps the feature flag off by default, and preserves backend limitations for later UI display.
- Later strict request schema and optimizer work remains explicitly deferred.
