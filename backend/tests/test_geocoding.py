from __future__ import annotations

import pytest

from geocoding import (
    LOCAL_PLACES,
    UnknownPlaceError,
    build_place_index,
    lookup_place,
    normalize_place_name,
)


def test_lookup_known_place_by_english_name() -> None:
    place = lookup_place("Gangnam Station")

    assert place.place_id == "gangnam-station"
    assert place.lon == pytest.approx(127.0276)
    assert place.lat == pytest.approx(37.4979)


def test_lookup_known_place_by_korean_alias() -> None:
    place = lookup_place("  제주공항  ")

    assert place.to_dict() == {
        "place_id": "jeju-airport",
        "name": "Jeju Airport",
        "lon": pytest.approx(126.4930),
        "lat": pytest.approx(33.5071),
    }


def test_lookup_known_place_by_casefolded_alias() -> None:
    place = lookup_place("SEOUL   STATION")

    assert place.place_id == "seoul-station"
    assert place.lon == pytest.approx(126.9707)
    assert place.lat == pytest.approx(37.5547)


def test_unknown_place_raises_typed_error() -> None:
    with pytest.raises(UnknownPlaceError, match="unknown place"):
        lookup_place("Busan Station")


@pytest.mark.parametrize("place_name", ["", "   ", None])
def test_missing_place_raises_typed_error(place_name: object) -> None:
    with pytest.raises(UnknownPlaceError, match="place is required"):
        lookup_place(place_name)  # type: ignore[arg-type]


def test_fixture_place_map_contains_initial_places() -> None:
    assert {place.place_id for place in LOCAL_PLACES} == {
        "gangnam-station",
        "seoul-station",
        "jeju-airport",
    }


def test_build_place_index_accepts_custom_fixture_map() -> None:
    index = build_place_index(LOCAL_PLACES)

    assert index[normalize_place_name("강남역")].place_id == "gangnam-station"
    assert index[normalize_place_name("Jeju International Airport")].place_id == "jeju-airport"
