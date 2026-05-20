# Monitoring Metrics Contract

This document defines the Phase 6B monitoring metric contract for the file-dataset status pipeline.

The current phase only documents metric names and expected labels. It does not add a Prometheus exporter, Grafana dashboard, alert manager, or runtime instrumentation.

## Scope

Included:

- File import success and failure counts.
- Station freshness by imported snapshot age.
- Region-level availability ratio from `availability_rollups`.
- API latency for local backend endpoints.

Deferred:

- Real-time OpenAPI polling metrics.
- External credential health checks.
- Prometheus scrape endpoint implementation.
- Grafana dashboard JSON.
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

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "evstation_file_import_success_total|evstation_file_import_failure_total|evstation_station_freshness_seconds|evstation_region_available_ratio|evstation_api_latency_seconds"
Select-String -Path D:\fleet\chargeflow-kr\docs\monitoring-metrics.md -Pattern "counter|gauge|histogram|seconds|ratio|Prometheus|Grafana"
```

Pass conditions:

- Document exists.
- Document lists all required metric names.
- Each metric defines type, unit, labels, and purpose.
- File import, freshness, availability, and API latency metrics are covered.
- Prometheus and Grafana are documented as future implementation work only.
