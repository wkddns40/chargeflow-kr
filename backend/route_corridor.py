"""Route corridor fixture shape for Phase 6D planning."""

from __future__ import annotations

import math
from typing import TypeAlias, TypedDict

from station_query import Feature, extract_coordinates


RouteCoordinate: TypeAlias = tuple[float, float]
RoutePolyline: TypeAlias = tuple[RouteCoordinate, ...]
ProjectedPoint: TypeAlias = tuple[float, float]

MIN_ROUTE_POLYLINE_POINTS = 2
DEFAULT_CORRIDOR_WIDTH_KM = 3.0
EARTH_RADIUS_KM = 6371.0088
ROUTE_POLYLINE_FIXTURE_FIELDS = ("id", "distance_km", "polyline")


class RoutePolylineFixture(TypedDict):
    id: str
    distance_km: float
    polyline: list[list[float]]


def distance_to_segment_km(point: RouteCoordinate, start: RouteCoordinate, end: RouteCoordinate) -> float:
    """Return approximate shortest distance from a lon/lat point to a lon/lat segment."""
    _validate_coordinate(point, "point")
    _validate_coordinate(start, "start")
    _validate_coordinate(end, "end")

    reference_lat = (point[1] + start[1] + end[1]) / 3
    projected_point = _project_to_km(point, reference_lat)
    projected_start = _project_to_km(start, reference_lat)
    projected_end = _project_to_km(end, reference_lat)

    segment_x = projected_end[0] - projected_start[0]
    segment_y = projected_end[1] - projected_start[1]
    segment_length_sq = segment_x * segment_x + segment_y * segment_y
    if segment_length_sq == 0:
        return _distance_km(projected_point, projected_start)

    point_x = projected_point[0] - projected_start[0]
    point_y = projected_point[1] - projected_start[1]
    projection = (point_x * segment_x + point_y * segment_y) / segment_length_sq
    clamped_projection = max(0.0, min(1.0, projection))
    closest = (
        projected_start[0] + clamped_projection * segment_x,
        projected_start[1] + clamped_projection * segment_y,
    )
    return _distance_km(projected_point, closest)


def distance_to_route_km(point: RouteCoordinate, polyline: RoutePolyline) -> float:
    if len(polyline) < MIN_ROUTE_POLYLINE_POINTS:
        raise ValueError("route polyline must contain at least two points")
    return min(
        distance_to_segment_km(point, segment_start, segment_end)
        for segment_start, segment_end in zip(polyline, polyline[1:])
    )


def is_within_route_corridor(
    point: RouteCoordinate,
    polyline: RoutePolyline,
    corridor_width_km: float = DEFAULT_CORRIDOR_WIDTH_KM,
) -> bool:
    _validate_corridor_width(corridor_width_km)
    return distance_to_route_km(point, polyline) <= corridor_width_km


def filter_candidates_by_route_corridor(
    features: list[Feature],
    polyline: RoutePolyline,
    corridor_width_km: float = DEFAULT_CORRIDOR_WIDTH_KM,
) -> list[Feature]:
    _validate_corridor_width(corridor_width_km)
    candidates: list[Feature] = []

    for feature in features:
        coordinate = extract_coordinates(feature)
        distance_from_route_km = distance_to_route_km(coordinate, polyline)
        if distance_from_route_km <= corridor_width_km:
            candidates.append(_with_route_distance(feature, distance_from_route_km))

    return candidates


def _project_to_km(coordinate: RouteCoordinate, reference_lat: float) -> ProjectedPoint:
    lon, lat = coordinate
    return (
        math.radians(lon) * EARTH_RADIUS_KM * math.cos(math.radians(reference_lat)),
        math.radians(lat) * EARTH_RADIUS_KM,
    )


def _distance_km(left: ProjectedPoint, right: ProjectedPoint) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _validate_coordinate(coordinate: RouteCoordinate, field: str) -> None:
    lon, lat = coordinate
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError(f"{field} coordinate must contain finite lon/lat values")
    if not -180 <= lon <= 180:
        raise ValueError(f"{field} longitude must be between -180 and 180")
    if not -90 <= lat <= 90:
        raise ValueError(f"{field} latitude must be between -90 and 90")


def _validate_corridor_width(corridor_width_km: float) -> None:
    if not math.isfinite(corridor_width_km) or corridor_width_km < 0:
        raise ValueError("corridor_width_km must be a finite non-negative number")


def _with_route_distance(feature: Feature, distance_from_route_km: float) -> Feature:
    candidate = dict(feature)
    properties = candidate.get("properties")
    candidate["properties"] = {
        **(properties if isinstance(properties, dict) else {}),
        "distance_from_route_km": distance_from_route_km,
    }
    return candidate
