# Phase 6C LLM Spatial Search Design

Phase 6C adds a typed natural-language search path for Korean EV charger queries. The LLM does not query the database directly and does not answer from memory. It converts user text into a typed command that the backend validates before using local datasets.

This phase is design-only for task 3.1. It does not add an LLM provider, API key, SQL execution layer, or frontend assistant panel.

## Scope

Included:

- LLM responsibilities and non-responsibilities.
- Typed command flow from user input to backend validation.
- Intent schema for charger search.
- Tool boundary and SQL safety rules.
- Validation rules.
- Korean query examples.
- Hallucination prevention rules.
- Local dataset limitation notes.

Deferred:

- Provider selection and model prompts.
- External LLM API credentials.
- Backend `POST /api/search/chargers` implementation.
- Frontend assistant panel.
- Route planning.
- Weather, traffic, pricing, and reservation integrations.

## Responsibilities

The LLM may:

- Classify the user request into a supported intent.
- Extract place names, radius, charger filters, and sort preference.
- Produce a typed command object that matches the backend schema.
- Ask for clarification when required fields are missing or ambiguous.
- Explain which local filters were applied after the backend returns data.

The LLM must not:

- Write SQL or partial SQL.
- Choose database table names, column names, joins, or indexes.
- Invent charger availability, distance, power, connector type, pricing, or operating status.
- Call external map, geocoding, traffic, weather, or payment APIs.
- Bypass backend validation.
- Return final charger facts before the backend tool result is available.

## Command Flow

```mermaid
flowchart LR
    user[User Korean query] --> llm[LLM intent parser]
    llm --> command[Typed command JSON]
    command --> validator[Backend schema validation]
    validator --> geocode[Local place lookup]
    geocode --> spatial[Local spatial filter]
    spatial --> station_api[Station and status datasets]
    station_api --> response[Structured search response]
    response --> llm_summary[LLM wording over backend result]
    llm_summary --> ui[Frontend result list and map state]
```

Rules:

- The LLM output is only accepted as data.
- Backend validation is authoritative.
- Local place lookup is authoritative for coordinates.
- Local station and status datasets are authoritative for charger facts.
- The frontend displays backend result objects, not unsupported LLM claims.

## Intent Schema

Initial supported intent:

```json
{
  "intent": "find_chargers",
  "place": "강남역",
  "radius_m": 2000,
  "filters": {
    "min_kw": 100,
    "status": "available",
    "connector_type": "DC"
  },
  "sort": "distance"
}
```

Fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `intent` | string enum | yes | Initial value: `find_chargers`. Unknown intents are rejected. |
| `place` | string | yes | Korean place name resolved through a local fixture or local geocoder abstraction. |
| `radius_m` | integer | yes | Search radius in meters. Backend enforces min and max bounds. |
| `filters.min_kw` | integer | no | Minimum charger output in kW. |
| `filters.status` | string enum | no | `available`, `occupied`, `offline`, or `unknown`. |
| `filters.connector_type` | string enum | no | Connector values supported by local station data. |
| `sort` | string enum | no | `distance`, `power`, or `availability`. Defaults to `distance`. |

Unsupported or future intents:

- `plan_route`
- `compare_prices`
- `reserve_charger`
- `predict_wait_time`
- `report_fault`

These intents should return a typed unsupported-intent error until their backend contracts exist.

## Validation Rules

Backend validation rejects:

- Missing `intent`, `place`, or `radius_m`.
- Unknown intent values.
- Non-integer or non-positive radius.
- Radius above the configured local-search maximum.
- Unsupported status values.
- Unsupported connector types.
- Unsupported sort values.
- Extra fields that look like SQL, raw table names, prompt instructions, API keys, or executable code.

Backend validation normalizes:

- Status aliases only when explicitly mapped, for example `사용가능` to `available`.
- Connector aliases only when explicitly mapped to local connector values.
- Whitespace around place names and enum values.

Backend validation does not infer:

- User location from IP address.
- Current charger availability from stale or missing snapshots.
- Coordinates from external services.
- Reservation or pricing data.

## Tool Boundary

The LLM may call one backend search tool shape:

```json
{
  "tool": "search_chargers",
  "arguments": {
    "intent": "find_chargers",
    "place": "강남역",
    "radius_m": 2000,
    "filters": {
      "status": "available"
    },
    "sort": "distance"
  }
}
```

