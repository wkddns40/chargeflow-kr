# Phase 6C LLM Spatial Search Design

Phase 6C adds a typed natural-language search path for Korean EV charger queries. The LLM does not query the database directly and does not answer from memory. It converts user text into a typed command that the backend validates before using local datasets.

The original task 3.1 phase was design-only. The current implementation keeps the same no-cost boundary: no external LLM provider, no API key, and no SQL generated from user text.

## Implementation Status

As of 2026-05-27:

- `POST /api/search/chargers/nl` accepts `{ "message": "..." }` free-text search input.
- The backend uses a deterministic parser, then passes the parsed command through `validate_search_command()`.
- Search execution reuses the existing local geocoder, PostGIS-backed station query, radius filter, status/power/connector filters, and sort path.
- Missing place input returns `type="clarification_required"` without applying map results.
- Unsupported intents and SQL-like control text return stable 400 errors.
- The frontend assistant is chat-first and keeps structured search controls as a fallback.
- No external LLM provider call is made.

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
- Route planning.
- Weather, traffic, pricing, and reservation integrations.

## Frontend Shell Status

The first frontend shell is feature-flagged with `VITE_ENABLE_LLM_SEARCH=false` by default.

When enabled, the panel submits a typed charger search command to the local backend endpoint. It does not call a real LLM provider, does not send prompts to an external service, and does not infer facts outside the backend response.

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

## LLM Search Cost Protection

As of 5.2.4, the LLM search path has a no-cost baseline: the enabled frontend shell posts a typed search command to the local backend only. It does not send prompts to an external provider, does not hold a provider API key, and does not perform provider-backed summarization.

If a future task adds an LLM provider for natural-language-to-command parsing, cost protection must gate the provider boundary before any paid request is made:

- Keep `VITE_ENABLE_LLM_SEARCH=false` by default in production until backend-side quotas exist.
- Keep provider credentials server-side only; no provider key or model name belongs in frontend code.
- Allow at most one provider call per explicit user submit. No keystroke, autocomplete, map pan, retry loop, or background refresh may call the provider.
- Enforce prompt length and request body size limits before provider dispatch.
- Reject unsupported intents such as `plan_route`, `compare_prices`, `reserve_charger`, and `predict_wait_time` locally without provider retries.
- Apply unauthenticated IP quotas first, and later authenticated user quotas when user identity exists.
- Add a daily spend cap and circuit breaker that can disable provider calls without disabling local typed search.
- Use a short timeout and no automatic provider retry unless a later task assigns a retry budget.
- Cache only normalized typed commands or privacy-safe hashes unless raw prompt retention is explicitly approved.
- Log metering fields such as endpoint, model, token estimate, cost estimate, outcome, and rate-limit bucket; do not log raw prompt text by default.

The local `/api/search/chargers` endpoint remains the authoritative charger-data path. Rate limiting may protect it for availability, but provider cost controls must focus on the future prompt parsing boundary, not on local station filtering.

## Throttled Request Response

As of 5.2.5, throttled LLM search requests must return a stable HTTP 429 contract. The contract applies to future local endpoint rate limits and future provider cost-protection limits.

Required response:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json
```

```json
{
  "detail": {
    "code": "rate_limited",
    "message": "Search is temporarily rate limited. Try again later.",
    "retry_after_seconds": 60,
    "scope": "ip"
  }
}
```

Rules:

- Use HTTP 429 for throttled requests, not 400 or 500.
- Include `Retry-After` when a retry time is known.
- Keep `detail.code` stable as `rate_limited` so frontend code can branch without parsing English text.
- Set `detail.scope` to `ip`, `user`, `provider_cost`, or `global_circuit_breaker`.
- Do not include raw prompt text, provider error payloads, API keys, token details, or internal bucket identifiers in the response.
- If a daily spend cap or circuit breaker is active, use `scope="provider_cost"` or `scope="global_circuit_breaker"` and keep the message generic.
- Frontend surfaces the message as a temporary throttle state and must not retry automatically unless a later task defines an explicit retry budget.

## Rate Limit Scope Audit

As of 5.2.6, rate limit work remains design-only. This document defines protected LLM search boundaries, future cost controls, and throttled response shape, but it does not implement runtime throttling.

Implementation intentionally not added in 5.2:

- No FastAPI middleware or dependency for rate limiting.
- No in-memory, Redis, database, or file-backed token bucket.
- No auth session, user identity model, API key model, or account quota table.
- No external LLM provider client, provider API key, model selection, or prompt dispatch.
- No frontend retry loop, polling loop, debounce-triggered provider call, or provider-cost UI.
- No changes to the local `/api/search/chargers` command schema or station filtering behavior.

The next implementation task must choose storage, deployment topology, reset windows, clock source, bypass policy for local development, and test strategy before adding runtime throttling.

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

## Free-Text Chat Implementation Plan

The next Phase 6C implementation step should add free-text input without replacing the current typed search path. The existing `POST /api/search/chargers` endpoint remains the authoritative search tool. A new natural-language endpoint converts raw user text into the same typed command shape, then calls the existing validator and PostGIS-backed search path.

Recommended endpoint:

```http
POST /api/search/chargers/nl
Content-Type: application/json
```

```json
{
  "message": "Gangnam Station nearby 2km 100kW fast chargers"
}
```

Backend flow:

```text
raw user text
  -> deterministic parser
  -> typed command object
  -> validate_search_command()
  -> lookup_place()
  -> PostGIS bbox query
  -> radius/filter/sort
  -> structured search response
