"""GeoJSON station query helpers for bbox-backed benchmark APIs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

BBox = tuple[float, float, float, float]
Feature = dict[str, Any]

DEFAULT_LIMIT = 2000


def parse_bbox(value: str) -> BBox:
    """Parse bbox=minLon,minLat,maxLon,maxLat into a validated tuple."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("bbox is required as minLon,minLat,maxLon,maxLat")

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must contain 4 comma-separated values")

    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in parts)
    except ValueError as exc:
        raise ValueError("bbox values must be numbers") from exc

    bbox = (min_lon, min_lat, max_lon, max_lat)
    if not all(math.isfinite(value) for value in bbox):
        raise ValueError("bbox values must be finite numbers")
    if not -180 <= min_lon <= 180 or not -180 <= max_lon <= 180:
        raise ValueError("bbox longitude values must be between -180 and 180")
    if not -90 <= min_lat <= 90 or not -90 <= max_lat <= 90:
        raise ValueError("bbox latitude values must be between -90 and 90")
    if min_lon > max_lon:
        raise ValueError("bbox minLon must be less than or equal to maxLon")
    if min_lat > max_lat:
        raise ValueError("bbox minLat must be less than or equal to maxLat")

    return bbox


def load_feature_collection(path: str | Path) -> list[Feature]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON fixture must be a FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON fixture features must be a list")
    return features


def extract_coordinates(feature: Feature) -> tuple[float, float]:
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError("GeoJSON feature geometry must be a Point")

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValueError("GeoJSON point coordinates must contain longitude and latitude")

    try:
        lon = float(coordinates[0])
        lat = float(coordinates[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("GeoJSON point coordinates must be numbers") from exc

    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError("GeoJSON point coordinates must be finite numbers")

    return lon, lat


def contains_coordinate(bbox: BBox, lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def normalize_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if isinstance(limit, bool):
        raise ValueError("limit must be a positive integer")
    try:
        normalized = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be a positive integer") from exc
    if normalized < 1:
        raise ValueError("limit must be a positive integer")
    return normalized


def filter_by_bbox(features: list[Feature], bbox: BBox, limit: int | None = DEFAULT_LIMIT) -> list[Feature]:
    max_results = normalize_limit(limit)
    results: list[Feature] = []

    for feature in features:
        lon, lat = extract_coordinates(feature)
        if contains_coordinate(bbox, lon, lat):
            results.append(feature)
            if len(results) >= max_results:
                break

    return results
