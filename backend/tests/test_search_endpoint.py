from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import search
from app.main import create_app
from station_query import contains_coordinate


class TestSettings:
    openai_api_key = ""
    openai_model = "gpt-4o-mini"
    openai_parse_timeout_seconds = 8.0


@pytest.fixture(autouse=True)
def disable_openai_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "get_settings", lambda: TestSettings())


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
    def fake_loader(bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        assert contains_coordinate(bbox, 127.0276, 37.4979)
        assert limit == search.SEARCH_PREFILTER_LIMIT
        return [
            feature("near-match", 127.0277, 37.4980),
            feature("wrong-status", 127.0278, 37.4981, status="occupied"),
            feature("wrong-power", 127.0279, 37.4982, max_kw=50),
            feature("wrong-connector", 127.0280, 37.4983, connector_type="AC Type 2"),
            feature("far-away", 127.0900, 37.5600),
        ]

    monkeypatch.setattr(search, "load_db_station_features", fake_loader)

    response = client().post("/api/search/chargers", json=command())

    assert response.status_code == 200
    payload = response.json()
    assert [item["properties"]["charger_id"] for item in payload["features"]] == ["near-match"]
    assert payload["query"]["place"] == "Gangnam Station"
    assert payload["query"]["place_location"]["place_id"] == "gangnam-station"
    assert payload["explanation"]["data_freshness"] == "synthetic-snapshot"
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
    def fake_loader(bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        assert contains_coordinate(bbox, 127.0276, 37.4979)
        assert limit == search.SEARCH_PREFILTER_LIMIT
        return [
            feature("near", 127.0277, 37.4980),
            feature("inside-bbox-outside-radius", 127.0356, 37.5059),
            feature("outside-bbox", 127.0900, 37.5600),
        ]

    monkeypatch.setattr(search, "load_db_station_features", fake_loader)

    response = client().post(
        "/api/search/chargers",
        json=command(filters={}, radius_m=1000),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["properties"]["charger_id"] for item in payload["features"]] == ["near"]
    assert payload["query"]["bbox"]["west"] < 127.0276 < payload["query"]["bbox"]["east"]
    assert payload["query"]["bbox"]["south"] < 37.4979 < payload["query"]["bbox"]["north"]


def test_search_chargers_reports_database_errors_without_secrets(monkeypatch) -> None:
    def broken_loader(*args: object) -> list[dict]:
        raise RuntimeError("could not connect with password=secret")

    monkeypatch.setattr(search, "load_db_station_features", broken_loader)

    response = client().post("/api/search/chargers", json=command())

    assert response.status_code == 500
    assert response.json()["detail"] == "station database query failed"


def test_natural_language_search_returns_parsed_results(monkeypatch) -> None:
    def fake_loader(bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        assert contains_coordinate(bbox, 127.0276, 37.4979)
        assert limit == search.SEARCH_PREFILTER_LIMIT
        return [
            feature("near-match", 127.0277, 37.4980),
            feature("wrong-connector", 127.0278, 37.4981, connector_type="AC Type 2"),
        ]

    monkeypatch.setattr(search, "load_db_station_features", fake_loader)

    response = client().post("/api/search/chargers/nl", json={"message": "Gangnam Station nearby 2km fast chargers"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "search_results"
    assert payload["input"]["parser"] == "deterministic-v1"
    assert payload["input"]["command"] == {
        "intent": "find_chargers",
        "place": "Gangnam Station",
        "radius_m": 2000,
        "filters": {"connector_type": "DC"},
        "sort": "distance",
    }
    assert [item["properties"]["charger_id"] for item in payload["features"]] == ["near-match"]


def test_natural_language_search_requires_place() -> None:
    response = client().post("/api/search/chargers/nl", json={"message": "nearby fast chargers"})

    assert response.status_code == 200
    assert response.json() == {
        "type": "clarification_required",
        "message": "Search needs a place. Try: Gangnam Station nearby chargers.",
        "missing_fields": ["place"],
    }


def test_natural_language_search_rejects_unsupported_intent() -> None:
    response = client().post("/api/search/chargers/nl", json={"message": "reserve a charger near Gangnam Station"})

    assert response.status_code == 400
    assert "unsupported intent: reserve_charger" in response.json()["detail"]


def test_natural_language_search_rejects_control_text() -> None:
    response = client().post("/api/search/chargers/nl", json={"message": "Gangnam Station drop table stations"})

    assert response.status_code == 400
    assert "unsupported control text" in response.json()["detail"]


def test_natural_language_search_validates_parsed_command(monkeypatch) -> None:
    calls: list[dict] = []
    real_validator = search.validate_search_command

    def spy_validator(payload: dict) -> object:
        calls.append(payload)
        return real_validator(payload)

    monkeypatch.setattr(search, "validate_search_command", spy_validator)
    monkeypatch.setattr(search, "load_db_station_features", lambda bbox, limit: [])

    response = client().post("/api/search/chargers/nl", json={"message": "Jeju Airport 100kW or higher"})

    assert response.status_code == 200
    assert calls == [
        {
            "intent": "find_chargers",
            "place": "Jeju Airport",
            "radius_m": 2000,
            "filters": {"min_kw": 100},
            "sort": "power",
        }
    ]


def test_natural_language_search_reports_database_errors_without_secrets(monkeypatch) -> None:
    def broken_loader(*args: object) -> list[dict]:
        raise ValueError("could not parse row with password=secret")

    monkeypatch.setattr(search, "load_db_station_features", broken_loader)

    response = client().post("/api/search/chargers/nl", json={"message": "Gangnam Station nearby chargers"})

    assert response.status_code == 500
    assert response.json()["detail"] == "station database query failed"
