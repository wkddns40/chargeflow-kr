"""Seed the demo PostGIS database from the synthetic station fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = BACKEND_ROOT / "fixtures" / "synthetic-stations-7k.geojson"
DEFAULT_SOURCE = "synthetic-stations-7k"
VALID_STATUSES = {"available", "occupied", "offline", "unknown"}

STATION_UPSERT_SQL = """
INSERT INTO stations (id, name, operator, address, region_code, geom, updated_at)
VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    operator = EXCLUDED.operator,
    address = EXCLUDED.address,
    region_code = EXCLUDED.region_code,
    geom = EXCLUDED.geom,
    updated_at = EXCLUDED.updated_at
"""

CONNECTOR_UPSERT_SQL = """
INSERT INTO connectors (id, station_id, connector_type, max_kw, current_type, status, status_updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    station_id = EXCLUDED.station_id,
    connector_type = EXCLUDED.connector_type,
    max_kw = EXCLUDED.max_kw,
    current_type = EXCLUDED.current_type,
    status = EXCLUDED.status,
    status_updated_at = EXCLUDED.status_updated_at
"""

STATUS_EVENT_INSERT_SQL = """
INSERT INTO status_events (connector_id, status, source, observed_at, raw_file_hash)
SELECT %s, %s, %s, %s, %s
WHERE NOT EXISTS (
    SELECT 1
    FROM status_events
    WHERE connector_id = %s
      AND status = %s
      AND source = %s
      AND observed_at = %s
      AND raw_file_hash = %s
)
"""


@dataclass(frozen=True)
class DemoSeedRow:
    station_id: str
    connector_id: str
    name: str
    operator: str
    address: str
    region_code: str
    lon: float
    lat: float
    connector_type: str
    max_kw: float
    current_type: str
    status: str
    observed_at: datetime


@dataclass(frozen=True)
class SeedSummary:
    fixture: Path
    source: str
    raw_file_hash: str
    station_count: int
    connector_count: int
    status_event_count: int


def fixture_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fixture:
        for chunk in iter(lambda: fixture.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_feature_collection(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise ValueError("fixture must be a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("fixture features must be a list")
    return features


def build_seed_rows(features: Iterable[dict[str, Any]]) -> list[DemoSeedRow]:
    rows: list[DemoSeedRow] = []
    for index, feature in enumerate(features):
        rows.append(seed_row_from_feature(feature, index))
    return rows


def seed_row_from_feature(feature: dict[str, Any], index: int) -> DemoSeedRow:
    if not isinstance(feature, dict):
        raise ValueError(f"feature at index {index}: feature must be an object")

    lon, lat = _feature_coordinates(feature, index)
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError(f"feature at index {index}: properties must be an object")

    charger_id = _required_text(properties, "charger_id", index)
    connector_type = _required_text(properties, "connector_type", index)
    status = _required_text(properties, "status", index)
    if status not in VALID_STATUSES:
        raise ValueError(f"feature at index {index}: unsupported status: {status}")

    max_kw = _positive_float(properties.get("max_kw"), "max_kw", index)
    observed_at = _aware_datetime(
        _required_text(properties, "status_updated_at", index),
        "status_updated_at",
        index,
    )
    address = _required_text(properties, "address", index)

    return DemoSeedRow(
        station_id=charger_id,
        connector_id=f"{charger_id}-01",
        name=_required_text(properties, "charger_name", index),
        operator=_required_text(properties, "operator", index),
        address=address,
        region_code=derive_region_code(address, lon, lat),
        lon=lon,
        lat=lat,
        connector_type=connector_type,
        max_kw=max_kw,
        current_type=derive_current_type(connector_type),
        status=status,
        observed_at=observed_at,
    )


def derive_current_type(connector_type: str) -> str:
    normalized = connector_type.strip().casefold()
    if normalized.startswith("ac"):
        return "AC"
    return "DC"


def derive_region_code(address: str, lon: float, lat: float) -> str:
    stripped = address.strip()
    prefix_map = (
        ("Seoul", "KR-11"),
        ("Busan", "KR-26"),
        ("Daegu", "KR-27"),
        ("Incheon", "KR-28"),
        ("Gwangju", "KR-29"),
        ("Daejeon", "KR-30"),
        ("Ulsan", "KR-31"),
        ("Sejong", "KR-36"),
        ("Gyeonggi-do", "KR-41"),
        ("Jeju", "KR-50"),
        ("Seogwipo", "KR-50"),
    )
    for prefix, region_code in prefix_map:
        if stripped.startswith(prefix):
            return region_code

    if 33.0 <= lat <= 34.0 and 126.0 <= lon <= 127.0:
        return "KR-50"
    if 37.0 <= lat <= 38.5 and 126.0 <= lon <= 128.0:
        return "KR-41"
    return "unknown"


def station_params(rows: Sequence[DemoSeedRow]) -> list[tuple[Any, ...]]:
    return [
        (row.station_id, row.name, row.operator, row.address, row.region_code, row.lon, row.lat, row.observed_at)
        for row in rows
    ]


def connector_params(rows: Sequence[DemoSeedRow]) -> list[tuple[Any, ...]]:
    return [
        (
            row.connector_id,
            row.station_id,
            row.connector_type,
            row.max_kw,
            row.current_type,
            row.status,
            row.observed_at,
        )
        for row in rows
    ]


def status_event_params(rows: Sequence[DemoSeedRow], source: str, raw_file_hash: str) -> list[tuple[Any, ...]]:
    return [
        (
            row.connector_id,
            row.status,
            source,
            row.observed_at,
            raw_file_hash,
            row.connector_id,
            row.status,
            source,
            row.observed_at,
            raw_file_hash,
        )
        for row in rows
    ]


def seed_rows(database_url: str, rows: Sequence[DemoSeedRow], source: str, raw_file_hash: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(STATION_UPSERT_SQL, station_params(rows))
            cursor.executemany(CONNECTOR_UPSERT_SQL, connector_params(rows))
            cursor.executemany(STATUS_EVENT_INSERT_SQL, status_event_params(rows, source, raw_file_hash))


def build_summary(fixture: Path, rows: Sequence[DemoSeedRow], source: str, raw_file_hash: str) -> SeedSummary:
    return SeedSummary(
        fixture=fixture,
        source=source,
        raw_file_hash=raw_file_hash,
        station_count=len(rows),
        connector_count=len(rows),
        status_event_count=len(rows),
    )


def seed_fixture(fixture: Path, database_url: str, source: str = DEFAULT_SOURCE) -> SeedSummary:
    raw_file_hash = fixture_sha256(fixture)
    rows = build_seed_rows(load_feature_collection(fixture))
    seed_rows(database_url, rows, source, raw_file_hash)
    return build_summary(fixture, rows, source, raw_file_hash)


def _feature_coordinates(feature: dict[str, Any], index: int) -> tuple[float, float]:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError(f"feature at index {index}: geometry must be a Point")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValueError(f"feature at index {index}: coordinates must contain longitude and latitude")
    try:
        lon = float(coordinates[0])
        lat = float(coordinates[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"feature at index {index}: coordinates must be numbers") from exc
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError(f"feature at index {index}: coordinates must be finite")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"feature at index {index}: coordinates are outside EPSG:4326 bounds")
    return lon, lat


def _required_text(properties: dict[str, Any], field: str, index: int) -> str:
    value = properties.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"feature at index {index}: {field} is required")
    return value.strip()


def _positive_float(value: Any, field: str, index: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"feature at index {index}: {field} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"feature at index {index}: {field} must be positive")
    return parsed


def _aware_datetime(value: str, field: str, index: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"feature at index {index}: {field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"feature at index {index}: {field} must include timezone")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed synthetic ChargeFlow KR demo rows into PostGIS.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="synthetic GeoJSON fixture path")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Postgres connection URL")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="source label for status_events")
    parser.add_argument("--dry-run", action="store_true", help="parse fixture and print planned counts without DB writes")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    if not fixture.exists():
        parser.error(f"fixture not found: {fixture}")

    raw_file_hash = fixture_sha256(fixture)
    rows = build_seed_rows(load_feature_collection(fixture))
    summary = build_summary(fixture, rows, args.source, raw_file_hash)

    if not args.dry_run:
        if not args.database_url:
            parser.error("--database-url or DATABASE_URL is required unless --dry-run is used")
        seed_rows(args.database_url, rows, args.source, raw_file_hash)

    print(
        "seeded "
        f"{summary.station_count} stations, "
        f"{summary.connector_count} connectors, "
        f"{summary.status_event_count} status events "
        f"from {summary.fixture} ({summary.raw_file_hash})"
    )


if __name__ == "__main__":
    main()
