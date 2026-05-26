# Monitoring Metrics Contract

This document defines the Phase 6B monitoring metric contract for the file-dataset status pipeline and the Phase 6E production observability checklist.

The current phase only documents metric names and expected labels. It does not add a Prometheus exporter, Grafana dashboard, alert manager, or runtime instrumentation.

## Scope

Included:

- File import success and failure counts.
- File import failure check requirements.
- Station freshness by imported snapshot age.
- Stale data check requirements.
- Region-level availability ratio from `availability_rollups`.
- API latency for local backend endpoints.
- API latency check requirements.
- Queue depth placeholder requirements.
- Frontend error tracking requirements for production readiness.
- Backend error tracking requirements for production readiness.
- Deploy readiness checklist requirements.
- Incident triage checklist requirements.
- Ownership and follow-up field requirements.
- Phase 6B monitoring alignment review.

Deferred:

- Real-time OpenAPI polling metrics.
- External credential health checks.
- Prometheus scrape endpoint implementation.
- Grafana dashboard JSON.
- File import alert job implementation.
- Stale data alert rule implementation.
- API latency alert rule implementation.
- Queue depth metric, worker, and queue exporter implementation.
- Frontend error tracking SDK wiring.
- Backend error tracking SDK or OpenTelemetry exporter wiring.
- Deploy gate automation, dashboard provisioning, and rollback automation.
- Incident ticket automation, on-call rotation, and status-page automation.
- Ownership registry, issue tracker sync, and follow-up reminder automation.
- Additional importer row-count, status-event-count, and rollup-job metrics.
- Alert routing and paging policies.

## Metric Inventory

| Metric | Type | Unit | Labels | Description |
| --- | --- | --- | --- | --- |
| `evstation_file_import_success_total` | counter | imports | `source`, `snapshot_date` | Count of successful file import runs. Increment once after the raw file is parsed, validated, and committed. |
| `evstation_file_import_failure_total` | counter | failures | `source`, `stage`, `reason` | Count of failed file import runs. Use `stage` values such as `download`, `parse`, `validate`, or `write`. |
| `evstation_station_freshness_seconds` | gauge | seconds | `source`, `region_code`, `freshness_label` | Age of the newest usable station or connector status snapshot. Lower is fresher. |
| `evstation_region_available_ratio` | gauge | ratio | `region_code`, `source`, `snapshot_date` | Available connector ratio per region after stale connectors are separated from confident status counts. |
| `evstation_api_latency_seconds` | histogram | seconds | `route`, `method`, `status_code` | Backend API request duration. Use route templates such as `/api/stations`, not raw URLs. |

## File Import Metrics

`evstation_file_import_success_total`

- Type: counter.
- Unit: imports.
- Labels:
  - `source`: importer or dataset name, for example `synthetic-status-file-sample`.
  - `snapshot_date`: file-effective date when available, otherwise `unknown`.
- Increment after station, connector, and `status_events` writes complete.
- Do not increment for partially written or quarantined import runs.

`evstation_file_import_failure_total`

- Type: counter.
- Unit: failures.
- Labels:
  - `source`: importer or dataset name.
  - `stage`: `download`, `parse`, `validate`, `write`, or `unknown`.
  - `reason`: low-cardinality reason such as `missing_file`, `invalid_json`, `schema_error`, or `write_error`.
- Increment once per failed import run.
- Keep `reason` low-cardinality; do not include file paths, stack traces, raw exception messages, or credential values.

## File Import Failure Check

As of 5.3.3, file import failure checks remain a production readiness requirement, not a runtime implementation. No scheduler, alert job, Prometheus rule, or import runner change is added in this task.

Required checks for a future file import monitor:

- Alert when `evstation_file_import_failure_total` increases for any `source` within the active import window.
- Alert when no `evstation_file_import_success_total` increment exists for a required `source` within the expected freshness window.
- Alert when the latest imported metadata is missing `raw_file_hash`, `snapshot_date`, `downloaded_at`, or source identity.
- Alert when rejected-row ratio exceeds the configured threshold for one import run.
- Alert when an import reaches `parse`, `validate`, or `write` failure stage and leaves no committed `status_events`.
- Alert when quarantined rows exist without a matching low-cardinality `reason`.
- Treat a partial import as failure unless station, connector, status event, and availability rollup writes are all complete.
- Keep per-source checks separate so one optional dataset does not mask failure in a required dataset.

