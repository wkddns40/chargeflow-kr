from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, status

from app.api.stations import MAX_LIMIT, STATION_SOURCE, load_db_station_features
from geocoding import UnknownPlaceError, lookup_place
from nl_search_parser import (
    ClarificationRequired,
    NaturalLanguageSearchError,
    ParsedNaturalLanguageSearch,
    parse_natural_language_search,
)
from search_schema import SearchCommand, SearchCommandError, validate_search_command
from station_query import BBox, Feature, contains_coordinate, extract_coordinates

router = APIRouter(tags=["search"])

EARTH_RADIUS_M = 6_371_000
METERS_PER_DEGREE_LAT = 111_320
MAX_SEARCH_RESULTS = 50
SEARCH_PREFILTER_LIMIT = MAX_LIMIT


@router.post("/search/chargers")
def search_chargers(payload: dict[str, Any]) -> dict:
    try:
        command = validate_search_command(payload)
        return execute_search(command)
    except (SearchCommandError, UnknownPlaceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="station database query failed",
        ) from exc


@router.post("/search/chargers/nl")
def search_chargers_nl(payload: dict[str, Any]) -> dict:
    try:
        parsed = parse_natural_language_search(payload)
        if isinstance(parsed, ClarificationRequired):
            return parsed.to_dict()

        command = validate_search_command(parsed.command)
        response = execute_search(command)
    except (NaturalLanguageSearchError, SearchCommandError, UnknownPlaceError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="station database query failed",
        ) from exc

    return {
        "type": "search_results",
        "input": natural_language_input_metadata(parsed, command),
        **response,
    }


def natural_language_input_metadata(parsed: ParsedNaturalLanguageSearch, command: SearchCommand) -> dict:
    return {
        "message": parsed.message,
        "parser": parsed.parser,
        "command": command.to_dict(),
    }


def execute_search(command: SearchCommand) -> dict:
    place = lookup_place(command.place)
    bbox = bbox_for_radius(place.lon, place.lat, command.radius_m)

    features = load_db_station_features(bbox, SEARCH_PREFILTER_LIMIT)
    matched = search_station_features(features, place.lon, place.lat, command, bbox)

    return {
        "query": {
            **command.to_dict(),
            "place_location": place.to_dict(),
            "bbox": {
                "west": bbox[0],
                "south": bbox[1],
                "east": bbox[2],
                "north": bbox[3],
            },
        },
        "features": matched[:MAX_SEARCH_RESULTS],
        "explanation": {
            "applied_filters": applied_filters(command),
            "data_freshness": "synthetic-snapshot",
            "source": STATION_SOURCE,
            "result_limit": MAX_SEARCH_RESULTS,
        },
    }


def search_station_features(
    features: list[Feature],
    center_lon: float,
    center_lat: float,
    command: SearchCommand,
    bbox: BBox | None = None,
) -> list[Feature]:
    search_bbox = bbox or bbox_for_radius(center_lon, center_lat, command.radius_m)
    results: list[Feature] = []

    for feature in features:
        lon, lat = extract_coordinates(feature)
        if not contains_coordinate(search_bbox, lon, lat):
            continue

        distance_m = haversine_m(center_lon, center_lat, lon, lat)
        if distance_m > command.radius_m:
            continue
        if not matches_filters(feature, command):
            continue

        result = deepcopy(feature)
        result.setdefault("properties", {})["distance_m"] = round(distance_m)
        results.append(result)

    return sort_features(results, command.sort)


def matches_filters(feature: Feature, command: SearchCommand) -> bool:
    properties = feature.get("properties", {})
    filters = command.filters

    if filters.status is not None and properties.get("status") != filters.status:
        return False
    if filters.connector_type is not None and not connector_matches(properties.get("connector_type"), filters.connector_type):
        return False
    if filters.min_kw is not None:
        try:
            max_kw = int(properties.get("max_kw"))
        except (TypeError, ValueError):
            return False
        if max_kw < filters.min_kw:
            return False

    return True


def connector_matches(value: Any, expected: str) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.casefold()
    if expected == "DC":
        return normalized.startswith("dc") or normalized == "chademo"
    if expected == "AC":
        return normalized.startswith("ac")
    return normalized == expected.casefold()


def sort_features(features: list[Feature], sort: str) -> list[Feature]:
    if sort == "power":
        return sorted(features, key=lambda feature: (-int(feature.get("properties", {}).get("max_kw", 0)), distance_m(feature)))
    if sort == "availability":
        return sorted(features, key=lambda feature: (availability_rank(feature), distance_m(feature)))
    return sorted(features, key=distance_m)


def availability_rank(feature: Feature) -> int:
    status_value = feature.get("properties", {}).get("status")
    ranks = {"available": 0, "occupied": 1, "unknown": 2, "offline": 3}
    return ranks.get(status_value, 4)


def distance_m(feature: Feature) -> int:
    return int(feature.get("properties", {}).get("distance_m", 0))


def applied_filters(command: SearchCommand) -> list[str]:
    filters = [f"radius_m={command.radius_m}", f"sort={command.sort}"]
    if command.filters.min_kw is not None:
        filters.append(f"min_kw={command.filters.min_kw}")
    if command.filters.status is not None:
        filters.append(f"status={command.filters.status}")
    if command.filters.connector_type is not None:
        filters.append(f"connector_type={command.filters.connector_type}")
    return filters


def bbox_for_radius(lon: float, lat: float, radius_m: int) -> BBox:
    lat_delta = radius_m / METERS_PER_DEGREE_LAT
    cos_lat = math.cos(math.radians(lat))
    lon_delta = 180 if abs(cos_lat) < 0.000001 else radius_m / (METERS_PER_DEGREE_LAT * cos_lat)

    return (
        max(-180.0, lon - lon_delta),
        max(-90.0, lat - lat_delta),
        min(180.0, lon + lon_delta),
        min(90.0, lat + lat_delta),
    )


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(value), math.sqrt(1 - value))
