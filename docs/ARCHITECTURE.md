# Architecture

## Current MVP

```mermaid
flowchart LR
    browser[Browser] --> frontend[React + MapLibre + deck.gl]
    frontend --> demo[Static sample-chargers.json]
    frontend --> api[FastAPI]
    api --> pg[(Postgres + PostGIS)]
```

## Target Path

```mermaid
flowchart LR
    browser[Browser] --> frontend[React + MapLibre + deck.gl]
    frontend --> stations[Station JSON API]
    frontend --> tiles[MVT Tile API]
    frontend --> search[LLM Search API]

    stations --> pg[(Postgres + PostGIS)]
    tiles --> pg
    search --> tools[Typed Query Tools]
    tools --> pg

    ingest[File Download Importers] --> pg
    pg --> rollups[Availability Rollups]
```

## Design Rules

- PostGIS owns spatial truth.
- LLM search never answers distance, availability, or filters from memory.
- Frontend renders large layers through deck.gl, not DOM markers.
- Static GeoJSON remains demo-only.
- Public-data API keys remain deferred; near-term ingestion uses login-free downloaded files.
