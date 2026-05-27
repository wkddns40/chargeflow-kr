from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
SCRIPT_PATH = SCRIPTS_DIR / "deploy_demo_db.py"
SPEC = importlib.util.spec_from_file_location("deploy_demo_db", SCRIPT_PATH)
assert SPEC is not None
deploy_demo_db = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = deploy_demo_db
SPEC.loader.exec_module(deploy_demo_db)


def test_main_applies_schema_and_seeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    schema = tmp_path / "schema.sql"
    fixture = tmp_path / "stations.geojson"
    schema.write_text("SELECT 1;", encoding="utf-8")
    fixture.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    calls: list[tuple[str, object]] = []

    def fake_apply_schema(database_url: str, schema_path: Path) -> None:
        calls.append(("schema", database_url, schema_path))

    def fake_seed_fixture(fixture_path: Path, database_url: str, source: str) -> SimpleNamespace:
        calls.append(("seed", fixture_path, database_url, source))
        return SimpleNamespace(
            station_count=1,
            connector_count=1,
            status_event_count=1,
            fixture=fixture_path,
            raw_file_hash="sha256:test",
        )

    def fake_seed_places(database_url: str, places: object) -> SimpleNamespace:
        calls.append(("place-seed", database_url, places))
        return SimpleNamespace(place_count=1, alias_count=2, station_count=1, region_count=0)

    monkeypatch.setattr(deploy_demo_db, "apply_schema", fake_apply_schema)
    monkeypatch.setattr(deploy_demo_db, "seed_fixture", fake_seed_fixture)
    monkeypatch.setattr(deploy_demo_db, "build_places_from_sources", lambda: ["place"])
    monkeypatch.setattr(deploy_demo_db, "seed_places", fake_seed_places)

    deploy_demo_db.main(
        [
            "--database-url",
            "postgresql://example",
            "--schema",
            str(schema),
            "--fixture",
            str(fixture),
            "--source",
            "synthetic-test",
        ]
    )

    assert calls == [
        ("schema", "postgresql://example", schema.resolve()),
        ("seed", fixture.resolve(), "postgresql://example", "synthetic-test"),
        ("place-seed", "postgresql://example", ["place"]),
    ]


def test_main_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit):
        deploy_demo_db.main(["--skip-schema"])