Allowed alert context:

- `source`, `snapshot_date`, `stage`, `reason`, committed row counts, rejected row count, quarantine count, and raw file hash prefix.
- Do not include raw file paths, full file contents, credential material, row payloads, stack traces, or user data in alert text.

Runbook requirements:

- Link each alert to the source document, expected import cadence, last successful snapshot, and quarantine location if available.
- Include a manual recovery step: inspect quarantined rows, validate source metadata, rerun import from the same raw file, then confirm success and freshness metrics.
- Escalate repeated failure across two consecutive scheduled windows as a production data freshness incident.

## Freshness And Availability Metrics

`evstation_station_freshness_seconds`

- Type: gauge.
- Unit: seconds.
- Labels:
  - `source`: dataset or importer name.
  - `region_code`: Korean region code, or `unknown` when no region is available.
  - `freshness_label`: `fresh`, `aging`, `stale`, or `unknown`.
- Calculate from the newest usable timestamp using the Phase 6B precedence:
  1. row-level `observed_at`;
  2. file-level `snapshot_date`;
  3. local `downloaded_at`;
  4. `unknown`.
- Freshness labels follow `docs/phase-6b-file-status.md`:
  - `fresh`: 0-2 days old.
  - `aging`: more than 2 days and up to 7 days old.
  - `stale`: more than 7 days old.
  - `unknown`: no usable timestamp.

`evstation_region_available_ratio`

- Type: gauge.
- Unit: ratio from `0.0` to `1.0`.
- Labels:
  - `region_code`: Korean region code.
  - `source`: dataset or importer name.
  - `snapshot_date`: file-effective date when available.
- Numerator: non-stale latest connector events with normalized status `available`.
- Denominator: latest connector events in the same region and window, including stale connectors.
- Stale connectors contribute to `stale_count` in rollups and should not count as confidently available.
- Recompute deterministically from `availability_rollups` inputs.

## Stale Data Check

As of 5.3.4, stale data checks remain a production readiness requirement, not a runtime implementation. No scheduler, alert job, Prometheus rule, API response change, or frontend banner is added in this task.

Required checks for a future stale data monitor:

- Alert when `evstation_station_freshness_seconds` for a required `source` and `region_code` exceeds the configured stale threshold or reports `freshness_label="stale"` across consecutive evaluation windows.
- Alert when `freshness_label="unknown"` persists for a required source or region because no usable `observed_at`, `snapshot_date`, or `downloaded_at` timestamp exists.
- Alert when `evstation_region_available_ratio` is computed with `stale_count` above the configured stale-share threshold for the region denominator.
- Alert when every region for a required source becomes stale, or when the latest `snapshot_date` is older than the expected import cadence.
- Treat stale data as a data confidence issue, not as evidence that chargers are offline.
- Keep required source and region checks separate so one optional or unavailable dataset does not page for unrelated regions.

Allowed alert context:

- `source`, `region_code`, `freshness_label`, `snapshot_date`, freshness age seconds, `stale_count`, denominator count, configured threshold, and import cadence.
- Do not include raw station rows, connector payloads, user search text, route planner input, credential material, stack traces, or full raw files in alert text.

Runbook requirements:

- Link each alert to the latest imported metadata, expected source cadence, last successful snapshot, and affected regions.
- Compare `observed_at`, `snapshot_date`, and `downloaded_at` precedence before deciding whether the source is stale or only missing row-level timestamps.
- Rerun the import from the latest trusted raw file or mark the source degraded when upstream data is unavailable.
- Confirm UI and assistant responses disclose stale data instead of presenting stale availability as live status.
- Escalate repeated stale or unknown freshness across the configured windows as a production data freshness incident.

## API Latency Metric

`evstation_api_latency_seconds`

- Type: histogram.
- Unit: seconds.
- Labels:
  - `route`: route template, for example `/api/stations`.
  - `method`: HTTP method, for example `GET`.
  - `status_code`: HTTP response code family or exact code, for example `200` or `400`.
- Suggested buckets: `0.01`, `0.025`, `0.05`, `0.1`, `0.25`, `0.5`, `1.0`, `2.5`.
- Do not label by bbox, query string, IP address, user input, or raw error text.

