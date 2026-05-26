# Production Observability Checklist

This document captures the Phase 6E production observability checklist. Metric names and Phase 6B file-status alignment remain defined in `docs/monitoring-metrics.md`.

The checklist is design-only. It does not add SDKs, exporters, alert rules, dashboards, CI gates, ticket automation, on-call routing, or runtime instrumentation.

## Scope

Included:

- Frontend error tracking requirements.
- Backend error tracking requirements.
- File import failure checks.
- Stale data checks.
- API latency checks.
- Queue depth placeholder for future queue use.
- Deploy readiness checks.
- Incident triage checks.
- Ownership and follow-up fields.
- Phase 6B monitoring alignment review.

Deferred:

- Error tracking SDK wiring and source-map upload.
- OpenTelemetry exporter, middleware, and correlation ID implementation.
- Prometheus scrape endpoint, alert rules, and Grafana dashboard JSON.
- Queue worker, broker, exporter, and queue alert implementation.
- Deploy gate, rollback, ticket, on-call, status-page, and owner registry automation.

## Frontend Error Tracking

Required future coverage:

- Capture top-level React render crashes through an error boundary.
- Capture unhandled promise rejections from data loading, map initialization, search, and route planner flows.
- Attach release, environment, route/view name, browser family, app version, frontend build hash, and low-cardinality feature flags.
- Preserve production stack trace debugging through controlled source-map handling.
- Sample repeated noisy errors and suppress known non-actionable browser extension failures.
- Fail open when no DSN is configured or the provider is unavailable.

Privacy rules:

- Do not record raw search text, route polylines, precise user location, IP address, auth tokens, API keys, cookies, query strings, request bodies, or full backend responses.
- Keep station IDs, route templates, status codes, and low-cardinality feature flags as allowed debugging context.

## Backend Error Tracking

Required future coverage:

- Capture unhandled FastAPI exceptions, unexpected `500` responses, startup failures, station fixture load failures, import pipeline failures, and route planner graph failures.
- Attach route template, method, status code, exception class, release, environment, service name, and request or correlation ID.
- Keep expected `400` validation errors out of paging by default while allowing sampled schema-drift visibility.
- Separate data/import failures from application bugs.
- Fail open when the provider or exporter is unavailable.

Privacy rules:

- Do not record raw request bodies, search text, route polylines, API keys, cookies, authorization headers, client IPs, full station fixture rows, or stack traces in API responses.
- Keep route templates, status codes, stable error codes, and sanitized fixture names as allowed context.

## File Import Failure Checks

Required future checks:

- Alert when `evstation_file_import_failure_total` increases during the active import window.
- Alert when no `evstation_file_import_success_total` exists for a required source within the expected freshness window.
- Alert when latest imported metadata lacks `raw_file_hash`, `snapshot_date`, `downloaded_at`, or source identity.
- Alert when rejected-row ratio exceeds the configured threshold.
- Treat partial station, connector, status event, or availability rollup writes as failed imports.
- Keep optional and required sources separate.

Allowed context:

- `source`, `snapshot_date`, `stage`, `reason`, committed row counts, rejected row count, quarantine count, and raw file hash prefix.

## Stale Data Checks

Required future checks:

- Alert when `evstation_station_freshness_seconds` for a required source and region exceeds the stale threshold or reports `freshness_label="stale"` across consecutive windows.
- Alert when `freshness_label="unknown"` persists because no usable `observed_at`, `snapshot_date`, or `downloaded_at` exists.
- Alert when `evstation_region_available_ratio` has `stale_count` above the configured stale-share threshold.
- Alert when all regions for a required source are stale or the latest `snapshot_date` is older than the expected import cadence.
- Treat stale data as a data confidence issue, not charger offline evidence.

Allowed context:

- `source`, `region_code`, `freshness_label`, `snapshot_date`, freshness age seconds, `stale_count`, denominator count, threshold, and import cadence.

## API Latency Checks

Required future checks:

- Alert when p95 or p99 `evstation_api_latency_seconds` for a required route and method exceeds configured thresholds across consecutive windows.
- Track `GET /api/stations`, `POST /api/search/chargers`, and `POST /api/routes/charging-plan` as route templates.
- Keep success, client-error, and server-error latency separate through `status_code`.
- Alert when a required route has no samples during an expected traffic window.
- Treat route planner latency separately from station search latency.

