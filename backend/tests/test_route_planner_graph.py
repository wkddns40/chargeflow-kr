from __future__ import annotations

import json

from route_planner_graph import (
    ROUTE_PLANNER_STATE_KEYS,
    RoutePlannerGraphState,
    build_route_corridor,
    empty_route_planner_state,
    find_station_candidates,
    validate_route_request,
    validate_vehicle_profile,
)


def test_empty_route_planner_state_is_json_serializable() -> None:
    state = empty_route_planner_state()

    assert json.loads(json.dumps(state)) == {"errors": []}


def station_feature(station_id: str, lon: float, lat: float) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"station_id": station_id},
    }


def test_route_planner_graph_state_uses_json_safe_payloads() -> None:
    state: RoutePlannerGraphState = {
        "request": {
            "route": {
                "id": "fixture-seoul-daejeon",
                "distance_km": 165.2,
                "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
            },
            "vehicle": {
                "battery_kwh": 77.4,
                "current_soc": 0.64,
                "target_arrival_soc": 0.15,
                "consumption_kwh_per_km": 0.18,
                "preferred_connector_types": ["DC Combo"],
                "max_charging_kw": 180.0,
            },
            "constraints": {"corridor_width_km": 3.0, "max_results": 5},
        },
        "route_id": "fixture-seoul-daejeon",
        "route_distance_km": 165.2,
        "route_polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
        "route_corridor": {
            "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
            "corridor_width_km": 3.0,
        },
        "vehicle": {
            "battery_kwh": 77.4,
            "current_soc": 0.64,
            "target_arrival_soc": 0.15,
            "consumption_kwh_per_km": 0.18,
            "preferred_connector_types": ["DC Combo"],
            "max_charging_kw": 180.0,
        },
        "constraints": {"corridor_width_km": 3.0, "max_results": 5},
        "station_features": [],
        "candidate_features": [],
        "stop_candidates": [],
        "optimizer_input": {"route_id": "fixture-seoul-daejeon"},
        "optimizer_response": {
            "route_id": "fixture-seoul-daejeon",
            "recommendations": [{"station_id": "CFL-SYN-00001", "reasons": ["reachable"]}],
        },
        "response": {"route_id": "fixture-seoul-daejeon", "recommendations": []},
        "errors": [],
    }

    encoded = json.loads(json.dumps(state))

    assert tuple(encoded.keys()) == ROUTE_PLANNER_STATE_KEYS
    assert encoded["route_polyline"][0] == [126.978, 37.5665]
    assert encoded["optimizer_response"]["recommendations"][0]["reasons"] == ["reachable"]


