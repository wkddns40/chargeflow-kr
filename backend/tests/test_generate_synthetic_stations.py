from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_synthetic_stations.py"
SPEC = importlib.util.spec_from_file_location("generate_synthetic_stations", SCRIPT_PATH)
assert SPEC is not None
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def test_region_allocation_matches_7k_target() -> None:
    assert generator.allocate_region_counts(7000) == {
        "seoul_metro": 3500,
        "other_metro": 2450,
        "jeju": 1050,
    }


def test_generated_features_match_charger_shape() -> None:
    collection = generator.generate_collection(count=12, seed=7)

    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 12

    expected_properties = {
        "charger_id",
        "charger_name",
        "operator",
        "connector_type",
        "max_kw",
        "address",
        "status",
        "status_updated_at",
    }

    for feature in collection["features"]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        lon, lat = feature["geometry"]["coordinates"]
        assert generator.SOUTH_KOREA_BOUNDS["west"] <= lon <= generator.SOUTH_KOREA_BOUNDS["east"]
        assert generator.SOUTH_KOREA_BOUNDS["south"] <= lat <= generator.SOUTH_KOREA_BOUNDS["north"]
        assert set(feature["properties"]) == expected_properties
        assert feature["properties"]["status"] in generator.STATUS_VALUES


def test_sample_chargers_path_is_protected() -> None:
    with pytest.raises(ValueError, match="sample-chargers"):
        generator.validate_output_path(generator.PROTECTED_SAMPLE)