## API Latency Check

As of 5.3.5, API latency checks remain a production readiness requirement, not a runtime implementation. No middleware, histogram exporter, Prometheus rule, API route change, or frontend retry behavior is added in this task.

Required checks for a future API latency monitor:

- Alert when p95 or p99 `evstation_api_latency_seconds` for a required `route` and `method` exceeds the configured latency threshold across consecutive evaluation windows.
- Track `GET /api/stations`, `POST /api/search/chargers`, and `POST /api/routes/charging-plan` as route templates, not raw URLs.
- Keep success, client-error, and server-error latency separate through `status_code` so expected `400` validation responses do not hide slow `200` or `500` responses.
- Alert when a required route has no latency samples during an expected traffic window, because missing data can hide instrumentation failure.
- Treat route planner latency separately from station search latency because graph execution and fixture filtering have different performance profiles.
- Do not page on one isolated slow request unless it persists across the configured windows or breaches the deploy health threshold.

Allowed alert context:

- `route`, `method`, `status_code`, percentile, configured threshold, evaluation window, sample count, release, and environment.
- Do not include bbox values, query strings, request bodies, raw search text, route polylines, user location, IP address, cookies, authorization headers, stack traces, or full backend responses in alert text.

Runbook requirements:

- Compare p50, p95, and p99 latency by route before deciding whether the issue is broad backend slowness or a single endpoint regression.
- Check whether the slow route correlates with a new release, fixture reload, import run, route planner graph change, or external dependency boundary.
- Inspect backend logs using the request or correlation ID once backend error tracking is implemented, without copying sensitive request payloads into the incident.
- Confirm whether elevated latency also increases `500` responses, frontend request failures, or route planner timeouts.
- Escalate sustained latency across the configured windows as a deploy health incident.

## Queue Depth Placeholder

As of 5.3.6, queue depth remains a placeholder for future production observability, not a runtime implementation. The current local app has no production worker queue, message broker, background job table, queue exporter, or queue alert rule added in this task.

Placeholder contract for a future queue depth metric:

- Reserve `evstation_queue_depth` as the candidate gauge name only after a real queue boundary exists.
- Use low-cardinality labels such as `queue_name`, `state`, `source`, `release`, and `environment`.
- Keep `state` values bounded, for example `pending`, `running`, `retry`, and `dead_letter`.
- Track oldest job age as a separate future metric instead of overloading queue depth with age semantics.
- Separate file import, route planner, and provider request queues if they are implemented later because their backpressure and recovery paths differ.
- Do not infer charger availability, station demand, user wait time, or route ETA from queue depth.

Allowed alert context:

- `queue_name`, `state`, `source`, depth value, configured threshold, evaluation window, worker count, release, and environment.
- Do not include job IDs, raw file contents, station rows, search prompts, route polylines, request bodies, credential material, stack traces, or user data in alert text.

Runbook requirements:

- Confirm whether queue growth is caused by stopped workers, import backpressure, provider outage, retry storms, or a new release.
- Compare pending, retry, and dead-letter depth before deciding whether to pause producers or scale workers.
- Check oldest job age once that metric exists, because a shallow queue with old jobs can still indicate stuck processing.
- Drain or quarantine failed jobs using the future queue system's supported recovery path; do not manually edit production queue storage without a runbook.
- Escalate sustained queue growth across the configured windows as a production readiness incident.

## Frontend Error Tracking Requirements

As of 5.3.1, frontend error tracking remains a production requirement, not a runtime implementation. No SDK dependency, DSN, source-map upload, or browser error handler is added in this task.

Required coverage for a future frontend error tracking implementation:

- Capture uncaught React render errors through a top-level error boundary.
- Capture unhandled promise rejections from data loading, map initialization, and panel submit flows.
- Capture build `release`, deployment `environment`, current route or view name, and feature flag state.
- Group errors by stable component or subsystem values such as `map`, `station-data`, `llm-search`, and `route-planner`.
- Record browser family, app version, and frontend build hash when available.
- Preserve source-map support for production stack traces without exposing source maps publicly unless access is controlled.
- Sample repeated noisy errors and suppress known non-actionable browser extension failures.
- Keep frontend reporting optional in local development and disabled when no tracking DSN is configured.