def test_validate_route_request_normalizes_route_fields() -> None:
    update = validate_route_request(
        {
            "request": {
                "route": {
                    "id": " fixture-seoul-daejeon ",
                    "distance_km": 165.2,
                    "polyline": ((126.978, 37.5665), (127.3845, 36.3504)),
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update == {
        "route_id": "fixture-seoul-daejeon",
        "route_distance_km": 165.2,
        "route_polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
        "errors": [],
    }
    assert json.loads(json.dumps(update)) == update


def test_validate_route_request_defaults_missing_route_id() -> None:
    update = validate_route_request(
        {
            "request": {
                "route": {
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update["route_id"] == "route-request"
    assert update["errors"] == []


def test_validate_route_request_reports_missing_route() -> None:
    update = validate_route_request({"errors": [{"node": "build_response", "message": "prior", "code": "prior"}]})

    assert update == {
        "errors": [
            {"node": "build_response", "message": "prior", "code": "prior"},
            {
                "node": "validate_route_request",
                "message": "request is required",
                "code": "missing_request",
            },
        ]
    }


def test_validate_route_request_reports_invalid_polyline() -> None:
    update = validate_route_request(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update == {
        "errors": [
            {
                "node": "validate_route_request",
                "message": "route.polyline must contain at least two points",
                "code": "invalid_route",
            }
        ]
    }


def test_validate_vehicle_profile_normalizes_vehicle_fields() -> None:
    update = validate_vehicle_profile(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": (" DC Combo ", "CHAdeMO"),
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update == {
        "vehicle": {
            "battery_kwh": 77.4,
            "current_soc": 0.64,
            "target_arrival_soc": 0.15,
            "consumption_kwh_per_km": 0.18,
            "preferred_connector_types": ["DC Combo", "CHAdeMO"],
            "max_charging_kw": 180.0,
        },
        "errors": [],
    }
    assert json.loads(json.dumps(update)) == update


def test_validate_vehicle_profile_reports_missing_vehicle() -> None:
    update = validate_vehicle_profile(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                }
            },
            "errors": [{"node": "validate_route_request", "message": "prior", "code": "prior"}],
        }
    )

    assert update == {
        "errors": [
            {"node": "validate_route_request", "message": "prior", "code": "prior"},
            {
                "node": "validate_vehicle_profile",
                "message": "request.vehicle is required",
                "code": "missing_vehicle",
            },
        ]
    }


def test_validate_vehicle_profile_reports_invalid_soc() -> None:
    update = validate_vehicle_profile(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 1.2,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update == {
        "errors": [
            {
                "node": "validate_vehicle_profile",
                "message": "current_soc must be between 0.0 and 1.0",
                "code": "invalid_vehicle",
            }
        ]
    }


def test_validate_vehicle_profile_reports_unsupported_connector() -> None:
    update = validate_vehicle_profile(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["NACS"],
                    "max_charging_kw": 180.0,
                },
            }
        }
    )

    assert update == {
        "errors": [
            {
                "node": "validate_vehicle_profile",
                "message": "unsupported preferred_connector_types: NACS",
                "code": "invalid_vehicle",
            }
        ]
    }


def test_build_route_corridor_uses_default_width() -> None:
    update = build_route_corridor(
        {
            "route_polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
        }
    )

    assert update == {
        "constraints": {"corridor_width_km": 3.0},
        "route_corridor": {
            "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
            "corridor_width_km": 3.0,
        },
        "errors": [],
    }
    assert json.loads(json.dumps(update)) == update


def test_build_route_corridor_uses_request_constraint_width() -> None:
    update = build_route_corridor(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
                "constraints": {"corridor_width_km": 2.5, "max_results": 5},
            },
            "route_polyline": ((126.978, 37.5665), (127.3845, 36.3504)),
        }
    )

    assert update["constraints"] == {"corridor_width_km": 2.5}
    assert update["route_corridor"] == {
        "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
        "corridor_width_km": 2.5,
    }
    assert update["errors"] == []


def test_build_route_corridor_reports_missing_route_polyline() -> None:
    update = build_route_corridor(
        {"errors": [{"node": "validate_route_request", "message": "prior", "code": "prior"}]}
    )

    assert update == {
        "errors": [
            {"node": "validate_route_request", "message": "prior", "code": "prior"},
            {
                "node": "build_route_corridor",
                "message": "route_polyline is required",
                "code": "invalid_corridor",
            },
        ]
    }


def test_build_route_corridor_reports_invalid_corridor_width() -> None:
    update = build_route_corridor(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": {
                    "battery_kwh": 77.4,
                    "current_soc": 0.64,
                    "target_arrival_soc": 0.15,
                    "consumption_kwh_per_km": 0.18,
                    "preferred_connector_types": ["DC Combo"],
                    "max_charging_kw": 180.0,
                },
                "constraints": {"corridor_width_km": -1.0},
            },
            "route_polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
        }
    )

    assert update == {
        "errors": [
            {
                "node": "build_route_corridor",
                "message": "constraints.corridor_width_km must be non-negative",
                "code": "invalid_corridor",
            }
        ]
    }


def test_find_station_candidates_filters_features_by_corridor() -> None:
    inside = station_feature("CFL-SYN-00001", 0.0, 0.5)
    outside = station_feature("CFL-SYN-00002", 1.0, 0.5)

    update = find_station_candidates(
        {
            "route_corridor": {
                "polyline": [[0.0, 0.0], [0.0, 1.0]],
                "corridor_width_km": 2.0,
            },
            "station_features": [outside, inside],
        }
    )

    assert [feature["properties"]["station_id"] for feature in update["candidate_features"]] == ["CFL-SYN-00001"]
    assert update["candidate_features"][0]["properties"]["distance_from_route_km"] == 0.0
    assert "distance_from_route_km" not in inside["properties"]
    assert update["errors"] == []
    assert json.loads(json.dumps(update)) == update


def test_find_station_candidates_reports_missing_corridor() -> None:
    update = find_station_candidates(
        {
            "station_features": [station_feature("CFL-SYN-00001", 0.0, 0.5)],
            "errors": [{"node": "build_route_corridor", "message": "prior", "code": "prior"}],
        }
    )

    assert update == {
        "errors": [
            {"node": "build_route_corridor", "message": "prior", "code": "prior"},
            {
                "node": "find_station_candidates",
                "message": "route_corridor is required",
                "code": "invalid_station_candidates",
            },
        ]
    }


def test_find_station_candidates_reports_missing_station_features() -> None:
    update = find_station_candidates(
        {
            "route_corridor": {
                "polyline": [[0.0, 0.0], [0.0, 1.0]],
                "corridor_width_km": 2.0,
            }
        }
    )

    assert update == {
        "errors": [
            {
                "node": "find_station_candidates",
                "message": "station_features is required",
                "code": "invalid_station_candidates",
            }
        ]
    }


def test_find_station_candidates_reports_invalid_station_geometry() -> None:
    update = find_station_candidates(
        {
            "route_corridor": {
                "polyline": [[0.0, 0.0], [0.0, 1.0]],
                "corridor_width_km": 2.0,
            },
            "station_features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0.0, 0.5], [0.0, 0.6]]},
                    "properties": {"station_id": "CFL-SYN-00001"},
                }
            ],
        }
    )

    assert update == {
        "errors": [
            {
                "node": "find_station_candidates",
                "message": "GeoJSON feature geometry must be a Point",
                "code": "invalid_station_candidates",
            }
        ]
    }