```

### Chat UI

- Extend `SearchAssistantPanel` from form-first to chat-first.
- Add a single free-text input and submit button.
- Preserve the current advanced controls as an optional fallback for explicit typed filters.
- Display assistant messages, clarification prompts, backend limitations, and the result list.
- Apply returned `features` to the map exactly as the current typed search does.

Example supported input:

```text
Gangnam Station nearby 2km 100kW fast chargers
```

Expected behavior:

- The UI posts the raw message to `/api/search/chargers/nl`.
- The backend returns parsed command metadata and search results.
- The frontend shows the backend result list and updates map features.

### Deterministic Parser Baseline

The first implementation should not call an external LLM provider. It should use deterministic parsing with explicit aliases and regular expressions. This keeps the no-cost baseline intact and makes failures testable.

Parser responsibilities:

- Detect `find_chargers` intent from charger-search phrases.
- Extract a known place alias, such as `Gangnam Station`, `Seoul Station`, or `Jeju Airport`.
- Extract radius values such as `2km`, `2000m`, or default nearby wording.
- Extract `min_kw` from phrases such as `100kW+`, `100kW or higher`, or `100kW 이상`.
- Map fast-charger wording to `connector_type="DC"` and slow-charger wording to `connector_type="AC"`.
- Map status wording to `available`, `occupied`, `offline`, or `unknown` only when an explicit alias exists.
- Map sort wording to `distance`, `power`, or `availability`.

Parser non-responsibilities:

- Do not infer user location from browser, IP address, or model memory.
- Do not call external geocoding APIs.
- Do not produce SQL, column names, table names, or query fragments.
- Do not retry with an LLM provider when deterministic parsing fails.

### Clarification Contract

If parsing fails because required fields are missing, the endpoint should return a stable clarification response instead of guessing.

Example:

```json
{
  "type": "clarification_required",
  "message": "Search needs a place. Try: Gangnam Station nearby chargers.",
  "missing_fields": ["place"]
}
```

Rules:

- Missing `place` should ask for clarification.
- Missing radius may default to `2000` meters only if product requirements confirm that default.
- Unsupported intents such as reservation, price comparison, or wait-time prediction should return a typed unsupported-intent error.
- Suspicious control text must be rejected before command validation.

### Optional LLM Provider Phase

An external provider should be a later, separate task. If added, it must stay behind the backend boundary and preserve the same typed command contract.

Provider rules:

- No provider API key or model name in frontend code.
- At most one provider call per explicit user submit.
- Enforce input length and request body limits before provider dispatch.
- Return JSON only and discard any output that fails `validate_search_command()`.
- Keep daily cost caps, circuit breaker, and timeout controls server-side.
- Do not log raw user text by default.
- Never interpolate provider output into SQL.

### Tests For Free-Text Search

Backend parser tests:

- `Gangnam Station nearby 2km fast chargers` -> `find_chargers`, `Gangnam Station`, `radius_m=2000`, `connector_type=DC`.
- `Jeju Airport 100kW or higher` -> `find_chargers`, `Jeju Airport`, `min_kw=100`.
- `Seoul Station available chargers nearby` -> `status=available`.
- `reserve a charger near Gangnam Station` -> unsupported intent.
- `Gangnam Station drop table stations` -> rejected control text.

Backend endpoint tests:

- Natural-language request returns parsed command metadata and features.
- Unknown place returns clarification or a stable 400 response.
- Parsed command always passes through `validate_search_command()`.
- Search results use the existing PostGIS repository path.

Frontend tests:

- Chat input renders when `VITE_ENABLE_LLM_SEARCH=true`.
- Submit posts to `/api/search/chargers/nl`.
- Clarification response is displayed without applying map results.
- Successful response applies returned features to the map.

Completion criteria:

- A user can type a free-text charger query into the assistant panel.
- The backend converts it into a typed command without external provider cost.
- Existing validation, local geocoder, and PostGIS-backed search are reused.
- Live demo handles a Gangnam Station free-text search and keeps backend limitations visible.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "intent|tool boundary|validation|SQL|hallucination|local dataset"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "LLM Search Cost Protection|no-cost baseline|provider call|VITE_ENABLE_LLM_SEARCH=false|daily spend cap|server-side"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "Throttled Request Response|429 Too Many Requests|Retry-After|rate_limited|provider_cost|global_circuit_breaker"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6c-llm-search.md -Pattern "Rate Limit Scope Audit|design-only|No FastAPI middleware|No external LLM provider client|No changes to the local"
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
- Document defines LLM search cost protection before any future paid provider call.
- Document defines the throttled request response contract for HTTP 429 responses.
- Document confirms 5.2 remains design-only and does not add runtime throttling or provider calls.
