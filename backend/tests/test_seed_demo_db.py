from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_demo_db.py"
SPEC = importlib.util.spec_from_file_location("seed_demo_db", SCRIPT_PATH)
assert SPEC is not None
seed_demo_db = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = seed_demo_db
SPEC.loader.exec_module(seed_demo_db)


def charger_feature(
    *,
    charger_id: str = "CFL-SYN-00001",
    address: str = "Seoul Gangnam-gu Teheran-ro 123",
    connector_type: str = "DC Combo",
    status: str = "available",
    status_updated_at: str = "2026-05-19T08:00:00+09:00",
    max_kw: object = 150,
    lon: float = 127.0276,
    lat: float = 37.4979,
) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "charger_id": charger_id,
            "charger_name": "Gangnam Demo Charger",
            "operator": "ChargeFlow KR",
            "connector_type": connector_type,
            "max_kw": max_kw,
            "address": address,
            "status": status,
            "status_updated_at": status_updated_at,
        },
    }


def test_fixture_sha256_uses_stable_prefix(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.geojson"
    fixture.write_text("abc", encoding="utf-8")

    assert seed_demo_db.fixture_sha256(fixture) == (
        "sha256:"
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_build_seed_rows_maps_synthetic_feature_to_db_rows() -> None:
    rows = seed_demo_db.build_seed_rows([charger_feature()])

    assert len(rows) == 1
    row = rows[0]
    assert row.station_id == "CFL-SYN-00001"
    assert row.connector_id == "CFL-SYN-00001-01"
    assert row.name == "Gangnam Demo Charger"
    assert row.operator == "ChargeFlow KR"
    assert row.address == "Seoul Gangnam-gu Teheran-ro 123"
    assert row.region_code == "KR-11"
    assert row.current_type == "DC"
    assert row.max_kw == 150.0
    assert row.status == "available"
    assert row.observed_at.utcoffset() is not None


@pytest.mark.parametrize(
    ("address", "region_code"),
    [
        ("Seoul Gangnam-gu Teheran-ro 123", "KR-11"),
        ("Busan Haeundae-gu Marine City 1", "KR-26"),
        ("Daegu Suseong-gu Dalgubeol-daero 1", "KR-27"),
        ("Incheon Yeonsu-gu Songdo-dong 1", "KR-28"),
        ("Gwangju Seo-gu Sangmujungang-ro 1", "KR-29"),
        ("Daejeon Yuseong-gu Expo-ro 1", "KR-30"),
        ("Ulsan Nam-gu Samsan-ro 1", "KR-31"),
        ("Sejong-si Government Complex 1", "KR-36"),
        ("Gyeonggi-do Suwon-si Paldal-gu 1", "KR-41"),
        ("Jeju-si Airport-ro 1", "KR-50"),
        ("Seogwipo-si Jungang-ro 1", "KR-50"),
    ],
)
def test_region_code_is_derived_from_address_prefix(address: str, region_code: str) -> None:
    row = seed_demo_db.build_seed_rows([charger_feature(address=address)])[0]

    assert row.region_code == region_code


def test_status_event_params_are_idempotency_safe() -> None:
    row = seed_demo_db.build_seed_rows([charger_feature()])[0]
    params = seed_demo_db.status_event_params(
        [row],
        "synthetic-stations-7k",
        "sha256:abc",
    )

    assert "WHERE NOT EXISTS" in seed_demo_db.STATUS_EVENT_INSERT_SQL
    assert params == [
        (
            row.connector_id,
            row.status,
            "synthetic-stations-7k",
            row.observed_at,
            "sha256:abc",
            row.connector_id,
            row.status,
            "synthetic-stations-7k",
            row.observed_at,
            "sha256:abc",
        )
    ]


@pytest.mark.parametrize(
    ("feature", "message"),
    [
        (charger_feature(status="busy"), "unsupported status"),
        (
            charger_feature(status_updated_at="2026-05-19T08:00:00"),
            "must include timezone",
        ),
        (
            {
                **charger_feature(),
                "geometry": {"type": "LineString", "coordinates": [[127.0, 37.0]]},
            },
            "geometry must be a Point",
        ),
        (charger_feature(max_kw=-1), "max_kw must be positive"),
    ],
)
def test_build_seed_rows_rejects_invalid_features(feature: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        seed_demo_db.build_seed_rows([feature])


def test_load_feature_collection_rejects_non_feature_collection(tmp_path: Path) -> None:
    fixture = tmp_path / "not-feature-collection.geojson"
    fixture.write_text('{"type": "Feature"}', encoding="utf-8")

    with pytest.raises(ValueError, match="FeatureCollection"):
        seed_demo_db.load_feature_collection(fixture)


def test_committed_synthetic_fixture_has_expected_count() -> None:
    features = seed_demo_db.load_feature_collection(seed_demo_db.DEFAULT_FIXTURE)

    assert len(features) == 7000
