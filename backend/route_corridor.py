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
    return _segment_projection(point, start, end)[0]


def distance_to_route_km(point: RouteCoordinate, polyline: RoutePolyline) -> float:
    _validate_polyline(polyline)
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
    route_total_distance_km: float | None = None,
) -> list[Feature]:
    _validate_corridor_width(corridor_width_km)
    _validate_polyline(polyline)
    if route_total_distance_km is not None:
        _validate_route_total_distance(route_total_distance_km)
    candidates: list[Feature] = []

    for feature in features:
        coordinate = extract_coordinates(feature)
        distance_from_route_km = distance_to_route_km(coordinate, polyline)
        if distance_from_route_km <= corridor_width_km:
            route_distance_km = (
                route_distance_at_point_km(coordinate, polyline, route_total_distance_km)
                if route_total_distance_km is not None
                else None
            )
            candidates.append(_with_route_metrics(feature, distance_from_route_km, route_distance_km))

    return candidates


def route_distance_at_point_km(
    point: RouteCoordinate,
    polyline: RoutePolyline,
    route_total_distance_km: float,
) -> float:
    _validate_coordinate(point, "point")
    _validate_polyline(polyline)
    _validate_route_total_distance(route_total_distance_km)

    best_distance_from_route_km = math.inf
    best_geometry_progress_km = 0.0
    geometry_progress_km = 0.0

    for segment_start, segment_end in zip(polyline, polyline[1:]):
        distance_from_segment_km, projection_ratio, _ = _segment_projection(
            point,
            segment_start,
            segment_end,
        )
        segment_length_km = _segment_length_km(segment_start, segment_end)
        candidate_progress_km = geometry_progress_km + segment_length_km * projection_ratio
        if distance_from_segment_km < best_distance_from_route_km:
            best_distance_from_route_km = distance_from_segment_km
            best_geometry_progress_km = candidate_progress_km
        geometry_progress_km += segment_length_km

    if geometry_progress_km == 0:
        return 0.0
    return route_total_distance_km * best_geometry_progress_km / geometry_progress_km


def _project_to_km(coordinate: RouteCoordinate, reference_lat: float) -> ProjectedPoint:
    lon, lat = coordinate
    return (
        math.radians(lon) * EARTH_RADIUS_KM * math.cos(math.radians(reference_lat)),
        math.radians(lat) * EARTH_RADIUS_KM,
    )


def _distance_km(left: ProjectedPoint, right: ProjectedPoint) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _segment_length_km(start: RouteCoordinate, end: RouteCoordinate) -> float:
    _validate_coordinate(start, "start")
    _validate_coordinate(end, "end")

    reference_lat = (start[1] + end[1]) / 2
    projected_start = _project_to_km(start, reference_lat)
    projected_end = _project_to_km(end, reference_lat)
    return _distance_km(projected_start, projected_end)


def _segment_projection(
    point: RouteCoordinate,
    start: RouteCoordinate,
    end: RouteCoordinate,
) -> tuple[float, float, float]:
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
    segment_length_km = math.sqrt(segment_length_sq)
    if segment_length_sq == 0:
        return _distance_km(projected_point, projected_start), 0.0, 0.0

    point_x = projected_point[0] - projected_start[0]
    point_y = projected_point[1] - projected_start[1]
    projection = (point_x * segment_x + point_y * segment_y) / segment_length_sq
    clamped_projection = max(0.0, min(1.0, projection))
    closest = (
        projected_start[0] + clamped_projection * segment_x,
        projected_start[1] + clamped_projection * segment_y,
    )
    return _distance_km(projected_point, closest), clamped_projection, segment_length_km


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


def _validate_route_total_distance(route_total_distance_km: float) -> None:
    if not math.isfinite(route_total_distance_km) or route_total_distance_km <= 0:
        raise ValueError("route_total_distance_km must be a finite positive number")


def _validate_polyline(polyline: RoutePolyline) -> None:
    if len(polyline) < MIN_ROUTE_POLYLINE_POINTS:
        raise ValueError("route polyline must contain at least two points")


def _with_route_metrics(
    feature: Feature,
    distance_from_route_km: float,
    route_distance_km: float | None,
) -> Feature:
    candidate = dict(feature)
    properties = candidate.get("properties")
    updated_properties = {
        **(properties if isinstance(properties, dict) else {}),
        "distance_from_route_km": distance_from_route_km,
    }
    if route_distance_km is not None and "route_distance_km" not in updated_properties:
        updated_properties["route_distance_km"] = route_distance_km
    candidate["properties"] = {
        **updated_properties,
    }
    return candidate
