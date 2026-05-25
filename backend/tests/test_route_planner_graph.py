from __future__ import annotations

import json

import pytest

from route_planner_graph import (
    ROUTE_PLANNER_STATE_KEYS,
    RoutePlannerGraphState,
    build_response,
    build_route_corridor,
    empty_route_planner_state,
    estimate_soc,
    find_station_candidates,
    rank_charging_stops,
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


def optimizer_candidate_feature(
    station_id: str,
    route_distance_km: float,
    *,
    max_kw: float = 150.0,
    distance_from_route_km: float = 0.8,
    connector_type: str = "DC Combo",
    status: str = "available",
    status_updated_at: str | None = None,
    use_charger_aliases: bool = False,
) -> dict[str, object]:
    identity = (
        {"charger_id": station_id, "charger_name": f"{station_id} Alias Charger"}
        if use_charger_aliases
        else {"station_id": station_id, "name": f"{station_id} Charger"}
    )
    properties: dict[str, object] = {
        **identity,
        "connector_type": connector_type,
        "max_kw": max_kw,
        "distance_from_route_km": distance_from_route_km,
        "route_distance_km": route_distance_km,
        "status": status,
    }
    if status_updated_at is not None:
        properties["status_updated_at"] = status_updated_at

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [127.03, 37.5]},
        "properties": properties,
    }


def graph_vehicle_payload() -> dict[str, object]:
    return {
        "battery_kwh": 77.4,
        "current_soc": 0.64,
        "target_arrival_soc": 0.15,
        "consumption_kwh_per_km": 0.18,
        "preferred_connector_types": ["DC Combo"],
        "max_charging_kw": 180.0,
    }