Privacy and data rules:

- Do not record raw user search text, route polylines, precise user location, IP address, auth tokens, API keys, cookies, or full backend response bodies.
- Redact query strings and request bodies before attaching network context.
- Keep station IDs, endpoint route templates, status codes, and low-cardinality feature flags as allowed debugging context.
- Treat LLM search prompts and route planner inputs as sensitive unless a later privacy review explicitly allows retention.

Operational requirements:

- Frontend error alerts should separate deploy-breaking crashes from low-volume recoverable UI errors.
- A deploy should be considered unhealthy if a new release creates a sustained increase in top-level render crashes.
- Error tracking must not block rendering, map interaction, local dataset loading, or form submission if the tracking provider is unavailable.
- Provider selection, SDK wiring, source-map upload automation, and alert routing are deferred to later implementation tasks.

## Backend Error Tracking Requirements

As of 5.3.2, backend error tracking remains a production requirement, not a runtime implementation. No SDK dependency, OpenTelemetry exporter, middleware, request ID generator, or logging sink is added in this task.

Required coverage for a future backend error tracking implementation:

- Capture unhandled FastAPI exceptions and unexpected `500` responses.
- Capture startup failures, station fixture load failures, import pipeline failures, and route planner graph failures.
- Capture low-cardinality route template, HTTP method, status code, exception class, deployment environment, release, and service name.
- Add a request or correlation ID to backend logs and error events, then expose it in error responses only when safe.
- Keep expected `400` validation errors out of alerting by default, while allowing sampled visibility for schema drift.
- Separate local file/data failures from application bugs so import issues do not look like code regressions.
- Track dependency and fixture boundaries such as `station_fixture`, `search_schema`, `route_planner_graph`, and `status_import`.
- Preserve stack traces for server-side debugging without exposing them in API responses.

Privacy and data rules:

- Do not record raw request bodies, search text, route polylines, API keys, cookies, authorization headers, client IP addresses, or full station fixture rows.
- Redact query strings and headers before attaching request context.
- Keep route templates, status codes, stable error codes, low-cardinality node names, and sanitized fixture names as allowed context.
- Treat LLM search commands and route planner payloads as sensitive unless a later privacy review explicitly allows retention.

Operational requirements:

- Backend error alerts should page only for sustained `500` spikes, startup failures, repeated import failures, or route planner graph failures.
- A deploy should be considered unhealthy if a new release creates a sustained increase in uncaught exceptions or health-check failures.
- Error tracking must fail open: provider outage must not block local API responses, station search, route planning, or file import.
- Provider selection, middleware wiring, correlation ID strategy, sampling, and alert routing are deferred to later implementation tasks.

## Deploy Readiness Checklist

As of 5.3.7, the deploy readiness checklist remains a production observability requirement, not a runtime or CI implementation. No workflow file, deployment script, environment variable, dashboard, alert route, rollback automation, or release gate is added in this task.

Required go/no-go checks before a future production deploy:

- Confirm frontend and backend error tracking have provider, environment, release, sampling, and privacy redaction decisions recorded.
- Confirm file import failure, stale data, API latency, and queue depth checks have owners, thresholds, evaluation windows, and runbook links.
- Confirm alert routing separates deploy-breaking crashes, sustained backend `500` errors, stale data incidents, import failures, latency breaches, and queue backpressure.
- Confirm dashboards expose import health, freshness age, stale connector ratio, regional availability, API latency, frontend errors, backend errors, and any future queue depth metric.
- Confirm source-map upload and access rules are decided before frontend production stack traces are enabled.
- Confirm backend request or correlation ID handling is decided before incident workflows depend on cross-system tracing.
- Confirm privacy review covers search prompts, route polylines, precise location, query strings, request bodies, cookies, authorization headers, and raw source files.
- Confirm local demo-mode behavior and missing observability credentials fail open instead of blocking station search, map rendering, route planning, or file import.

Required post-deploy checks:

- Check the new release appears in frontend and backend error tracking with the expected environment label.
- Check API latency samples exist for `GET /api/stations`, `POST /api/search/chargers`, and `POST /api/routes/charging-plan`.
- Check the latest file import success, failure, freshness, and regional availability metrics still report low-cardinality labels.
- Check no alert includes raw user input, credential material, raw file contents, stack traces, or full backend responses.
- Check deploy health does not regress through sustained top-level frontend crashes, backend `500` spikes, stale required data, import failure, or latency breach.

Rollback triggers:

- Roll back when a new release creates sustained frontend render crashes, sustained backend `500` responses, broken station search, broken route planning, or unavailable required data.
- Roll back when observability instrumentation blocks the product path instead of failing open.
- Do not roll back only because an optional metric or optional dataset is absent unless the deploy policy marks it required.

## Incident Triage Checklist

As of 5.3.8, the incident triage checklist remains a production observability requirement, not a runtime or operations automation implementation. No ticketing integration, on-call rotation, status-page update, alert route, dashboard panel, or escalation bot is added in this task.

Initial classification:

- Identify the primary signal as frontend crash, backend `500` spike, file import failure, stale data, API latency breach, queue backpressure, or missing observability data.
- Classify the impact as user-visible outage, degraded route planning, degraded charger search, data confidence issue, deploy health regression, or optional feature degradation.
- Confirm whether the alert is tied to a new release, missing instrumentation, source dataset failure, local fixture issue, or external provider boundary.
- Separate optional dataset or placeholder metric gaps from required production path failures.
- Treat stale data and missing freshness as confidence incidents, not as proof that chargers are unavailable.

Minimum triage context:

- `release`, `environment`, alert name, evaluation window, first-seen time, affected route or feature, and current deploy status.
- For API incidents: `route`, `method`, `status_code`, p95 or p99 latency, sample count, and correlation ID when available.
- For import and stale data incidents: `source`, `region_code`, `snapshot_date`, `freshness_label`, `raw_file_hash` prefix, `stale_count`, and last successful import time.
- For queue incidents after a queue exists: `queue_name`, `state`, depth value, worker count, oldest job age metric if available, and retry or dead-letter count.
- Do not paste raw search prompts, route polylines, precise user location, request bodies, cookies, authorization headers, full stack traces, raw station rows, raw file contents, or credential material into incident notes.

First response steps:

- Check deploy readiness and rollback triggers before changing thresholds or muting alerts.
- Compare frontend errors, backend errors, API latency, import health, freshness, and regional availability before declaring a single root cause.
- Verify whether the product path fails open when observability providers or credentials are unavailable.
- If the issue follows a new release and affects required paths, prepare rollback while preserving minimal evidence for root-cause analysis.
- If the issue is data-source related, mark affected source or region degraded rather than presenting stale availability as live status.
- If the issue is only missing optional telemetry, open a follow-up instead of paging.

Closure requirements:

- Record impact, timeline, root cause, mitigation, rollback decision, and customer-visible data confidence notes.
- Record which thresholds, runbooks, dashboards, alerts, or privacy redaction rules need follow-up.
- Confirm alerts returned to normal and that no incident note contains sensitive raw payloads.
- Link follow-up work to the future owner fields once ownership metadata is added.

## Ownership And Follow-Up Fields

As of 5.3.9, ownership and follow-up fields remain a production observability requirement, not a runtime or workflow automation implementation. No ownership registry, issue tracker sync, reminder job, alert route, contact directory, or escalation policy file is added in this task.

Required ownership fields for future checklist entries:

- `service_area`: low-cardinality area such as `frontend`, `backend`, `file_import`, `data_freshness`, `api_latency`, `queue`, or `deploy`.
- `owner_team`: team or role responsible for first response; avoid individual-only ownership.
- `backup_owner`: secondary team or role used when the primary owner is unavailable.
- `alert_owner`: team or role allowed to change thresholds, routing, and mute policy.
- `data_owner`: team or role responsible for source cadence, freshness, and import correctness when the check depends on external data.
- `runbook_url` and `dashboard_url`: stable internal links once those systems exist.
- `last_reviewed_at`: date when the owner, thresholds, and runbook were last reviewed.

Required follow-up fields for future incident and readiness work:

- `follow_up_id`: issue, PR, or ticket identifier once a tracker exists.
- `follow_up_type`: bounded value such as `threshold`, `runbook`, `dashboard`, `privacy`, `instrumentation`, `rollback`, or `owner`.
- `severity`: bounded value such as `sev1`, `sev2`, `sev3`, or `sev4`.
- `priority`: bounded value such as `high`, `medium`, or `low`.
- `status`: bounded value such as `open`, `blocked`, `in_progress`, `merged`, or `verified`.
- `due_date`: target date for remediation or review.
- `verification`: command, dashboard check, or manual validation needed to close the follow-up.
- `closure_note`: short summary of the fix or accepted risk.

Field hygiene:

- Keep field values short, stable, and suitable for filtering.
- Do not store personal phone numbers, private email addresses, raw user input, request bodies, route polylines, credential material, raw station rows, raw file contents, stack traces, or full backend responses in ownership or follow-up fields.
- Link sensitive evidence from the approved incident system instead of copying it into checklist fields.
- Required production checks should not be considered deploy-ready without an `owner_team`, `backup_owner`, `runbook_url`, `dashboard_url`, and `last_reviewed_at`.

## Phase 6B Monitoring Alignment Review

As of 5.3.10, the production observability checklist has been reviewed against `docs/phase-6b-file-status.md`. This review does not add metric exporters, importer counters, rollup job instrumentation, alert rules, dashboard panels, or runtime code.

Coverage against Phase 6B needed checks:

| Phase 6B check | 5.3 coverage | Status |
| --- | --- | --- |
| Last successful import time by source | `evstation_file_import_success_total` plus the file import failure check for missing success in the expected freshness window. | Covered as future alert logic. |
| Latest snapshot date by source | `snapshot_date` label and stale data checks for old or missing snapshot dates. | Covered. |
| Raw file hash captured for every import | File import failure check alerts when `raw_file_hash` is missing. | Covered. |
| Imported row count and rejected row count | File import failure check allows committed row counts, rejected row count, quarantine count, and rejected-row ratio in alert context. | Covered as checklist context; dedicated row-count metrics are deferred. |
| Status-event count by normalized status | Backend error tracking and import triage mention `status_import`, but no dedicated metric exists yet. | Deferred until importer instrumentation exists. |
| Stale connector count by region | `stale_count` in `availability_rollups`, stale data checks, and regional availability metric context. | Covered. |
| Rollup calculation duration and failure count | Availability rollup recomputation is documented, but no rollup job metric exists yet. | Deferred until a rollup job/exporter exists. |

Coverage against Phase 6B alert candidates:

- No successful import for more than 7 days maps to the file import failure check and stale data check.
- Missing `raw_file_hash` maps to the file import failure check and incident triage context.
- Rejected row ratio above threshold maps to the file import failure check and ownership follow-up fields.
- Stale connector ratio above threshold maps to the stale data check through `stale_count` and region denominator.

Alignment decisions:

- Keep the current Phase 6B metric inventory limited to the five documented metric names until runtime instrumentation is approved.
- Do not add real-time OpenAPI polling, ServiceKey handling, partner integrations, OCPI, or external credential health checks.
- Do not treat stale data as offline charger status; keep it as a data confidence issue across monitoring, incident triage, and deploy readiness.
- Add future row-count, status-event-count, rollup-duration, and rollup-failure metrics only after importer and rollup job boundaries are implemented.

## Example Samples

```text
evstation_file_import_success_total{source="synthetic-status-file-sample",snapshot_date="2026-05-19"} 1
evstation_file_import_failure_total{source="synthetic-status-file-sample",stage="validate",reason="schema_error"} 1
evstation_station_freshness_seconds{source="synthetic-status-file-sample",region_code="KR-11",freshness_label="fresh"} 3600
evstation_region_available_ratio{region_code="KR-11",source="synthetic-status-file-sample",snapshot_date="2026-05-19"} 0.72
evstation_api_latency_seconds_bucket{route="/api/stations",method="GET",status_code="200",le="0.1"} 42
```

## Future Prometheus And Grafana Notes

When runtime instrumentation is added later:

