from __future__ import annotations

import pytest

from nl_search_parser import (
    ClarificationRequired,
    NaturalLanguageSearchError,
    ParsedNaturalLanguageSearch,
    UnsupportedNaturalLanguageIntentError,
    parse_natural_language_search,
)


def parse(message: str) -> dict:
    result = parse_natural_language_search({"message": message})
    assert isinstance(result, ParsedNaturalLanguageSearch)
    return result.command


def test_parses_gangnam_fast_charger_query() -> None:
    command = parse("Gangnam Station nearby 2km fast chargers")

    assert command == {
        "intent": "find_chargers",
        "place": "Gangnam Station",
        "radius_m": 2000,
        "filters": {"connector_type": "DC"},
        "sort": "distance",
    }


def test_parses_jeju_airport_power_filter() -> None:
    command = parse("Jeju Airport 100kW or higher")

    assert command["place"] == "Jeju Airport"
    assert command["radius_m"] == 2000
    assert command["filters"] == {"min_kw": 100}
    assert command["sort"] == "power"


def test_parses_available_status() -> None:
    command = parse("Seoul Station available chargers nearby")

    assert command["place"] == "Seoul Station"
    assert command["filters"] == {"status": "available"}
    assert command["sort"] == "distance"


def test_missing_place_returns_clarification() -> None:
    result = parse_natural_language_search({"message": "nearby fast chargers"})

    assert isinstance(result, ClarificationRequired)
    assert result.to_dict() == {
        "type": "clarification_required",
        "message": "Search needs a place. Try: Gangnam Station nearby chargers.",
        "missing_fields": ["place"],
    }


def test_unsupported_reservation_intent_rejects() -> None:
    with pytest.raises(UnsupportedNaturalLanguageIntentError, match="unsupported intent: reserve_charger"):
        parse_natural_language_search({"message": "reserve a charger near Gangnam Station"})


def test_control_text_rejects() -> None:
    with pytest.raises(NaturalLanguageSearchError, match="unsupported control text"):
        parse_natural_language_search({"message": "Gangnam Station drop table stations"})