def optimizer_response_payload() -> dict[str, object]:
    return {
        "route_id": "fixture-seoul-daejeon",
        "summary": {
            "distance_km": 165.2,
            "estimated_energy_kwh": 29.736,
            "start_soc": 0.64,
            "target_arrival_soc": 0.15,
            "minimum_required_soc": 0.5341860465116279,
            "reachable_without_stop": True,
        },
        "recommendations": [
            {
                "station_id": "CFL-SYN-00001",
                "name": "CFL-SYN-00001 Charger",
                "connector_type": "DC Combo",
                "max_kw": 180.0,
                "distance_from_route_km": 0.5,
                "route_distance_km": 42.5,
                "estimated_arrival_soc": 0.5411627906976744,
                "score": 0.91,
                "reasons": ["connector_match", "reachable", "high_power", "fresh_availability", "short_detour"],
            }
        ],
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
        "route_summary": {
            "distance_km": 165.2,
            "estimated_energy_kwh": 29.736,
            "start_soc": 0.64,
            "target_arrival_soc": 0.15,
            "minimum_required_soc": 0.5341860465116279,
            "reachable_without_stop": True,
        },
        "constraints": {"corridor_width_km": 3.0, "max_results": 5},
        "reference_time": "2026-05-24T00:00:00+00:00",
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


def test_estimate_soc_builds_route_summary_from_helper_math() -> None:
    update = estimate_soc(
        {
            "route_distance_km": 165.2,
            "vehicle": {
                "battery_kwh": 77.4,
                "current_soc": 0.64,
                "target_arrival_soc": 0.15,
                "consumption_kwh_per_km": 0.18,
                "preferred_connector_types": ["DC Combo"],
                "max_charging_kw": 180.0,
            },
        }
    )

    assert update["route_summary"] == {
        "distance_km": 165.2,
        "estimated_energy_kwh": pytest.approx(29.736),
        "start_soc": 0.64,
        "target_arrival_soc": 0.15,
        "minimum_required_soc": pytest.approx(0.5341860465116279),
        "reachable_without_stop": True,
    }
    assert update["errors"] == []
    assert json.loads(json.dumps(update)) == update


def test_estimate_soc_marks_unreachable_route() -> None:
    update = estimate_soc(
        {
            "route_distance_km": 300.0,
            "vehicle": {
                "battery_kwh": 77.4,
                "current_soc": 0.64,
                "target_arrival_soc": 0.15,
                "consumption_kwh_per_km": 0.18,
                "preferred_connector_types": ["DC Combo"],
                "max_charging_kw": 180.0,
            },
        }
    )

    assert update["route_summary"]["reachable_without_stop"] is False
    assert update["route_summary"]["minimum_required_soc"] > 0.64
    assert update["errors"] == []


def test_estimate_soc_reports_missing_vehicle() -> None:
    update = estimate_soc(
        {
            "route_distance_km": 165.2,
            "errors": [{"node": "validate_vehicle_profile", "message": "prior", "code": "prior"}],
        }
    )

    assert update == {
        "errors": [
            {"node": "validate_vehicle_profile", "message": "prior", "code": "prior"},
            {
                "node": "estimate_soc",
                "message": "vehicle is required",
                "code": "invalid_soc_estimate",
            },
        ]
    }


def test_estimate_soc_reports_invalid_route_distance() -> None:
    update = estimate_soc(
        {
            "route_distance_km": 0.0,
            "vehicle": {
                "battery_kwh": 77.4,
                "current_soc": 0.64,
                "target_arrival_soc": 0.15,
                "consumption_kwh_per_km": 0.18,
                "preferred_connector_types": ["DC Combo"],
                "max_charging_kw": 180.0,
            },
        }
    )

    assert update == {
        "errors": [
            {
                "node": "estimate_soc",
                "message": "route_distance_km must be positive",
                "code": "invalid_soc_estimate",
            }
        ]
    }


def test_rank_charging_stops_builds_optimizer_payload_and_response() -> None:
    update = rank_charging_stops(
        {
            "request": {
                "route": {
                    "id": "fixture-seoul-daejeon",
                    "distance_km": 165.2,
                    "polyline": [[126.978, 37.5665], [127.3845, 36.3504]],
                },
                "vehicle": graph_vehicle_payload(),
                "constraints": {"max_results": 1},
            },
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "candidate_features": [
                optimizer_candidate_feature(
                    "CFL-SYN-00002",
                    40.0,
                    max_kw=50.0,
                    distance_from_route_km=0.5,
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
                optimizer_candidate_feature(
                    "CFL-SYN-00001",
                    42.5,
                    max_kw=180.0,
                    distance_from_route_km=0.5,
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
            ],
            "reference_time": "2026-05-24T00:00:00+00:00",
        }
    )

    assert [candidate["station_id"] for candidate in update["stop_candidates"]] == [
        "CFL-SYN-00002",
        "CFL-SYN-00001",
    ]
    assert update["optimizer_input"]["max_results"] == 1
    assert [item["station_id"] for item in update["optimizer_response"]["recommendations"]] == [
        "CFL-SYN-00001"
    ]
    assert update["optimizer_response"]["summary"]["estimated_energy_kwh"] == pytest.approx(29.736)
    assert update["errors"] == []
    assert json.loads(json.dumps(update)) == update


def test_rank_charging_stops_accepts_station_property_aliases() -> None:
    update = rank_charging_stops(
        {
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "candidate_features": [
                optimizer_candidate_feature(
                    "CFL-SYN-00001",
                    42.5,
                    use_charger_aliases=True,
                )
            ],
            "reference_time": "2026-05-24T00:00:00+00:00",
        }
    )

    assert update["stop_candidates"][0]["station_id"] == "CFL-SYN-00001"
    assert update["stop_candidates"][0]["name"] == "CFL-SYN-00001 Alias Charger"
    assert update["optimizer_response"]["recommendations"][0]["station_id"] == "CFL-SYN-00001"
    assert update["errors"] == []


def test_rank_charging_stops_reports_missing_reference_time() -> None:
    update = rank_charging_stops(
        {
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "candidate_features": [optimizer_candidate_feature("CFL-SYN-00001", 42.5)],
            "errors": [{"node": "estimate_soc", "message": "prior", "code": "prior"}],
        }
    )

    assert update == {
        "errors": [
            {"node": "estimate_soc", "message": "prior", "code": "prior"},
            {
                "node": "rank_charging_stops",
                "message": "reference_time is required",
                "code": "invalid_stop_ranking",
            },
        ]
    }


def test_rank_charging_stops_reports_missing_candidate_features() -> None:
    update = rank_charging_stops(
        {
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "reference_time": "2026-05-24T00:00:00+00:00",
        }
    )

    assert update == {
        "errors": [
            {
                "node": "rank_charging_stops",
                "message": "candidate_features is required",
                "code": "invalid_stop_ranking",
            }
        ]
    }


def test_rank_charging_stops_reports_invalid_candidate_route_distance() -> None:
    candidate = optimizer_candidate_feature("CFL-SYN-00001", 42.5)
    properties = candidate["properties"]
    assert isinstance(properties, dict)
    del properties["route_distance_km"]

    update = rank_charging_stops(
        {
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "candidate_features": [candidate],
            "reference_time": "2026-05-24T00:00:00+00:00",
        }
    )

    assert update == {
        "errors": [
            {
                "node": "rank_charging_stops",
                "message": "candidate_features[0].properties.route_distance_km must be a number",
                "code": "invalid_stop_ranking",
            }
        ]
    }


def test_rank_charging_stops_reports_naive_reference_time() -> None:
    update = rank_charging_stops(
        {
            "route_id": "fixture-seoul-daejeon",
            "route_distance_km": 165.2,
            "vehicle": graph_vehicle_payload(),
            "candidate_features": [optimizer_candidate_feature("CFL-SYN-00001", 42.5)],
            "reference_time": "2026-05-24T00:00:00",
        }
    )

    assert update == {
        "errors": [
            {
                "node": "rank_charging_stops",
                "message": "reference_time must include timezone",
                "code": "invalid_stop_ranking",
            }
        ]
    }


def test_build_response_wraps_optimizer_response_with_meta() -> None:
    update = build_response(
        {
            "optimizer_response": optimizer_response_payload(),
            "candidate_features": [
                optimizer_candidate_feature(
                    "CFL-SYN-00001",
                    42.5,
                    status_updated_at="2026-05-23T00:00:00+00:00",
                )
            ],
        }
    )

    assert update["response"]["route_id"] == "fixture-seoul-daejeon"
    assert update["response"]["summary"] == optimizer_response_payload()["summary"]
    assert update["response"]["recommendations"] == optimizer_response_payload()["recommendations"]
    assert update["response"]["meta"] == {
        "source": "local-dataset",
        "freshness_label": "fresh",
        "limitations": [
            "Route geometry is provided input, not generated by an external route API.",
            "No live traffic or weather is used.",
            "Availability and reliability use imported snapshot data, not live polling or historical uptime.",
            "Fallback recommendations may include unreachable or offline chargers and must be labeled clearly.",
        ],
    }
    assert update["errors"] == []
    assert json.loads(json.dumps(update)) == update


def test_build_response_preserves_candidate_source_metadata() -> None:
    candidate = optimizer_candidate_feature("CFL-SYN-00001", 42.5)
    properties = candidate["properties"]
    assert isinstance(properties, dict)
    properties["source"] = "synthetic-status-file-sample"
    properties["snapshot_date"] = "2026-05-19"

    update = build_response(
        {
            "optimizer_response": optimizer_response_payload(),
            "candidate_features": [candidate],
        }
    )

    assert update["response"]["meta"]["source"] == "synthetic-status-file-sample"
    assert update["response"]["meta"]["snapshot_date"] == "2026-05-19"
    assert update["errors"] == []


def test_build_response_reports_missing_optimizer_response() -> None:
    update = build_response({"errors": [{"node": "rank_charging_stops", "message": "prior", "code": "prior"}]})

    assert update == {
        "errors": [
            {"node": "rank_charging_stops", "message": "prior", "code": "prior"},
            {
                "node": "build_response",
                "message": "optimizer_response is required",
                "code": "invalid_response",
            },
        ]
    }


def test_build_response_reports_invalid_recommendation_payload() -> None:
    optimizer_response = optimizer_response_payload()
    optimizer_response["recommendations"] = ["not-a-recommendation"]

    update = build_response({"optimizer_response": optimizer_response})

    assert update == {
        "errors": [
            {
                "node": "build_response",
                "message": "optimizer_response.recommendations[0] must be an object",
                "code": "invalid_response",
            }
        ]
    }
