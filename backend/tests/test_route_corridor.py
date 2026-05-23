from __future__ import annotations

import pytest

from route_corridor import (
    DEFAULT_CORRIDOR_WIDTH_KM,
    RoutePolyline,
    distance_to_route_km,
    filter_candidates_by_route_corridor,
    is_within_route_corridor,
)


ROUTE: RoutePolyline = (
    (126.9780, 37.5665),
    (127.0276, 37.4979),
    (127.3845, 36.3504),
)
DISTANCE_ASSERTION_TOLERANCE_KM = 1e-9


def feature(feature_id: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"charger_id": feature_id},
    }


@pytest.mark.parametrize("point", ROUTE)
def test_route_polyline_points_are_inside_corridor(point: tuple[float, float]) -> None:
    assert distance_to_route_km(point, ROUTE) == pytest.approx(0.0, abs=DISTANCE_ASSERTION_TOLERANCE_KM)
    assert is_within_route_corridor(point, ROUTE)


def test_nearby_station_is_inside_default_corridor() -> None:
    point = (127.03, 37.50)

    distance_from_route_km = distance_to_route_km(point, ROUTE)

    assert 0 < distance_from_route_km < DEFAULT_CORRIDOR_WIDTH_KM
    assert is_within_route_corridor(point, ROUTE)


def test_filter_candidates_by_route_corridor_includes_inside_station() -> None:
    station = feature("inside-gangnam", 127.03, 37.50)

    results = filter_candidates_by_route_corridor([station], ROUTE)

    assert [item["properties"]["charger_id"] for item in results] == ["inside-gangnam"]
    assert 0 < results[0]["properties"]["distance_from_route_km"] < DEFAULT_CORRIDOR_WIDTH_KM
    assert "distance_from_route_km" not in station["properties"]


def test_far_station_is_outside_default_corridor() -> None:
    point = (128.0, 37.5)

    distance_from_route_km = distance_to_route_km(point, ROUTE)

    assert distance_from_route_km > DEFAULT_CORRIDOR_WIDTH_KM
    assert not is_within_route_corridor(point, ROUTE)


def test_filter_candidates_by_route_corridor_excludes_outside_station() -> None:
    station = feature("outside-east", 128.0, 37.5)

    assert filter_candidates_by_route_corridor([station], ROUTE) == []
    assert "distance_from_route_km" not in station["properties"]


def test_corridor_boundary_is_inclusive() -> None:
    point = (127.03, 37.50)
    boundary_width_km = distance_to_route_km(point, ROUTE)

    assert boundary_width_km > 0
    assert is_within_route_corridor(point, ROUTE, corridor_width_km=boundary_width_km)


def test_filter_candidates_by_route_corridor_includes_boundary_station() -> None:
    station = feature("boundary-gangnam", 127.03, 37.50)
    boundary_width_km = distance_to_route_km((127.03, 37.50), ROUTE)

    results = filter_candidates_by_route_corridor([station], ROUTE, corridor_width_km=boundary_width_km)

    assert [item["properties"]["charger_id"] for item in results] == ["boundary-gangnam"]
    assert results[0]["properties"]["distance_from_route_km"] == pytest.approx(
        boundary_width_km,
        abs=DISTANCE_ASSERTION_TOLERANCE_KM,
    )


@pytest.mark.parametrize("polyline", [(), ((126.9780, 37.5665),)])
def test_distance_to_route_rejects_empty_or_single_point_route(polyline: RoutePolyline) -> None:
    with pytest.raises(ValueError, match="at least two points"):
        distance_to_route_km((127.0, 37.5), polyline)


def test_filter_candidates_by_route_corridor_rejects_empty_route_even_without_station_input() -> None:
    with pytest.raises(ValueError, match="at least two points"):
        filter_candidates_by_route_corridor([], ())


def test_filter_candidates_by_route_corridor_returns_empty_for_empty_station_input() -> None:
    assert filter_candidates_by_route_corridor([], ROUTE) == []