- Expose metrics from the backend only after the file import and API paths are stable.
- Use a dedicated scrape endpoint such as `/metrics`.
- Keep labels low-cardinality and avoid raw user input.
- Build Grafana panels for import health, freshness age, stale connector ratio, regional availability, and API latency.
- Add alerts for no successful import for more than 7 days, missing `raw_file_hash`, high rejected-row ratio, high stale connector ratio, and high API latency.
- Add file import failure checks only after required source cadence, rejection thresholds, and quarantine paths are defined.
- Add stale data checks only after required source, region, cadence, and stale-share thresholds are defined.
- Add API latency checks only after route-specific thresholds, expected traffic windows, and deploy health policy are defined.
- Add queue depth metrics only after a real queue boundary, worker model, state names, and backpressure thresholds are defined.
- Add frontend error tracking only after provider selection, privacy redaction, and source-map upload rules are decided.
- Add backend error tracking only after provider selection, request redaction, correlation ID, and sampling rules are decided.
- Add deploy readiness automation only after production environments, dashboard URLs, alert owners, and rollback policy are defined.
- Add incident triage automation only after alert routing, owner fields, incident tooling, and status-page policy are defined.
- Add ownership and follow-up automation only after owner taxonomy, issue tracker IDs, reminder policy, and privacy rules are defined.
- Add Phase 6B gap metrics only after importer row counts, normalized status-event counts, and rollup job boundaries are implemented.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "evstation_file_import_success_total|evstation_file_import_failure_total|evstation_station_freshness_seconds|evstation_region_available_ratio|evstation_api_latency_seconds"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "counter|gauge|histogram|seconds|ratio|Prometheus|Grafana"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "File Import Failure Check|raw_file_hash|rejected-row ratio|partial import|quarantined rows|production data freshness incident"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Stale Data Check|freshness_label=""stale""|freshness_label=""unknown""|stale_count|data confidence issue"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "API Latency Check|p95|p99|GET /api/stations|POST /api/search/chargers|POST /api/routes/charging-plan|deploy health incident"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Queue Depth Placeholder|evstation_queue_depth|queue_name|oldest job age|dead_letter|production worker queue"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Frontend Error Tracking Requirements|error boundary|unhandled promise|source-map|raw user search text|tracking DSN"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Backend Error Tracking Requirements|FastAPI exceptions|request or correlation ID|raw request bodies|fail open|OpenTelemetry"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Deploy Readiness Checklist|go/no-go|post-deploy|rollback|alert routing|dashboard|fail open"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Incident Triage Checklist|Initial classification|Minimum triage context|First response steps|Closure requirements|data confidence issue"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Ownership And Follow-Up Fields|owner_team|backup_owner|follow_up_id|last_reviewed_at|closure_note|owner taxonomy"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "Phase 6B Monitoring Alignment Review|Status-event count by normalized status|Rollup calculation duration and failure count|Phase 6B alert candidates|Phase 6B gap metrics"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6b-file-status.md -Pattern "Last successful import time|Status-event count by normalized status|Rollup calculation duration and failure count|Stale connector ratio"
```

Pass conditions:

- Document exists.
- Document lists all required metric names.
- Each metric defines type, unit, labels, and purpose.
- File import, freshness, availability, and API latency metrics are covered.
- File import failure checks cover failure increments, missing successful imports, source metadata, rejected rows, partial writes, and runbook requirements.
- Stale data checks cover stale and unknown freshness, stale_count thresholds, data confidence wording, allowed alert context, and runbook requirements.
- API latency checks cover p95 and p99 thresholds, route templates, status-code separation, missing samples, allowed alert context, and runbook requirements.
- Queue depth placeholder covers the candidate metric name, bounded labels, queue states, oldest-job-age separation, allowed alert context, and deferred runtime implementation.
- Prometheus and Grafana are documented as future implementation work only.
- Frontend error tracking requirements cover crash capture, privacy redaction, release context, and deferred SDK wiring.
- Backend error tracking requirements cover server exceptions, privacy redaction, correlation IDs, alerting, and deferred exporter wiring.
- Deploy readiness checklist covers go/no-go checks, post-deploy validation, rollback triggers, privacy review, alert routing, and deferred automation.
- Incident triage checklist covers classification, minimum context, first response, closure requirements, sensitive data exclusions, and deferred automation.
- Ownership and follow-up fields cover owner roles, backup owner, alert owner, data owner, follow-up IDs, status, verification, closure notes, field hygiene, and deferred automation.
- Phase 6B alignment review maps each Phase 6B needed check and alert candidate to covered or deferred 5.3 observability work.
