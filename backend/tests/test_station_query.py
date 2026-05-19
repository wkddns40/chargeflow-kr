from __future__ import annotations

import json

import pytest

from station_query import (
    DEFAULT_LIMIT,
    filter_by_bbox,
    load_feature_collection,
    normalize_limit,
    parse_bbox,
)


def feature(feature_id: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"charger_id": feature_id},
    }


def test_parse_bbox_accepts_valid_values() -> None:
    assert parse_bbox("126,33,128,38") == (126.0, 33.0, 128.0, 38.0)
    assert parse_bbox(" 126.5, 33.1, 128.9, 38.2 ") == (126.5, 33.1, 128.9, 38.2)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "126,33,128",
        "126,33,128,38,39",
        "126,abc,128,38",
        "nan,33,128,38",
        "181,33,128,38",
        "126,-91,128,38",
        "128,33,126,38",
        "126,38,128,33",
    ],
)
def test_parse_bbox_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="bbox"):
        parse_bbox(value)


def test_load_feature_collection_reads_geojson_fixture(tmp_path) -> None:
    fixture_path = tmp_path / "stations.geojson"
    fixture_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature("inside", 127.0, 37.0)]}),
        encoding="utf-8",
    )

    assert load_feature_collection(fixture_path)[0]["properties"]["charger_id"] == "inside"


def test_filter_by_bbox_excludes_outside_and_includes_boundary() -> None:
    features = [
        feature("outside-west", 125.9, 37.0),
        feature("inside", 127.0, 37.0),
        feature("min-boundary", 126.0, 33.0),
        feature("max-boundary", 128.0, 38.0),
        feature("outside-north", 127.0, 38.1),
    ]

    results = filter_by_bbox(features, parse_bbox("126,33,128,38"))

    assert [item["properties"]["charger_id"] for item in results] == [
        "inside",
        "min-boundary",
        "max-boundary",
    ]


def test_filter_by_bbox_applies_explicit_limit() -> None:
    features = [feature(str(index), 127.0, 37.0) for index in range(5)]

    assert len(filter_by_bbox(features, parse_bbox("126,33,128,38"), limit=3)) == 3


def test_filter_by_bbox_uses_default_limit() -> None:
    features = [feature(str(index), 127.0, 37.0) for index in range(DEFAULT_LIMIT + 1)]

    assert len(filter_by_bbox(features, parse_bbox("126,33,128,38"), limit=None)) == DEFAULT_LIMIT


@pytest.mark.parametrize("limit", [0, -1, True])
def test_normalize_limit_rejects_invalid_values(limit: int | bool) -> None:
    with pytest.raises(ValueError, match="limit"):
        normalize_limit(limit)
