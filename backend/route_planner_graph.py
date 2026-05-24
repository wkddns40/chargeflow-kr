"""Serializable route planner graph state for Phase 6D."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any, Literal, NotRequired, TypedDict

from route_corridor import DEFAULT_CORRIDOR_WIDTH_KM
from vehicle_profile import VehicleProfile, VehicleProfileError


GraphNodeName = Literal[
    "validate_route_request",
    "validate_vehicle_profile",
    "build_route_corridor",
    "find_station_candidates",
    "estimate_soc",
    "rank_charging_stops",
    "build_response",
]
FeaturePayload = dict[str, Any]
OptimizerPayload = dict[str, Any]
DEFAULT_ROUTE_ID = "route-request"


class RoutePayload(TypedDict):
    distance_km: float
    polyline: list[list[float]]
    id: NotRequired[str]


class VehicleProfilePayload(TypedDict):
    battery_kwh: float
    current_soc: float
    target_arrival_soc: float
    consumption_kwh_per_km: float
    preferred_connector_types: list[str]
    max_charging_kw: float


class RoutePlannerConstraintsPayload(TypedDict, total=False):
    corridor_width_km: float
    max_results: int


class RouteCorridorPayload(TypedDict):
    polyline: list[list[float]]
    corridor_width_km: float


class RoutePlannerRequestPayload(TypedDict):
    route: RoutePayload
    vehicle: VehicleProfilePayload
    constraints: NotRequired[RoutePlannerConstraintsPayload]


class RoutePlannerErrorPayload(TypedDict):
    node: GraphNodeName
    message: str
    code: NotRequired[str]


class RoutePlannerGraphState(TypedDict, total=False):
    request: RoutePlannerRequestPayload
    route_id: str
    route_distance_km: float
    route_polyline: list[list[float]]
    route_corridor: RouteCorridorPayload
    vehicle: VehicleProfilePayload
    constraints: RoutePlannerConstraintsPayload
    station_features: list[FeaturePayload]
    candidate_features: list[FeaturePayload]
    stop_candidates: list[OptimizerPayload]
    optimizer_input: OptimizerPayload
    optimizer_response: OptimizerPayload
    response: OptimizerPayload
    errors: list[RoutePlannerErrorPayload]


ROUTE_PLANNER_STATE_KEYS: tuple[str, ...] = (
    "request",
    "route_id",
    "route_distance_km",
    "route_polyline",
    "route_corridor",
    "vehicle",
    "constraints",
    "station_features",
    "candidate_features",
    "stop_candidates",
    "optimizer_input",
    "optimizer_response",
    "response",
    "errors",
)


def empty_route_planner_state() -> RoutePlannerGraphState:
    return {"errors": []}


def validate_route_request(state: RoutePlannerGraphState) -> RoutePlannerGraphState:
    errors = list(state.get("errors", []))
    request = state.get("request")
    if not isinstance(request, Mapping):
        return {"errors": [*errors, _route_request_error("request is required", "missing_request")]}

    route = request.get("route")
    if not isinstance(route, Mapping):
        return {"errors": [*errors, _route_request_error("request.route is required", "missing_route")]}

    try:
        route_id = _normalize_route_id(route.get("id"))
        route_distance_km = _validate_positive_number(route.get("distance_km"), "route.distance_km")
        route_polyline = _normalize_route_polyline(route.get("polyline"))
    except ValueError as exc:
        return {"errors": [*errors, _route_request_error(str(exc), "invalid_route")]}

    return {
        "route_id": route_id,
        "route_distance_km": route_distance_km,
        "route_polyline": route_polyline,
        "errors": errors,
    }


def validate_vehicle_profile(state: RoutePlannerGraphState) -> RoutePlannerGraphState:
    errors = list(state.get("errors", []))
    request = state.get("request")
    if not isinstance(request, Mapping):
        return {"errors": [*errors, _vehicle_profile_error("request is required", "missing_request")]}

    vehicle_payload = request.get("vehicle")
    if not isinstance(vehicle_payload, Mapping):
        return {"errors": [*errors, _vehicle_profile_error("request.vehicle is required", "missing_vehicle")]}

    try:
        vehicle = VehicleProfile(
            battery_kwh=vehicle_payload["battery_kwh"],
            current_soc=vehicle_payload["current_soc"],
            target_arrival_soc=vehicle_payload["target_arrival_soc"],
            consumption_kwh_per_km=vehicle_payload["consumption_kwh_per_km"],
            preferred_connector_types=vehicle_payload["preferred_connector_types"],
            max_charging_kw=vehicle_payload["max_charging_kw"],
        )
    except (KeyError, TypeError, VehicleProfileError) as exc:
        return {"errors": [*errors, _vehicle_profile_error(str(exc), "invalid_vehicle")]}

    return {"vehicle": vehicle.to_dict(), "errors": errors}


def build_route_corridor(state: RoutePlannerGraphState) -> RoutePlannerGraphState:
    errors = list(state.get("errors", []))
    try:
        if "route_polyline" not in state:
            raise ValueError("route_polyline is required")
        route_polyline = _normalize_route_polyline(state.get("route_polyline"))
        corridor_width_km = _route_corridor_width_from_state(state)
    except ValueError as exc:
        return {"errors": [*errors, _route_corridor_error(str(exc), "invalid_corridor")]}

    return {
        "constraints": {"corridor_width_km": corridor_width_km},
        "route_corridor": {
            "polyline": route_polyline,
            "corridor_width_km": corridor_width_km,
        },
        "errors": errors,
    }


def _route_request_error(message: str, code: str) -> RoutePlannerErrorPayload:
    return {"node": "validate_route_request", "message": message, "code": code}


def _vehicle_profile_error(message: str, code: str) -> RoutePlannerErrorPayload:
    return {"node": "validate_vehicle_profile", "message": message, "code": code}


def _route_corridor_error(message: str, code: str) -> RoutePlannerErrorPayload:
    return {"node": "build_route_corridor", "message": message, "code": code}


def _normalize_route_id(value: object) -> str:
    if value is None:
        return DEFAULT_ROUTE_ID
    if not isinstance(value, str):
        raise ValueError("route.id must be a string")
    normalized = value.strip()
    return normalized or DEFAULT_ROUTE_ID


def _validate_positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _validate_non_negative_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be non-negative")
    return number


def _route_corridor_width_from_state(state: RoutePlannerGraphState) -> float:
    request = state.get("request")
    if not isinstance(request, Mapping):
        return DEFAULT_CORRIDOR_WIDTH_KM

    constraints = request.get("constraints")
    if constraints is None:
        return DEFAULT_CORRIDOR_WIDTH_KM
    if not isinstance(constraints, Mapping):
        raise ValueError("request.constraints must be an object")

    return _validate_non_negative_number(
        constraints.get("corridor_width_km", DEFAULT_CORRIDOR_WIDTH_KM),
        "constraints.corridor_width_km",
    )


def _normalize_route_polyline(value: object) -> list[list[float]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("route.polyline must be a coordinate list")
    if len(value) < 2:
        raise ValueError("route.polyline must contain at least two points")

    return [_normalize_route_coordinate(point, index) for index, point in enumerate(value)]


def _normalize_route_coordinate(value: object, index: int) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise ValueError(f"route.polyline[{index}] must be [lon, lat]")

    lon = _validate_coordinate_number(value[0], f"route.polyline[{index}][0]")
    lat = _validate_coordinate_number(value[1], f"route.polyline[{index}][1]")
    if not -180 <= lon <= 180:
        raise ValueError(f"route.polyline[{index}][0] must be between -180 and 180")
    if not -90 <= lat <= 90:
        raise ValueError(f"route.polyline[{index}][1] must be between -90 and 90")
    return [lon, lat]


def _validate_coordinate_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number
