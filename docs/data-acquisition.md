# Data Acquisition Plan

## Scope

ChargeFlow KR uses login-free downloadable public files for the near-term data path. Phase 6A does not apply for public-data OpenAPI access, does not store API credentials, and does not poll real-time charger status APIs.

<!--
Deferred: public-data OpenAPI application, ServiceKey handling, getChargerStatus polling.
Current scope: login-free file downloads only.
-->

## Primary Dataset

Primary source:

- Korea Environment Corporation EV charger location/operation information file dataset.

Intended use:

- Seed `stations` with charger site identity, name, operator, address, region, and coordinates.
- Seed `connectors` with connector type, charger power, current type, and model data when present.
- Preserve source metadata so frontend and API responses can show dataset source and snapshot freshness.

Expected fields:

- station or charger id,
- station or charger name,
- operator,
- address,
- latitude and longitude,
- charger type or connector type,
- charging capacity or maximum kW,
- operating restriction or usage notes,
- snapshot or file publication date when available.

## Secondary Datasets

Allowed secondary sources:

- Jeju EV charging history file datasets.
- Regional or local government charger CSV files.
- Other public files only when downloadable without login or API credentials.

Use secondary sources for examples, enrichment, and historical availability analysis only after the primary station/connector master path is stable.

## Acquisition Mode

Allowed:

- Manual download from a public file page.
- Scripted download from a direct public file URL when no login, session cookie, API key, or quota approval is required.
- Documented local import from files already downloaded by the operator.

Forbidden in current scope:

- Applying for API keys.
- Committing ServiceKey or serviceKey values.
- Polling real-time status endpoints.
- Scraping login-gated pages.
- Adding partner, OCPI, or commercial provider integrations.

## Raw File Storage

Raw downloaded files go under:

```text
backend/data/raw/
```

Rules:

- Raw files are local artifacts and are not committed.
- Each raw file should keep its original filename when practical.
- If a filename is unclear, prefix it with an acquisition date such as `2026-05-19_`.
- Store a sidecar note or import metadata with source URL, download time, snapshot date, and file hash.
- Treat raw files as replaceable inputs, not canonical app code.

Suggested raw metadata shape:

```json
{
  "source_name": "Korea Environment Corporation EV charger location/operation information file dataset",
  "source_url": "manual-or-public-download-url",
  "downloaded_at": "2026-05-19T00:00:00+09:00",
  "snapshot_date": "2026-05-19",
  "raw_file_hash": "sha256:..."
}
```

## Fixture Commit Rules

Commit only small, sanitized samples under:

```text
backend/fixtures/
```

Fixture rules:

- Keep fixtures small enough for review.
- Remove credentials, private account data, session tokens, or non-public fields.
- Prefer synthetic data for performance fixtures.
- Real public sample fixtures must include source and snapshot metadata.
- Never overwrite `frontend/public/sample-chargers.json` from ingestion scripts.

## Import Contract

Future import code should:

- Parse raw file rows into station and connector records.
- Validate coordinates before writing to PostGIS.
- Normalize status and connector values with explicit unknown fallbacks.
- Preserve source name, source URL or acquisition note, snapshot date, and raw file hash.
- Emit row-level validation errors for malformed data.
- Keep import runs repeatable and deterministic for the same input file.

Status history and rollup design lives in `docs/phase-6b-file-status.md`.

## Verification

Commands:

```powershell
Test-Path D:\fleet\chargeflow-kr\docs\data-acquisition.md
Select-String -Path D:\fleet\chargeflow-kr\docs\data-acquisition.md -Pattern "login-free|deferred|backend/data/raw"
Select-String -Path D:\fleet\chargeflow-kr\docs\data-acquisition.md -Pattern "ServiceKey|polling|OpenAPI"
```

Pass conditions:

- Document exists.
- Document states login-free file downloads only.
- Document states API credential flow and polling are deferred.
- Document states raw files go under `backend/data/raw/`.
- Document states raw files are not committed.
- No instruction tells the developer to request API keys in the current phase.