Allowed context:

- `route`, `method`, `status_code`, percentile, threshold, evaluation window, sample count, release, and environment.

## Queue Depth Placeholder

Queue depth is reserved for future production queues only. The current app has no production worker queue, message broker, background job table, queue exporter, or queue alert rule.

Candidate future metric:

- `evstation_queue_depth` as a gauge after a real queue boundary exists.
- Labels: `queue_name`, `state`, `source`, `release`, and `environment`.
- Bounded states: `pending`, `running`, `retry`, and `dead_letter`.
- Oldest job age should be a separate metric.

Queue depth must not imply charger availability, station demand, user wait time, or route ETA.

## Deploy Readiness

Future go/no-go checks:

- Frontend and backend error tracking have provider, release, environment, sampling, and privacy decisions.
- File import, stale data, API latency, and queue checks have owners, thresholds, windows, dashboards, and runbooks.
- Alert routing separates frontend crashes, backend `500` spikes, stale data, import failures, latency breaches, and queue backpressure.
- Privacy review covers prompts, route polylines, precise location, query strings, request bodies, cookies, authorization headers, and raw source files.
- Missing observability credentials fail open.

Post-deploy checks:

- New release appears in frontend and backend error tracking.
- API latency samples exist for required routes.
- File import success, failure, freshness, and regional availability metrics still use low-cardinality labels.
- Alerts do not include raw user input, credentials, raw files, stack traces, or full backend responses.

Rollback triggers:

- Sustained frontend render crashes, backend `500` responses, broken station search, broken route planning, unavailable required data, or observability that blocks the product path.

## Incident Triage

Initial classification:

- Classify the primary signal as frontend crash, backend `500` spike, file import failure, stale data, API latency breach, queue backpressure, or missing observability data.
- Classify impact as user-visible outage, degraded route planning, degraded charger search, data confidence issue, deploy health regression, or optional feature degradation.
- Separate optional dataset or placeholder metric gaps from required production path failures.

Minimum context:

- `release`, `environment`, alert name, evaluation window, first-seen time, affected feature, deploy status, and rollback decision.
- API incidents include route, method, status code, p95 or p99 latency, sample count, and correlation ID when available.
- Import and stale data incidents include source, region, snapshot date, freshness label, raw file hash prefix, stale count, and last successful import time.

Closure:

- Record impact, timeline, root cause, mitigation, rollback decision, customer-visible data confidence notes, follow-up work, and verification.
- Confirm no incident note contains sensitive raw payloads.

## Ownership And Follow-Up

Required ownership fields:

- `service_area`
- `owner_team`
- `backup_owner`
- `alert_owner`
- `data_owner`
- `runbook_url`
- `dashboard_url`
- `last_reviewed_at`

Required follow-up fields:

- `follow_up_id`
- `follow_up_type`
- `severity`
- `priority`
- `status`
- `due_date`
- `verification`
- `closure_note`

Field values must stay short, stable, and filterable. Do not store personal phone numbers, private email addresses, raw user input, request bodies, route polylines, credential material, raw station rows, raw file contents, stack traces, or full backend responses.

## Phase 6B Alignment

Covered from `docs/phase-6b-file-status.md`:

- Last successful import time by source.
- Latest snapshot date by source.
- Raw file hash captured for every import.
- Imported row count and rejected row count as future alert context.
- Stale connector count by region.
- No successful import, missing raw hash, high rejected-row ratio, and high stale connector ratio alert candidates.

Deferred until importer or rollup runtime boundaries exist:

- Dedicated importer row-count metrics.
- Dedicated normalized status-event-count metrics.
- Rollup calculation duration and failure metrics.

## Verification

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\production-observability-checklist.md
Select-String -Path D:\fleet\chargeflow-kr\docs\production-observability-checklist.md -Pattern "Frontend Error Tracking|Backend Error Tracking|File Import Failure Checks|Stale Data Checks|API Latency Checks"
Select-String -Path D:\fleet\chargeflow-kr\docs\production-observability-checklist.md -Pattern "Queue Depth Placeholder|Deploy Readiness|Incident Triage|Ownership And Follow-Up|Phase 6B Alignment"
```
