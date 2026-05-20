"""Local place lookup for Phase 6C charger search.

This module intentionally does not call external geocoding APIs. The first
Phase 6C search path resolves only a small fixture map of known places.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceLocation:
    place_id: str
    name: str
    lon: float
    lat: float
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, float | str]:
        return {
            "place_id": self.place_id,
            "name": self.name,
            "lon": self.lon,
            "lat": self.lat,
        }


class UnknownPlaceError(ValueError):
    """Raised when a place is not present in the local fixture map."""


LOCAL_PLACES: tuple[PlaceLocation, ...] = (
    PlaceLocation(
        place_id="gangnam-station",
        name="Gangnam Station",
        lon=127.0276,
        lat=37.4979,
        aliases=("강남역", "gangnam", "gangnam station"),
    ),
    PlaceLocation(
        place_id="seoul-station",
        name="Seoul Station",
        lon=126.9707,
        lat=37.5547,
        aliases=("서울역", "seoul", "seoul station"),
    ),
    PlaceLocation(
        place_id="jeju-airport",
        name="Jeju Airport",
        lon=126.4930,
        lat=33.5071,
        aliases=("제주공항", "jeju airport", "jeju international airport"),
    ),
)

def lookup_place(place_name: str, place_index: Mapping[str, PlaceLocation] | None = None) -> PlaceLocation:
    if not isinstance(place_name, str) or not place_name.strip():
        raise UnknownPlaceError("place is required")

    index = place_index or PLACE_INDEX
    key = normalize_place_name(place_name)
    place = index.get(key)
    if place is None:
        raise UnknownPlaceError(f"unknown place: {place_name.strip()}")
    return place


def normalize_place_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def build_place_index(places: Iterable[PlaceLocation]) -> dict[str, PlaceLocation]:
    return {alias: place for place in places for alias in _place_keys(place)}


def _place_keys(place: PlaceLocation) -> tuple[str, ...]:
    values = (place.place_id, place.name, *place.aliases)
    return tuple(normalize_place_name(value) for value in values)


PLACE_INDEX = build_place_index(LOCAL_PLACES)
