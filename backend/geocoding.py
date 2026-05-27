"""Place lookup for Phase 6C charger search."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import psycopg

from app.db.connection import open_connection
from app.db.place_repository import PlaceCandidate, query_place_candidates, unique_candidates
from place_normalization import normalize_place_name


@dataclass(frozen=True)
class PlaceLocation:
    place_id: str
    name: str
    lon: float
    lat: float
    aliases: tuple[str, ...] = ()
    place_type: str = "station"
    bbox: tuple[float, float, float, float] | None = None

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
        return payload


class UnknownPlaceError(ValueError):
    """Raised when a place cannot be resolved."""


class AmbiguousPlaceError(UnknownPlaceError):
    """Raised when a phrase maps to more than one candidate place."""

    def __init__(self, place_name: str, candidates: Iterable[PlaceCandidate]) -> None:
        self.place_name = place_name.strip()
        self.candidates = tuple(candidates)
        super().__init__(f"ambiguous place: {self.place_name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "clarification_required",
            "message": f"'{self.place_name}' matches multiple places. Choose one.",
            "missing_fields": ["place"],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


LOCAL_PLACES: tuple[PlaceLocation, ...] = (
    PlaceLocation(
        place_id="gangnam-station",
        name="Gangnam Station",
        lon=127.0276,
        lat=37.4979,
        aliases=("강남역", "강남 역", "gangnam", "gangnam station"),
    ),
    PlaceLocation(
        place_id="seoul-station",
        name="Seoul Station",
        lon=126.9707,
        lat=37.5547,
        aliases=("서울역", "서울 역", "seoul", "seoul station"),
    ),
    PlaceLocation(
        place_id="jeju-airport",
        name="Jeju Airport",
        lon=126.4930,
        lat=33.5071,
        aliases=("제주공항", "제주 공항", "제주국제공항", "jeju airport", "jeju international airport"),
    ),
)


def lookup_place(
    place_name: str,
    place_index: Mapping[str, PlaceLocation] | None = None,
) -> PlaceLocation | PlaceCandidate:
    if not isinstance(place_name, str) or not place_name.strip():
        raise UnknownPlaceError("place is required")

    if place_index is None:
        db_place = lookup_place_from_db(place_name)
        if db_place is not None:
            return db_place

    index = place_index or PLACE_INDEX
    key = normalize_place_name(place_name)
    place = index.get(key)
    if place is None:
        raise UnknownPlaceError(f"unknown place: {place_name.strip()}")
    return place


def lookup_place_from_db(place_name: str) -> PlaceCandidate | None:
    try:
        with open_connection() as connection:
            candidates = unique_candidates(query_place_candidates(connection, place_name))
    except psycopg.OperationalError:
        return None

    if not candidates:
        return None
    if len(candidates) > 1:
        raise AmbiguousPlaceError(place_name, candidates)
    return candidates[0]


def build_place_index(places: Iterable[PlaceLocation]) -> dict[str, PlaceLocation]:
    return {alias: place for place in places for alias in _place_keys(place)}


def _place_keys(place: PlaceLocation) -> tuple[str, ...]:
    values = (place.place_id, place.name, *place.aliases)
    return tuple(normalize_place_name(value) for value in values)


PLACE_INDEX = build_place_index(LOCAL_PLACES)
