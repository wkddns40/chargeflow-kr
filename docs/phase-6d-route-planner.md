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
```

Pass conditions:

- Document exists.
- MVP scope defines charger-stop recommendation, not full navigation.
- ABRP-inspired route planning UI assumptions are documented without copying ABRP assets.
- External route APIs are deferred.
- Weather and traffic exclusions are explicit and forbid live traffic, forecasts, live ETA, and weather-adjusted consumption.
- Vehicle profile schema documents fields, units, and validation notes for later implementation.
- Later schema and optimizer work remains explicitly deferred.
