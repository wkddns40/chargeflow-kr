# Phase 6B File Status Pipeline

## Scope

Phase 6B moves ChargeFlow KR from a single displayed snapshot toward imported file snapshot history. The near-term status path remains file-download based: import local or directly downloadable public files, preserve source metadata, and derive availability rollups from imported rows.

This phase does not implement real-time API polling, public-data OpenAPI credentials, partner integrations, or OCPI.

<!--
Deferred: public-data OpenAPI application, ServiceKey handling, getChargerStatus polling by zcode.
-->

## File Snapshot Lifecycle

1. Acquire a login-free public file through manual download, direct public URL, or operator-provided local file.
2. Store raw files outside git under `backend/data/raw/`.
3. Record source metadata before parsing:
   - `source_name`
   - `source_url` or acquisition note
   - `downloaded_at`
   - `snapshot_date`
   - `raw_file_hash`
4. Parse rows into station, connector, and status-event records.
5. Reject or quarantine malformed rows with row-level validation errors.
6. Upsert stable station and connector master data.
7. Append status history into `status_events`.
8. Calculate availability rollups for UI and monitoring use.

Import boundaries:

- Importers may read local raw files and committed sanitized fixtures.
- Importers must not fetch login-gated pages.
- Importers must not require API keys or ServiceKey values.
- Importers must be deterministic for the same input file.
- Raw downloaded files are replaceable inputs, not canonical app code.

## File Source Metadata

Every imported snapshot needs metadata that can be shown in API responses, debug logs, and monitoring.

Suggested metadata shape:

```json
{
  "source_name": "Korea Environment Corporation EV charger location/operation information file dataset",
  "source_url": "manual-or-public-download-url",
  "downloaded_at": "2026-05-19T00:00:00+09:00",
  "snapshot_date": "2026-05-19",
  "raw_file_hash": "sha256:..."
}
```

Rules:

- `raw_file_hash` is mandatory for imported raw files.
- Hash algorithm should be `sha256`.
- `snapshot_date` is the publisher or file-effective date when available.
- `downloaded_at` is the local acquisition time.
- Missing publisher dates should be represented as `null` and treated as lower-confidence freshness.

## Schema Notes

### `stations`

Existing table:

```text
stations(id, name, operator, address, region_code, geom, created_at, updated_at)
```

Purpose:

- Stable station/site identity.
- Spatial truth through PostGIS `geom`.
- Region-level grouping through `region_code`.

Import rules:

- Use deterministic station IDs from the source when present.
- Validate longitude/latitude before writing `geom`.
- Update `updated_at` when station identity or location fields change.
- Do not store transient availability directly on `stations`.

### `connectors`

Existing table:

```text
connectors(id, station_id, connector_type, max_kw, current_type, status, status_updated_at)
```

Purpose:

- Stable connector/charger-unit identity under a station.
- Current known status cache for fast station responses.
- Link target for status history.

Import rules:

- Use deterministic connector IDs from source station and charger identifiers.
- Normalize unknown connector values to explicit `unknown` fallbacks where needed.
- Update `status` and `status_updated_at` from the newest valid file event.
- Keep connector master fields separate from status-event history.

### `status_events`

Existing table:

```text
status_events(id, connector_id, status, source, observed_at, received_at, raw_file_hash)
```

Purpose:

- Append-only status history generated from file imports.
- Input for freshness checks, availability rollups, and later monitoring.

Event fields:

- `connector_id`: references `connectors.id`.
- `status`: normalized value such as `available`, `occupied`, `offline`, or `unknown`.
- `source`: source dataset or importer name.
- `observed_at`: status observation timestamp from the file or derived snapshot time.
- `received_at`: local import time.
- `raw_file_hash`: hash linking the event back to raw input.

Import rules:

- Do not overwrite previous events for different snapshots.
- Deduplicate exact repeated events by connector, status, observed time, source, and raw file hash.
- If source has only snapshot-level time, use the snapshot timestamp for `observed_at`.
- If no usable timestamp exists, reject the row or map it to a documented snapshot fallback.

### `availability_rollups`

Future table contract:

```text
availability_rollups(
  id,
  region_code,
  window_start,
  window_end,
  connector_count,
  available_count,
  occupied_count,
  offline_count,
  unknown_count,
  stale_count,
  source,
  snapshot_date,
  raw_file_hash,
  calculated_at
)
```

Purpose:

- Precomputed availability summaries for dashboard panels, monitoring, and later natural-language answers.
- Avoid repeated scans over `status_events` for common region/time-window queries.

Rollup rules:

- Count only the newest event per connector within the rollup window.
- Preserve `source`, `snapshot_date`, and `raw_file_hash` so rollups can cite freshness.
- Store unknown and stale counts separately.
- Recompute deterministically for the same event set and window.

## Freshness Rules

Freshness describes how recently the imported file snapshot was acquired or observed.

Recommended labels:

- `fresh`: latest snapshot age is 0-2 days.
- `aging`: latest snapshot age is more than 2 days and up to 7 days.
- `stale`: latest snapshot age is more than 7 days.
- `unknown`: no usable `snapshot_date`, `observed_at`, or `downloaded_at` exists.

Source precedence:

1. Row-level `observed_at`.
2. File-level `snapshot_date`.
3. Local `downloaded_at`.
4. `unknown`.

API and UI text should cite the date basis when possible, for example `snapshot_date=2026-05-19`.

## Stale Rules

Stale status means the latest event for a connector is too old to trust as current availability.

Default stale threshold:

- Connector status is stale when the newest `observed_at` is older than 7 days.

Handling:

- Stale connectors remain visible.
- Stale connectors should not count as confidently available.
- Availability rollups should expose `stale_count`.
- UI answers should distinguish stale status from `offline` and `unknown`.

## Monitoring And Alerting Contract

Phase 6B prepares metric names but does not implement monitoring exporters.

Needed checks:

- Last successful import time by source.
- Latest snapshot date by source.
- Raw file hash captured for every import.
- Imported row count and rejected row count.
- Status-event count by normalized status.
- Stale connector count by region.
- Rollup calculation duration and failure count.

Alert candidates:

- No successful import for more than 7 days.
- Missing `raw_file_hash` in an import run.
- Rejected row ratio exceeds a configured threshold.
- Stale connector ratio exceeds a configured threshold.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\phase-6b-file-status.md
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6b-file-status.md -Pattern "stations|connectors|status_events|availability_rollups"
Select-String -Path D:\fleet\chargeflow-kr\docs\phase-6b-file-status.md -Pattern "freshness|stale|raw_file_hash|ServiceKey"
```

Pass conditions:

- Document exists.
- Document covers `stations`, `connectors`, `status_events`, and `availability_rollups`.
- Document defines freshness and stale rules.
- Document requires file source metadata and `raw_file_hash`.
- Document keeps OpenAPI, ServiceKey, and real-time polling deferred.
