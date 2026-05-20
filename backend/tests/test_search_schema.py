from __future__ import annotations

import pytest

from search_schema import SearchCommandError, validate_search_command


def valid_command() -> dict:
    return {
        "intent": "find_chargers",
        "place": "강남역",
        "radius_m": 2000,
        "filters": {
            "min_kw": 100,
            "status": "available",
            "connector_type": "DC",
        },
        "sort": "distance",
    }


def test_valid_command_passes_and_normalizes() -> None:
    command = validate_search_command(valid_command())

    assert command.to_dict() == {
        "intent": "find_chargers",
        "place": "강남역",
        "radius_m": 2000,
        "filters": {
            "min_kw": 100,
            "status": "available",
            "connector_type": "DC",
        },
        "sort": "distance",
    }


def test_optional_filters_default_to_empty_object_and_distance_sort() -> None:
    command = validate_search_command(
        {
            "intent": "find_chargers",
            "place": "제주공항",
            "radius_m": 3000,
        }
    )

    assert command.to_dict() == {
        "intent": "find_chargers",
        "place": "제주공항",
        "radius_m": 3000,
        "filters": {},
        "sort": "distance",
    }


def test_status_and_connector_aliases_are_normalized() -> None:
    payload = valid_command()
    payload["filters"] = {
        "status": "사용 가능",
        "connector_type": "dc 콤보",
    }

    command = validate_search_command(payload)

    assert command.filters.status == "available"
    assert command.filters.connector_type == "DC Combo"


@pytest.mark.parametrize("intent", ["plan_route", "compare_prices", "", 3])
def test_unknown_intent_rejects(intent: object) -> None:
    payload = valid_command()
    payload["intent"] = intent

    with pytest.raises(SearchCommandError, match="intent"):
        validate_search_command(payload)


@pytest.mark.parametrize("radius_m", [0, -1, 50_001, 2.5, "2000", True])
def test_invalid_radius_rejects(radius_m: object) -> None:
    payload = valid_command()
    payload["radius_m"] = radius_m

    with pytest.raises(SearchCommandError, match="radius_m"):
        validate_search_command(payload)


def test_unsupported_status_rejects() -> None:
    payload = valid_command()
    payload["filters"]["status"] = "maybe"

    with pytest.raises(SearchCommandError, match="filters.status"):
        validate_search_command(payload)


def test_unsupported_connector_type_rejects() -> None:
    payload = valid_command()
    payload["filters"]["connector_type"] = "Tesla NACS"

    with pytest.raises(SearchCommandError, match="filters.connector_type"):
        validate_search_command(payload)


def test_unsupported_sort_rejects() -> None:
    payload = valid_command()
    payload["sort"] = "price"

    with pytest.raises(SearchCommandError, match="sort"):
        validate_search_command(payload)


def test_unknown_schema_fields_reject() -> None:
    payload = valid_command()
    payload["sql"] = "select * from stations"

    with pytest.raises(SearchCommandError, match="unsupported command field"):
        validate_search_command(payload)


def test_sql_like_place_text_rejects() -> None:
    payload = valid_command()
    payload["place"] = "강남역; drop table stations"

    with pytest.raises(SearchCommandError, match="place contains unsupported control text"):
        validate_search_command(payload)
