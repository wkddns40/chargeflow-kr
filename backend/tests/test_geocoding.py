from __future__ import annotations

from contextlib import contextmanager

import pytest

import geocoding
from app.db.place_repository import PlaceCandidate
from geocoding import (
    AmbiguousPlaceError,
    LOCAL_PLACES,
    PLACE_INDEX,
    UnknownPlaceError,
    build_place_index,
    lookup_place,
    normalize_place_name,
)


def test_lookup_known_place_by_english_name() -> None:
    place = lookup_place("Gangnam Station", PLACE_INDEX)

    assert place.place_id == "gangnam-station"
    assert place.lon == pytest.approx(127.0276)
    assert place.lat == pytest.approx(37.4979)


def test_lookup_known_place_by_korean_alias() -> None:
    place = lookup_place("  제주공항  ", PLACE_INDEX)

    assert place.to_dict() == {
        "place_id": "jeju-airport",
        "name": "Jeju Airport",
        "place_type": "station",
        "lon": pytest.approx(126.4930),
        "lat": pytest.approx(33.5071),
    }


def test_lookup_known_place_by_casefolded_alias() -> None:
    place = lookup_place("SEOUL   STATION", PLACE_INDEX)

    assert place.place_id == "seoul-station"
    assert place.lon == pytest.approx(126.9707)
    assert place.lat == pytest.approx(37.5547)


def test_unknown_place_raises_typed_error() -> None:
    with pytest.raises(UnknownPlaceError, match="unknown place"):
        lookup_place("Busan Station", PLACE_INDEX)


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


def test_lookup_place_uses_db_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open_connection():
        yield object()

    candidate = PlaceCandidate(
        place_id="osm-node-1",
        name="홍대입구역",
        place_type="station",
        lon=126.9237,
        lat=37.5572,
    )
    monkeypatch.setattr(geocoding, "open_connection", fake_open_connection)
    monkeypatch.setattr(geocoding, "query_place_candidates", lambda connection, phrase: [candidate])

    assert lookup_place("홍대입구역") == candidate


def test_lookup_place_reports_ambiguous_db_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open_connection():
        yield object()

    candidates = [
        PlaceCandidate("region-emd-1", "서울특별시 중구 중앙동", "subdistrict", 126.99, 37.56),
        PlaceCandidate("region-emd-2", "부산광역시 중구 중앙동", "subdistrict", 129.03, 35.10),
    ]
    monkeypatch.setattr(geocoding, "open_connection", fake_open_connection)
    monkeypatch.setattr(geocoding, "query_place_candidates", lambda connection, phrase: candidates)

    with pytest.raises(AmbiguousPlaceError) as exc_info:
        lookup_place("중앙동")

    assert [candidate.name for candidate in exc_info.value.candidates] == [
        "서울특별시 중구 중앙동",
        "부산광역시 중구 중앙동",
    ]
