from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, status

from app.api.stations import MAX_LIMIT, STATION_SOURCE, load_db_station_features
from app.schemas.route_planner import RouteChargingPlanRequest, RouteChargingPlanResponse
from route_corridor import DEFAULT_CORRIDOR_WIDTH_KM
from route_planner_graph import build_route_planner_graph
from station_query import BBox, Feature

router = APIRouter(tags=["routes"])

ROUTE_PREFETCH_LIMIT = MAX_LIMIT
ROUTE_PREFETCH_PADDING_KM = 1.0
KM_PER_DEGREE_LAT = 111.32


@lru_cache(maxsize=1)
def compiled_route_planner_graph() -> Any:
    return build_route_planner_graph()


@router.post("/routes/charging-plan", response_model=RouteChargingPlanResponse)
def create_charging_plan(payload: RouteChargingPlanRequest) -> dict[str, Any]:
    try:
        graph_payload = payload.to_graph_payload()
        station_features = load_route_station_features(graph_payload)
        reference_time = reference_time_from_payload(graph_payload, station_features)
        result = compiled_route_planner_graph().invoke(
            {
                "request": graph_payload,
                "station_features": station_features,
                "reference_time": reference_time,
            }
        )
    except (psycopg.Error, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="station database query failed",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    errors = result.get("errors")
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    response = result.get("response")
    if not isinstance(response, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="route planner graph did not produce a response",
        )
    return response


def load_route_station_features(payload: Mapping[str, Any]) -> list[Feature]:
    try:
        bbox = route_bbox_from_payload(payload)
    except ValueError:
        return []

    return with_route_planner_metadata(load_db_station_features(bbox, ROUTE_PREFETCH_LIMIT))


def route_bbox_from_payload(payload: Mapping[str, Any]) -> BBox:
    route = payload.get("route")
    if not isinstance(route, Mapping):
        raise ValueError("request.route is required")

    polyline = route.get("polyline")
    if not isinstance(polyline, list) or len(polyline) < 2:
        raise ValueError("route.polyline must contain at least two points")

    coordinates = [_route_coordinate(point, index) for index, point in enumerate(polyline)]
    padding_km = route_corridor_width_from_payload(payload) + ROUTE_PREFETCH_PADDING_KM
    lons = [point[0] for point in coordinates]
    lats = [point[1] for point in coordinates]
    min_lat = max(-90.0, min(lats) - padding_km / KM_PER_DEGREE_LAT)
    max_lat = min(90.0, max(lats) + padding_km / KM_PER_DEGREE_LAT)
    reference_lat = max(0.000001, math.cos(math.radians((min(lats) + max(lats)) / 2)))
    lon_padding = padding_km / (KM_PER_DEGREE_LAT * reference_lat)

    return (
        max(-180.0, min(lons) - lon_padding),
        min_lat,
        min(180.0, max(lons) + lon_padding),
        max_lat,
    )


def route_corridor_width_from_payload(payload: Mapping[str, Any]) -> float:
    constraints = payload.get("constraints")
    if not isinstance(constraints, Mapping):
        return DEFAULT_CORRIDOR_WIDTH_KM

    value = constraints.get("corridor_width_km")
    if value is None:
        return DEFAULT_CORRIDOR_WIDTH_KM

    try:
        corridor_width_km = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("constraints.corridor_width_km must be a number") from exc
    if not math.isfinite(corridor_width_km) or corridor_width_km < 0:
        raise ValueError("constraints.corridor_width_km must be non-negative")
    return corridor_width_km


def with_route_planner_metadata(features: list[Feature]) -> list[Feature]:
    enriched: list[Feature] = []
    for feature in features:
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            enriched.append(feature)
            continue
        updated_properties = dict(properties)
        updated_properties.setdefault("source", STATION_SOURCE)
        status_updated_at = updated_properties.get("status_updated_at")
        if isinstance(status_updated_at, str) and len(status_updated_at) >= 10:
            updated_properties.setdefault("snapshot_date", status_updated_at[:10])
        enriched.append({**feature, "properties": updated_properties})
    return enriched


def _route_coordinate(point: object, index: int) -> tuple[float, float]:
    if not isinstance(point, list | tuple) or len(point) != 2:
        raise ValueError(f"route.polyline[{index}] must be [lon, lat]")
    try:
        lon = float(point[0])
        lat = float(point[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"route.polyline[{index}] must contain numbers") from exc
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError(f"route.polyline[{index}] must contain finite numbers")
    if not -180 <= lon <= 180:
        raise ValueError(f"route.polyline[{index}][0] must be between -180 and 180")
    if not -90 <= lat <= 90:
        raise ValueError(f"route.polyline[{index}][1] must be between -90 and 90")
    return lon, lat


def reference_time_from_payload(payload: object, station_features: list[Feature]) -> object:
    if isinstance(payload, Mapping):
        requested_reference_time = payload.get("reference_time")
        if requested_reference_time is not None:
            return requested_reference_time.strip() if isinstance(requested_reference_time, str) else requested_reference_time

    if not station_features:
        return datetime.now(timezone.utc).isoformat()

    return latest_station_status_time(station_features)


def latest_station_status_time(station_features: list[Feature]) -> str:
    observed_times: list[datetime] = []
    for feature in station_features:
        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            continue
        status_updated_at = properties.get("status_updated_at")
        if not isinstance(status_updated_at, str) or not status_updated_at.strip():
            continue
        observed_at = datetime.fromisoformat(status_updated_at.strip())
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("station status_updated_at must include timezone")
        observed_times.append(observed_at.astimezone(timezone.utc))

    if not observed_times:
        raise ValueError("station features must include status_updated_at")
    return max(observed_times).isoformat()
