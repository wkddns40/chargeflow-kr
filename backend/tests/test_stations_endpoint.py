from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import stations
from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_stations_endpoint_filters_bbox_and_limit() -> None:
    response = client().get("/api/stations", params={"bbox": "126,33,128,38", "limit": 50})

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) <= 50
    assert payload["meta"] == {
        "count": len(payload["features"]),
        "limit": 50,
        "source": "synthetic-stations-7k",
    }

    for feature in payload["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        assert 126 <= lon <= 128
        assert 33 <= lat <= 38


def test_stations_endpoint_uses_default_limit() -> None:
    response = client().get("/api/stations", params={"bbox": "124.5,33,131.9,38.7"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["limit"] == 2000
    assert payload["meta"]["count"] == 2000
    assert len(payload["features"]) == 2000


def test_stations_endpoint_rejects_missing_bbox() -> None:
    response = client().get("/api/stations")

    assert response.status_code == 400
    assert "bbox is required" in response.json()["detail"]


def test_stations_endpoint_rejects_invalid_bbox() -> None:
    response = client().get("/api/stations", params={"bbox": "126,abc,128,38"})

    assert response.status_code == 400
    assert "bbox values must be numbers" in response.json()["detail"]


def test_station_fixture_missing_error_is_clear(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.geojson"

    with pytest.raises(FileNotFoundError, match="Synthetic station fixture not found"):
        stations.load_station_features(str(missing_path))
