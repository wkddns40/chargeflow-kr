# Migration From EV-STATION

ChargeFlow KR starts from EV-STATION's proven frontend map choices, but not its full legacy product surface.

## Migrated

- Charger GeoJSON domain types.
- Geo helpers for valid coordinates, latest point, and path construction.
- MapLibre + deck.gl shell pattern.
- Static demo data mode for quick frontend smoke tests.

## Rebuilt

- Backend starts as FastAPI with PostGIS-oriented schema and APIs.
- Station loading is shaped around bbox queries, not full-file production fetches.
- Docs and roadmap target production-scale data ingestion and availability analysis.

## Deliberately Not Migrated

- Legacy sidebar panes.
- CSV export UI.
- MySQL-specific Flask implementation.
- Demo-only animated car layer.
