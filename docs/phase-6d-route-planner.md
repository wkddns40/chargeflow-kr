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
```

Pass conditions:

- Document exists.
- MVP scope defines charger-stop recommendation, not full navigation.
- External route APIs are deferred.
- Weather and traffic are outside MVP scope.
- Later schema and optimizer work remains explicitly deferred.
