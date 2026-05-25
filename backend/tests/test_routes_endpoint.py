from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import create_app
from app.schemas.route_planner import RouteChargingPlanRequest, RouteChargingPlanResponse


def client() -> TestClient:
    return TestClient(create_app())


def station_feature(
    station_id: str,
    lon: float,
    lat: float,
    *,
    connector_type: str = "DC Combo",
    max_kw: float = 180.0,
    status: str = "available",
) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "charger_id": station_id,
            "charger_name": f"Route Test Charger {station_id}",
            "operator": "Route Test Operator",
            "connector_type": connector_type,
            "max_kw": max_kw,
            "address": "Route Test Address",
            "status": status,
            "status_updated_at": "2026-05-23T00:00:00+00:00",
            "source": "synthetic-status-file-sample",
            "snapshot_date": "2026-05-19",
        },
    }


def route_request(**overrides) -> dict:
    payload = {
        "route": {
            "id": "fixture-seoul-daejeon",
            "distance_km": 165.2,
            "polyline": [[0.0, 0.0], [0.0, 1.0]],
        },
        "vehicle": {
            "battery_kwh": 77.4,
            "current_soc": 0.64,
            "target_arrival_soc": 0.15,
            "consumption_kwh_per_km": 0.18,
            "preferred_connector_types": ["DC Combo"],
            "max_charging_kw": 180.0,
        },
        "constraints": {"corridor_width_km": 2.0, "max_results": 2},
        "reference_time": "2026-05-24T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_charging_plan_endpoint_returns_graph_response(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "load_station_features",
        lambda: [
            station_feature("CFL-SYN-00002", 0.0, 0.58, max_kw=50.0),
            station_feature("CFL-SYN-00001", 0.0, 0.43),
            station_feature("outside", 1.0, 0.43),
        ],
    )

    response = client().post("/api/routes/charging-plan", json=route_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["route_id"] == "fixture-seoul-daejeon"
    assert [item["station_id"] for item in payload["recommendations"]] == ["CFL-SYN-00001", "CFL-SYN-00002"]
    assert payload["recommendations"][0]["route_distance_km"] == pytest.approx(71.036)
    assert payload["recommendations"][0]["distance_from_route_km"] == pytest.approx(0.0)
    assert payload["meta"]["source"] == "synthetic-status-file-sample"
    assert payload["meta"]["snapshot_date"] == "2026-05-19"
    assert payload["meta"]["freshness_label"] == "fresh"
    assert RouteChargingPlanResponse.model_validate(payload).route_id == "fixture-seoul-daejeon"


def test_charging_plan_endpoint_derives_reference_time_from_station_status(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "load_station_features",
        lambda: [station_feature("CFL-SYN-00001", 0.0, 0.43)],
    )
    payload = route_request()
    del payload["reference_time"]

    response = client().post("/api/routes/charging-plan", json=payload)

    assert response.status_code == 200
    assert response.json()["recommendations"][0]["station_id"] == "CFL-SYN-00001"


def test_charging_plan_endpoint_returns_graph_errors_as_bad_request(monkeypatch) -> None:
    monkeypatch.setattr(routes, "load_station_features", lambda: [station_feature("CFL-SYN-00001", 0.0, 0.43)])

    response = client().post("/api/routes/charging-plan", json=route_request(route={"polyline": [[0.0, 0.0]]}))

    assert response.status_code == 400
    assert response.json()["detail"][0]["node"] == "validate_route_request"


def test_charging_plan_endpoint_keeps_request_errors_in_graph(monkeypatch) -> None:
    monkeypatch.setattr(routes, "load_station_features", lambda: [station_feature("CFL-SYN-00001", 0.0, 0.43)])

    response = client().post("/api/routes/charging-plan", json={"vehicle": route_request()["vehicle"]})

    assert response.status_code == 400
    assert response.json()["detail"][0] == {
        "node": "validate_route_request",
        "message": "request.route is required",
        "code": "missing_route",
    }
    assert RouteChargingPlanRequest.model_validate({"route": "not-a-route"}).route == "not-a-route"


def test_charging_plan_endpoint_reports_station_fixture_errors(monkeypatch) -> None:
    def raise_missing_fixture() -> list[dict]:
        raise FileNotFoundError("Synthetic station fixture not found: missing.geojson")

    monkeypatch.setattr(routes, "load_station_features", raise_missing_fixture)

    response = client().post("/api/routes/charging-plan", json=route_request())

    assert response.status_code == 500
    assert "Synthetic station fixture not found" in response.json()["detail"]


def test_charging_plan_endpoint_openapi_uses_response_schema() -> None:
    response = client().get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    operation = payload["paths"]["/api/routes/charging-plan"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RouteChargingPlanRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RouteChargingPlanResponse"
    }
    assert "RouteChargingPlanRequest" in payload["components"]["schemas"]
    assert "RouteChargingPlanResponse" in payload["components"]["schemas"]
    assert "RoutePlannerRecommendation" in payload["components"]["schemas"]
