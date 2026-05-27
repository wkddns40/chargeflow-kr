from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from psycopg.rows import dict_row

from place_normalization import place_lookup_keys
from station_query import BBox


EXACT_PLACE_SQL = """
WITH candidates AS (
    SELECT DISTINCT ON (p.id)
        p.id AS place_id,
        p.name,
        p.place_type,
        p.region_code,
        p.source,
        p.source_ref,
        a.alias AS matched_alias,
        a.priority,
        ST_X(p.geom) AS lon,
        ST_Y(p.geom) AS lat,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_XMin(Box2D(p.bbox)) END AS west,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_YMin(Box2D(p.bbox)) END AS south,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_XMax(Box2D(p.bbox)) END AS east,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_YMax(Box2D(p.bbox)) END AS north
    FROM place_aliases a
    JOIN places p ON p.id = a.place_id
    WHERE a.normalized_alias = ANY(%s::text[])
    ORDER BY p.id, a.priority, length(a.alias)
)
SELECT *
FROM candidates
ORDER BY priority, place_type, name
LIMIT %s
"""

FUZZY_PLACE_SQL = """
WITH candidates AS (
    SELECT DISTINCT ON (p.id)
        p.id AS place_id,
        p.name,
        p.place_type,
        p.region_code,
        p.source,
        p.source_ref,
        a.alias AS matched_alias,
        a.priority + 1000 AS priority,
        ST_X(p.geom) AS lon,
        ST_Y(p.geom) AS lat,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_XMin(Box2D(p.bbox)) END AS west,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_YMin(Box2D(p.bbox)) END AS south,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_XMax(Box2D(p.bbox)) END AS east,
        CASE WHEN p.bbox IS NULL THEN NULL ELSE ST_YMax(Box2D(p.bbox)) END AS north
    FROM place_aliases a
    JOIN places p ON p.id = a.place_id
    WHERE a.normalized_alias LIKE %s
    ORDER BY p.id, a.priority, length(a.alias)
)
SELECT *
FROM candidates
ORDER BY priority, place_type, name
LIMIT %s
"""


@dataclass(frozen=True)
class PlaceCandidate:
    place_id: str
    name: str
    place_type: str
    lon: float
    lat: float
    bbox: BBox | None = None
    region_code: str | None = None
    source: str | None = None
    source_ref: str | None = None
    matched_alias: str | None = None

    @property
    def is_area(self) -> bool:
        return self.place_type in {"province", "district", "subdistrict"}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "place_id": self.place_id,
            "name": self.name,
            "place_type": self.place_type,
            "lon": self.lon,
            "lat": self.lat,
        }
        if self.bbox is not None:
            west, south, east, north = self.bbox
            payload["bbox"] = {"west": west, "south": south, "east": east, "north": north}
        if self.region_code:
            payload["region_code"] = self.region_code
        if self.source:
            payload["source"] = self.source
        if self.source_ref:
            payload["source_ref"] = self.source_ref
        if self.matched_alias:
            payload["matched_alias"] = self.matched_alias
        return payload


def query_place_candidates(connection: Any, place_phrase: str, limit: int = 8) -> list[PlaceCandidate]:
    keys = place_lookup_keys(place_phrase)
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(EXACT_PLACE_SQL, (list(keys), limit))
        exact_rows = cursor.fetchall()
        if exact_rows:
            return [place_candidate_from_row(row) for row in exact_rows]

        fuzzy_key = f"{keys[-1]}%"
        cursor.execute(FUZZY_PLACE_SQL, (fuzzy_key, limit))
        return [place_candidate_from_row(row) for row in cursor.fetchall()]


def place_candidate_from_row(row: Mapping[str, Any]) -> PlaceCandidate:
    west = _optional_float(row, "west")
    south = _optional_float(row, "south")
    east = _optional_float(row, "east")
    north = _optional_float(row, "north")
    bbox = (west, south, east, north) if None not in (west, south, east, north) else None

    return PlaceCandidate(
        place_id=_required_text(row, "place_id"),
        name=_required_text(row, "name"),
        place_type=_required_text(row, "place_type"),
        lon=_required_float(row, "lon"),
        lat=_required_float(row, "lat"),
        bbox=bbox,  # type: ignore[arg-type]
        region_code=_optional_text(row, "region_code"),
        source=_optional_text(row, "source"),
        source_ref=_optional_text(row, "source_ref"),
        matched_alias=_optional_text(row, "matched_alias"),
    )


def unique_candidates(candidates: Sequence[PlaceCandidate]) -> list[PlaceCandidate]:
    seen: set[str] = set()
    unique: list[PlaceCandidate] = []
    for candidate in candidates:
        if candidate.place_id in seen:
            continue
        seen.add(candidate.place_id)
        unique.append(candidate)
    return unique


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"place row {key} is required")
    return value.strip()


def _optional_text(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _required_float(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"place row {key} must be numeric") from exc


def _optional_float(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"place row {key} must be numeric") from exc
