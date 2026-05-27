from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import stations
from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def station_feature(feature_id: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "charger_id": feature_id,
            "charger_name": f"{feature_id} charger",
            "operator": "ChargeFlow KR",
            "connector_type": "DC Combo",
            "max_kw": 150.0,
            "address": "Seoul Gangnam-gu Teheran-ro 123",
            "status": "available",
            "status_updated_at": "2026-05-19T08:00:00+09:00",
        },
    }


def test_stations_endpoint_filters_bbox_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_loader(bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        assert bbox == (126.0, 33.0, 128.0, 38.0)
        assert limit == 50
        return [station_feature("inside", 127.0, 37.0)]

    monkeypatch.setattr(stations, "load_db_station_features", fake_loader)

    response = client().get("/api/stations", params={"bbox": "126,33,128,38", "limit": 50})

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    assert payload["meta"] == {
        "count": len(payload["features"]),
        "limit": 50,
        "source": "synthetic-stations-7k",
    }
    assert "db;dur=" in response.headers["server-timing"]

    for feature in payload["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        assert 126 <= lon <= 128
        assert 33 <= lat <= 38


def test_stations_endpoint_uses_default_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_loader(bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        assert bbox == (124.5, 33.0, 131.9, 38.7)
        assert limit == 2000
        return [station_feature("inside", 127.0, 37.0)]

    monkeypatch.setattr(stations, "load_db_station_features", fake_loader)

    response = client().get("/api/stations", params={"bbox": "124.5,33,131.9,38.7"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["limit"] == 2000
    assert payload["meta"]["count"] == 1
    assert len(payload["features"]) == 1


def test_stations_endpoint_rejects_missing_bbox(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_loader(*args: object) -> list[dict]:
        pytest.fail("database loader should not run for invalid requests")

    monkeypatch.setattr(stations, "load_db_station_features", fail_loader)

    response = client().get("/api/stations")

    assert response.status_code == 400
    assert "bbox is required" in response.json()["detail"]


def test_stations_endpoint_rejects_invalid_bbox(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_loader(*args: object) -> list[dict]:
        pytest.fail("database loader should not run for invalid requests")

    monkeypatch.setattr(stations, "load_db_station_features", fail_loader)

    response = client().get("/api/stations", params={"bbox": "126,abc,128,38"})

    assert response.status_code == 400
    assert "bbox values must be numbers" in response.json()["detail"]


def test_station_fixture_missing_error_is_clear(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.geojson"

    with pytest.raises(FileNotFoundError, match="Synthetic station fixture not found"):
        stations.load_station_features(str(missing_path))


def test_stations_endpoint_reports_database_errors_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_loader(*args: object) -> list[dict]:
        raise RuntimeError("could not connect with password=secret")

    monkeypatch.setattr(stations, "load_db_station_features", broken_loader)

    response = client().get("/api/stations", params={"bbox": "126,33,128,38"})

    assert response.status_code == 500
    assert response.json()["detail"] == "station database query failed"
