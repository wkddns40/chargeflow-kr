from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import search
from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def feature(
    feature_id: str,
    lon: float,
    lat: float,
    *,
    status: str = "available",
    connector_type: str = "DC Combo",
    max_kw: int = 150,
) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "charger_id": feature_id,
            "charger_name": f"Test Charger {feature_id}",
            "operator": "Test Operator",
            "connector_type": connector_type,
            "max_kw": max_kw,
            "address": "Test Address",
            "status": status,
            "status_updated_at": "2026-05-19T08:00:00+09:00",
        },
    }


def command(**overrides) -> dict:
    payload = {
        "intent": "find_chargers",
        "place": "Gangnam Station",
        "radius_m": 1000,
        "filters": {
            "min_kw": 100,
            "status": "available",
            "connector_type": "DC",
        },
        "sort": "distance",
    }
    payload.update(overrides)
    return payload


def test_search_chargers_returns_filtered_results(monkeypatch) -> None:
    monkeypatch.setattr(
        search,
        "load_station_features",
        lambda: [
            feature("near-match", 127.0277, 37.4980),
            feature("wrong-status", 127.0278, 37.4981, status="occupied"),
            feature("wrong-power", 127.0279, 37.4982, max_kw=50),
            feature("wrong-connector", 127.0280, 37.4983, connector_type="AC Type 2"),
            feature("far-away", 127.0900, 37.5600),
        ],
    )

    response = client().post("/api/search/chargers", json=command())

    assert response.status_code == 200
    payload = response.json()
    assert [item["properties"]["charger_id"] for item in payload["features"]] == ["near-match"]
    assert payload["query"]["place"] == "Gangnam Station"
    assert payload["query"]["place_location"]["place_id"] == "gangnam-station"
    assert payload["explanation"]["data_freshness"] == "file-snapshot"
    assert payload["explanation"]["applied_filters"] == [
        "radius_m=1000",
        "sort=distance",
        "min_kw=100",
        "status=available",
        "connector_type=DC",
    ]
    assert payload["features"][0]["properties"]["distance_m"] < 50


def test_search_chargers_rejects_invalid_command() -> None:
    response = client().post("/api/search/chargers", json=command(intent="plan_route"))

    assert response.status_code == 400
    assert "unsupported intent" in response.json()["detail"]


def test_search_chargers_rejects_unknown_place() -> None:
    response = client().post("/api/search/chargers", json=command(place="Busan Station"))

    assert response.status_code == 400
    assert "unknown place" in response.json()["detail"]


def test_search_chargers_applies_radius_after_bbox_prefilter(monkeypatch) -> None:
    monkeypatch.setattr(
        search,
        "load_station_features",
        lambda: [
            feature("near", 127.0277, 37.4980),
            feature("inside-bbox-outside-radius", 127.0356, 37.5059),
            feature("outside-bbox", 127.0900, 37.5600),
        ],
    )

    response = client().post(
        "/api/search/chargers",
        json=command(filters={}, radius_m=1000),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["properties"]["charger_id"] for item in payload["features"]] == ["near"]
    assert payload["query"]["bbox"]["west"] < 127.0276 < payload["query"]["bbox"]["east"]
    assert payload["query"]["bbox"]["south"] < 37.4979 < payload["query"]["bbox"]["north"]
