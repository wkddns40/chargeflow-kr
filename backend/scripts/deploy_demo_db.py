"""Apply the demo schema and seed the synthetic station snapshot."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from seed_demo_db import DEFAULT_FIXTURE, DEFAULT_SOURCE, seed_fixture
from seed_places import build_places_from_sources, seed_places

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = BACKEND_ROOT / "app" / "db" / "schema.sql"


def apply_schema(database_url: str, schema: Path) -> None:
    import psycopg

    sql = schema.read_text(encoding="utf-8")
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the ChargeFlow KR synthetic snapshot demo database.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Postgres connection URL")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema SQL path")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="synthetic GeoJSON fixture path")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="source label for status_events")
    parser.add_argument("--skip-schema", action="store_true", help="skip schema application")
    parser.add_argument("--skip-seed", action="store_true", help="skip synthetic snapshot seed")
    parser.add_argument("--skip-place-seed", action="store_true", help="skip place resolver seed")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.skip_schema and args.skip_seed and args.skip_place_seed:
        parser.error("at least one of schema application or seed must run")
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    schema = args.schema.resolve()
    fixture = args.fixture.resolve()

    if not args.skip_schema:
        if not schema.exists():
            parser.error(f"schema not found: {schema}")
        apply_schema(args.database_url, schema)
        print(f"applied schema from {schema}")

    if not args.skip_seed:
        if not fixture.exists():
            parser.error(f"fixture not found: {fixture}")
        summary = seed_fixture(fixture, args.database_url, args.source)
        print(
            "seeded "
            f"{summary.station_count} stations, "
            f"{summary.connector_count} connectors, "
            f"{summary.status_event_count} status events "
            f"from {summary.fixture} ({summary.raw_file_hash})"
        )

    if not args.skip_place_seed:
        place_summary = seed_places(args.database_url, build_places_from_sources())
        print(
            "seeded "
            f"{place_summary.place_count} places, "
            f"{place_summary.alias_count} aliases "
            f"({place_summary.station_count} stations, {place_summary.region_count} regions)"
        )


if __name__ == "__main__":
    main()
