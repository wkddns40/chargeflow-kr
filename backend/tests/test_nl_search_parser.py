from __future__ import annotations

import pytest

import nl_search_parser
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


def test_parses_korean_nearest_query_with_top_three_limit() -> None:
    message = (
        "\uac15\ub0a8\uad6c\uccad\uc5ed\uc5d0\uc11c "
        "\uac00\uc7a5 \uac00\uae4c\uc6b4 \ucda9\uc804\uc18c \ucc3e\uc544\ubd10"
    )
    command = parse(message)

    assert command["place"] == "\uac15\ub0a8\uad6c\uccad\uc5ed"
    assert command["filters"] == {}
    assert command["sort"] == "distance"
    assert command["limit"] == 3


def test_missing_place_returns_clarification() -> None:
    result = parse_natural_language_search({"message": "nearby fast chargers"})

    assert isinstance(result, ClarificationRequired)
    assert result.to_dict() == {
        "type": "clarification_required",
        "message": "Search needs a place. Try: 홍대입구역 근처 급속 충전기.",
        "missing_fields": ["place"],
    }


def test_extracts_korean_station_phrase_without_resolving() -> None:
    command = parse("홍대입구역 근처 3km 100kW 이상 급속 충전기")

    assert command["place"] == "홍대입구역"
    assert command["radius_m"] == 3000
    assert command["filters"] == {"min_kw": 100, "connector_type": "DC"}


def test_extracts_korean_region_phrase_without_resolving() -> None:
    command = parse("서울 전체 사용가능한 충전기")

    assert command["place"] == "서울 전체"
    assert command["filters"] == {"status": "available"}


def test_unsupported_reservation_intent_rejects() -> None:
    with pytest.raises(UnsupportedNaturalLanguageIntentError, match="unsupported intent: reserve_charger"):
        parse_natural_language_search({"message": "reserve a charger near Gangnam Station"})


def test_control_text_rejects() -> None:
    with pytest.raises(NaturalLanguageSearchError, match="unsupported control text"):
        parse_natural_language_search({"message": "Gangnam Station drop table stations"})


class FakeOpenAIResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_openai_parser_uses_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float, **kwargs: object) -> FakeOpenAIResponse:
        requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout, **kwargs})
        return FakeOpenAIResponse(
            {
                "output_text": (
                    '{"type":"search_command","message":"","missing_fields":[],'
                    '"command":{"intent":"find_chargers","place":"Gangnam Station","radius_m":3000,'
                    '"filters":{"min_kw":150,"status":"available","connector_type":"DC Combo"},'
                    '"sort":"power"}}'
                )
            }
        )

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {
            "message": (
                "\uac15\ub0a8\uc5ed \uadfc\ucc98 3km 150kW \uc774\uc0c1 "
                "\uc0ac\uc6a9 \uac00\ub2a5\ud55c DC\ucf64\ubcf4 \ucda9\uc804\uae30"
            )
        },
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        openai_timeout_seconds=4.0,
    )

    assert isinstance(result, ParsedNaturalLanguageSearch)
    assert result.parser == "openai-responses-v1:gpt-4o-mini"
    assert result.command == {
        "intent": "find_chargers",
        "place": "Gangnam Station",
        "radius_m": 3000,
        "filters": {"min_kw": 150, "status": "available", "connector_type": "DC Combo"},
        "sort": "power",
    }
    assert requests[0]["headers"]["Authorization"] == "Bearer sk-test"
    assert requests[0]["url"] == nl_search_parser.OPENAI_RESPONSES_URL
    assert requests[0]["json"]["text"]["format"]["type"] == "json_schema"
    assert requests[0]["json"]["text"]["format"]["strict"] is True
    assert "\\uac15" not in requests[0]["json"]["input"][1]["content"][0]["text"]
    assert requests[0]["timeout"] == 4.0


def test_openai_parser_can_return_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: object, **kwargs: object) -> FakeOpenAIResponse:
        return FakeOpenAIResponse(
            {
                "output_text": (
                    '{"type":"clarification_required","message":"Search needs a place.",'
                    '"missing_fields":["place"],'
                    '"command":{"intent":"find_chargers","place":"","radius_m":2000,'
                    '"filters":{"min_kw":null,"status":null,"connector_type":null},"sort":"distance"}}'
                )
            }
        )

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {"message": "100kW \uc774\uc0c1 \ucda9\uc804\uae30 \ucc3e\uc544\uc918"},
        openai_api_key="sk-test",
    )

    assert isinstance(result, ClarificationRequired)
    assert result.to_dict() == {
        "type": "clarification_required",
        "message": "Search needs a place.",
        "missing_fields": ["place"],
    }


def test_openai_parser_preserves_area_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: object, **kwargs: object) -> FakeOpenAIResponse:
        return FakeOpenAIResponse(
            {
                "output_text": (
                    '{"type":"search_command","message":"","missing_fields":[],'
                    '"command":{"intent":"find_chargers","place":"서울","radius_m":2000,'
                    '"filters":{"min_kw":null,"status":"available","connector_type":null},'
                    '"sort":"availability"}}'
                )
            }
        )

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {"message": "서울 전체 사용가능한 충전기"},
        openai_api_key="sk-test",
    )

    assert isinstance(result, ParsedNaturalLanguageSearch)
    assert result.command["place"] == "서울 전체"


def test_openai_parser_strips_trailing_nearby_from_place(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: object, **kwargs: object) -> FakeOpenAIResponse:
        return FakeOpenAIResponse(
            {
                "output_text": (
                    '{"type":"search_command","message":"","missing_fields":[],'
                    '"command":{"intent":"find_chargers","place":"홍대입구역 근처","radius_m":2000,'
                    '"filters":{"min_kw":null,"status":null,"connector_type":"DC"},'
                    '"sort":"distance"}}'
                )
            }
        )

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {"message": "홍대입구역 근처 급속 충전기"},
        openai_api_key="sk-test",
    )

    assert isinstance(result, ParsedNaturalLanguageSearch)
    assert result.command["place"] == "홍대입구역"


def test_openai_parser_removes_unstated_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: object, **kwargs: object) -> FakeOpenAIResponse:
        return FakeOpenAIResponse(
            {
                "output_text": (
                    '{"type":"search_command","message":"","missing_fields":[],'
                    '"command":{"intent":"find_chargers","place":"홍대입구역","radius_m":2000,'
                    '"filters":{"min_kw":150,"status":"available","connector_type":"DC"},'
                    '"sort":"power"}}'
                )
            }
        )

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {"message": "홍대입구역 근처 급속 충전기"},
        openai_api_key="sk-test",
    )

    assert isinstance(result, ParsedNaturalLanguageSearch)
    assert result.command["filters"] == {"connector_type": "DC"}


def test_openai_parser_falls_back_to_deterministic_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args: object, **kwargs: object) -> None:
        raise nl_search_parser.httpx.TimeoutException("timeout")

    monkeypatch.setattr(nl_search_parser.httpx, "post", fake_post)

    result = parse_natural_language_search(
        {"message": "Gangnam Station nearby 2km fast chargers"},
        openai_api_key="sk-test",
    )

    assert isinstance(result, ParsedNaturalLanguageSearch)
    assert result.parser == "deterministic-v1"
    assert result.command["place"] == "Gangnam Station"