Backend-owned steps:

1. Validate the typed command.
2. Resolve `place` to coordinates using a local source.
3. Convert radius and coordinates into a bbox or spatial query.
4. Query local station, connector, and imported status data.
5. Apply filters and sorting.
6. Return structured results with provenance and limitation notes.

LLM-owned steps after tool result:

1. Summarize the backend result.
2. Preserve backend counts, names, distances, status, and freshness labels exactly.
3. State when no local result exists.
4. State when data is stale or unavailable.

## SQL Safety

- LLM output must never be interpolated into SQL.
- The backend maps validated enum fields to predefined query branches.
- Place names and user text are parameters only.
- Radius and numeric filters are parsed as typed numbers before query construction.
- Sort values map to a small allowlist.
- Raw SQL fragments, operators, table names, and column names in LLM output are rejected.
- Search responses should expose query metadata, not SQL text.

## Korean Query Examples

Example 1:

User text:

```text
강남역 근처 2km 안에 사용 가능한 급속 충전소 찾아줘
```

Typed command:

```json
{
  "intent": "find_chargers",
  "place": "강남역",
  "radius_m": 2000,
  "filters": {
    "status": "available",
    "connector_type": "DC"
  },
  "sort": "distance"
}
```

Example 2:

User text:

```text
제주공항 주변에서 100kW 이상 충전기만 보여줘
```

Typed command:

```json
{
  "intent": "find_chargers",
  "place": "제주공항",
  "radius_m": 3000,
  "filters": {
    "min_kw": 100
  },
  "sort": "power"
}
```

Example 3:

User text:

```text
부산역 근처 충전소 중 지금 상태를 알 수 없는 곳도 포함해서 찾아줘
```

Typed command:

```json
{
  "intent": "find_chargers",
  "place": "부산역",
  "radius_m": 3000,
  "filters": {
    "status": "unknown"
  },
  "sort": "distance"
}
```

Clarification example:

User text:

```text
근처 충전소 찾아줘
```

Expected response:

```text
검색 기준 위치가 필요합니다. 예: "강남역 근처 충전소 찾아줘"
```

## Hallucination Prevention

The assistant must:

- Say when local data has no matching charger.
- Say when availability is based on imported snapshot data, not real-time polling.
- Cite the backend-provided `snapshot_date`, `observed_at`, or freshness label when available.
- Preserve backend result order unless the user asks for a different supported sort.
- Use only backend-provided station names, connector types, power values, status values, and distances.

The assistant must not:

- Invent charger names or addresses.
- Promise that a charger is free unless backend status is `available` and not stale.
- Claim live occupancy, pricing, payment support, parking rules, or reservation support.
- Fill missing coordinates from model memory.
- Recommend external navigation routes as if route planning exists.

## Local Dataset Limitations

Phase 6C initially searches local datasets only:

- Station locations come from the local station dataset.
- Connector metadata comes from local connector records or committed fixtures.
- Availability comes from imported file snapshots and rollups.
- Freshness follows `docs/phase-6b-file-status.md`.
- 7,000-station scale remains the first target.

Known limitations:

- No live OpenAPI polling.
- No external geocoding API.
- No traffic, weather, price, reservation, or wait-time feed.
- Some place names may be unknown until the local place fixture is expanded.
- Availability can be stale when the latest snapshot is older than the Phase 6B threshold.

## Response Contract

Backend search response should include:

```json
{
  "query": {
    "place": "강남역",
    "radius_m": 2000,
    "filters": {
      "status": "available",
      "connector_type": "DC"
    },
    "sort": "distance"
  },
  "features": [],
  "meta": {
    "count": 0,
    "source": "local-dataset",
    "snapshot_date": "2026-05-19",
    "freshness_label": "fresh",
    "limitations": [
      "Availability is imported snapshot data, not live polling."
    ]
  }
}
```

The LLM may paraphrase `meta.limitations`, but must not remove them.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "intent|tool boundary|validation|SQL|hallucination|local dataset"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "강남역|제주공항|부산역"
```

Pass conditions:

- Document exists.
- Document includes an intent schema.
- Document defines tool boundary and SQL safety rules.
- Document includes validation rules.
- Document includes Korean query examples.
- Document includes hallucination prevention rules.
- Document notes local dataset limitations and keeps external APIs deferred.
