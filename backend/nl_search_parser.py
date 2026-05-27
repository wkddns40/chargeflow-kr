"""Free-text charger search parser with optional OpenAI extraction."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from geocoding import PLACE_INDEX, normalize_place_name
from search_schema import SUSPICIOUS_TEXT


DEFAULT_RADIUS_M = 2_000
MAX_MESSAGE_LENGTH = 500
PARSER_VERSION = "deterministic-v1"
OPENAI_PARSER_VERSION = "openai-responses-v1"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

RADIUS_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>km|kilometers?|m|meters?)\b", re.IGNORECASE)
MIN_KW_RE = re.compile(r"(?P<value>\d{1,4})\s*(?:kw|kilowatts?)\b", re.IGNORECASE)

EXTRA_PLACE_ALIASES = {
    "\uac15\ub0a8\uc5ed": "Gangnam Station",
    "\uac15\ub0a8 \uc5ed": "Gangnam Station",
    "\uc11c\uc6b8\uc5ed": "Seoul Station",
    "\uc11c\uc6b8 \uc5ed": "Seoul Station",
    "\uc81c\uc8fc\uacf5\ud56d": "Jeju Airport",
    "\uc81c\uc8fc \uacf5\ud56d": "Jeju Airport",
    "\uc81c\uc8fc\uad6d\uc81c\uacf5\ud56d": "Jeju Airport",
}

UNSUPPORTED_INTENT_PHRASES = (
    ("reserve", "reserve_charger"),
    ("reservation", "reserve_charger"),
    ("\uc608\uc57d", "reserve_charger"),
    ("compare price", "compare_prices"),
    ("price comparison", "compare_prices"),
    ("\uac00\uaca9 \ube44\uad50", "compare_prices"),
    ("wait time", "predict_wait_time"),
    ("waiting time", "predict_wait_time"),
    ("\ub300\uae30\uc2dc\uac04", "predict_wait_time"),
    ("report fault", "report_fault"),
    ("\uace0\uc7a5 \uc2e0\uace0", "report_fault"),
    ("route to", "plan_route"),
    ("navigation", "plan_route"),
)

DC_PHRASES = (
    "dc combo",
    "dc",
    "fast charger",
    "fast chargers",
    "rapid charger",
    "rapid chargers",
    "quick charger",
    "quick chargers",
    "\uae09\uc18d",
)
AC_PHRASES = (
    "ac type 2",
    "ac",
    "slow charger",
    "slow chargers",
    "level 2",
    "\uc644\uc18d",
)
CHADEMO_PHRASES = ("chademo", "cha demo")

STATUS_PHRASES = (
    ("available", "available"),
    ("open", "available"),
    ("free", "available"),
    ("\uc0ac\uc6a9 \uac00\ub2a5", "available"),
    ("\uc0ac\uc6a9\uac00\ub2a5", "available"),
    ("occupied", "occupied"),
    ("busy", "occupied"),
    ("in use", "occupied"),
    ("\uc0ac\uc6a9\uc911", "occupied"),
    ("offline", "offline"),
    ("out of service", "offline"),
    ("broken", "offline"),
    ("\uace0\uc7a5", "offline"),
    ("unknown", "unknown"),
    ("no status", "unknown"),
    ("\uc0c1\ud0dc \ubaa8\ub984", "unknown"),
)

POWER_SORT_PHRASES = ("highest power", "high power", "most powerful", "sort by power", "max kw")
AVAILABILITY_SORT_PHRASES = ("available first", "sort by availability")
DISTANCE_SORT_PHRASES = ("nearest", "closest", "nearby", "distance", "\uac00\uae4c\uc6b4")


class NaturalLanguageSearchError(ValueError):
    """Raised when free-text search input cannot be accepted."""


class UnsupportedNaturalLanguageIntentError(NaturalLanguageSearchError):
    """Raised when text asks for a known unsupported search intent."""


class NaturalLanguageProviderError(NaturalLanguageSearchError):
    """Raised when the optional provider fails to return usable JSON."""


@dataclass(frozen=True)
class ClarificationRequired:
    message: str
    missing_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "clarification_required",
            "message": self.message,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class ParsedNaturalLanguageSearch:
    message: str
    command: dict[str, Any]
    parser: str = PARSER_VERSION


def parse_natural_language_search(
    payload: Mapping[str, Any],
    *,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
    openai_timeout_seconds: float = 8.0,
) -> ParsedNaturalLanguageSearch | ClarificationRequired:
    if not isinstance(payload, Mapping):
        raise NaturalLanguageSearchError("natural-language search payload must be an object")

    message = _parse_message(payload.get("message"))
    normalized = normalize_place_name(message)
    _reject_control_text(normalized)
    _reject_unsupported_intent(normalized)

    if openai_api_key.strip():
        try:
            return _parse_with_openai(message, openai_api_key, openai_model, openai_timeout_seconds)
        except NaturalLanguageProviderError:
            pass

    return parse_deterministic_message(message)


def parse_deterministic_message(message: str) -> ParsedNaturalLanguageSearch | ClarificationRequired:
    normalized = normalize_place_name(message)
    place = _extract_place(normalized)
    if place is None:
        return ClarificationRequired(
            message="Search needs a place. Try: Gangnam Station nearby chargers.",
            missing_fields=("place",),
        )

    min_kw = _extract_min_kw(message)
    filters: dict[str, int | str] = {}
    if min_kw is not None:
        filters["min_kw"] = min_kw

    status = _extract_status(normalized)
    if status is not None:
        filters["status"] = status

    connector_type = _extract_connector_type(normalized)
    if connector_type is not None:
        filters["connector_type"] = connector_type

    command = {
        "intent": "find_chargers",
        "place": place,
        "radius_m": _extract_radius_m(message),
        "filters": filters,
        "sort": _extract_sort(normalized, min_kw),
    }
    return ParsedNaturalLanguageSearch(message=message, command=command)


def _parse_with_openai(
    message: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> ParsedNaturalLanguageSearch | ClarificationRequired:
    response_payload = _create_openai_response(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        message=message,
    )
    parsed = _extract_openai_json(response_payload)

    response_type = parsed.get("type")
    if response_type == "clarification_required":
        missing_fields = parsed.get("missing_fields")
        if not isinstance(missing_fields, list) or not all(isinstance(field, str) for field in missing_fields):
            raise NaturalLanguageProviderError("OpenAI clarification response is invalid")
        message_text = parsed.get("message")
        if not isinstance(message_text, str) or not message_text.strip():
            message_text = "Search needs a place. Try: Gangnam Station nearby chargers."
        return ClarificationRequired(message=message_text.strip(), missing_fields=tuple(missing_fields))

    if response_type != "search_command":
        raise NaturalLanguageProviderError("OpenAI response type is invalid")

    command = parsed.get("command")
    if not isinstance(command, Mapping):
        raise NaturalLanguageProviderError("OpenAI command response is invalid")
    return ParsedNaturalLanguageSearch(
        message=message,
        command=_clean_openai_command(command),
        parser=f"{OPENAI_PARSER_VERSION}:{model}",
    )


def _create_openai_response(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    message: str,
) -> Mapping[str, Any]:
    request = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": _openai_system_prompt(),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps({"message": message}, ensure_ascii=False),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "charger_search_parse",
                "strict": True,
                "schema": _openai_response_schema(),
            }
        },
        "temperature": 0,
    }
    try:
        response = httpx.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise NaturalLanguageProviderError("OpenAI parser request failed") from exc

    if not isinstance(data, Mapping):
        raise NaturalLanguageProviderError("OpenAI parser response is invalid")
    return data


def _extract_openai_json(response_payload: Mapping[str, Any]) -> dict[str, Any]:
    text = response_payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return _parse_json_text(text)

    output = response_payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, Mapping):
                    continue
                refusal = content_item.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    raise NaturalLanguageProviderError("OpenAI parser refused the request")
                content_text = content_item.get("text")
                if isinstance(content_text, str) and content_text.strip():
                    return _parse_json_text(content_text)

    raise NaturalLanguageProviderError("OpenAI parser response has no output text")


def _parse_json_text(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise NaturalLanguageProviderError("OpenAI parser output is not JSON") from exc
    if not isinstance(parsed, dict):
        raise NaturalLanguageProviderError("OpenAI parser output is not an object")
    return parsed


def _clean_openai_command(command: Mapping[str, Any]) -> dict[str, Any]:
    filters = command.get("filters")
    if not isinstance(filters, Mapping):
        raise NaturalLanguageProviderError("OpenAI command filters are invalid")

    clean_filters = {
        key: value
        for key, value in filters.items()
        if key in {"min_kw", "status", "connector_type"} and value is not None
    }
    return {
        "intent": command.get("intent"),
        "place": command.get("place"),
        "radius_m": command.get("radius_m"),
        "filters": clean_filters,
        "sort": command.get("sort"),
    }


def _openai_system_prompt() -> str:
    return (
        "You parse user free text into a local EV charger search command. "
        "Only use supported places: Gangnam Station, Seoul Station, Jeju Airport. "
        "Return canonical English place names. Place aliases: "
        "Gangnam Station = Gangnam, Gangnam Station, \uac15\ub0a8\uc5ed, \uac15\ub0a8 \uc5ed; "
        "Seoul Station = Seoul Station, \uc11c\uc6b8\uc5ed, \uc11c\uc6b8 \uc5ed; "
        "Jeju Airport = Jeju Airport, Jeju International Airport, \uc81c\uc8fc\uacf5\ud56d, "
        "\uc81c\uc8fc \uacf5\ud56d, \uc81c\uc8fc\uad6d\uc81c\uacf5\ud56d. "
        "Supported intent is only find_chargers. If the place is missing or unsupported, "
        "return clarification_required with missing_fields containing place. "
        "Use radius_m from text; default to 2000 for nearby searches. "
        "Map Korean and English charger wording to filters: fast/rapid/quick/DC "
        "and Korean fast-charger words -> DC, slow/AC and Korean slow-charger words -> AC, "
        "available/free and Korean available words -> available, occupied/busy/in-use words -> occupied, "
        "offline/broken/fault words -> offline, unknown/no-status words -> unknown. "
        "Map high power or kW-focused requests to sort=power unless nearest/distance is explicit. "
        "Do not invent charger facts, coordinates, SQL, or external data."
    )


def _openai_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "message", "missing_fields", "command"],
        "properties": {
            "type": {"type": "string", "enum": ["search_command", "clarification_required"]},
            "message": {"type": "string"},
            "missing_fields": {
                "type": "array",
                "items": {"type": "string", "enum": ["place"]},
            },
            "command": {
                "type": "object",
                "additionalProperties": False,
                "required": ["intent", "place", "radius_m", "filters", "sort"],
                "properties": {
                    "intent": {"type": "string", "enum": ["find_chargers"]},
                    "place": {"type": "string"},
                    "radius_m": {"type": "integer", "minimum": 1, "maximum": 50000},
                    "sort": {"type": "string", "enum": ["distance", "power", "availability"]},
                    "filters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["min_kw", "status", "connector_type"],
                        "properties": {
                            "min_kw": {"type": ["integer", "null"], "minimum": 1, "maximum": 1000},
                            "status": {
                                "type": ["string", "null"],
                                "enum": ["available", "occupied", "offline", "unknown", None],
                            },
                            "connector_type": {
                                "type": ["string", "null"],
                                "enum": ["DC", "AC", "DC Combo", "AC Type 2", "CHAdeMO", None],
                            },
                        },
                    },
                },
            },
        },
    }


def _parse_message(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NaturalLanguageSearchError("message is required")
    message = value.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        raise NaturalLanguageSearchError(f"message must be {MAX_MESSAGE_LENGTH} characters or fewer")
    return message


def _reject_control_text(normalized: str) -> None:
    if any(token in normalized for token in SUSPICIOUS_TEXT):
        raise NaturalLanguageSearchError("message contains unsupported control text")


def _reject_unsupported_intent(normalized: str) -> None:
    for phrase, intent in UNSUPPORTED_INTENT_PHRASES:
        if normalize_place_name(phrase) in normalized:
            raise UnsupportedNaturalLanguageIntentError(f"unsupported intent: {intent}")


def _extract_place(normalized: str) -> str | None:
    matches: list[tuple[int, str]] = []

    for alias, place in PLACE_INDEX.items():
        if alias and alias in normalized:
            matches.append((len(alias), place.name))

    for alias, canonical_name in EXTRA_PLACE_ALIASES.items():
        normalized_alias = normalize_place_name(alias)
        if normalized_alias in normalized:
            matches.append((len(normalized_alias), canonical_name))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][1]


def _extract_radius_m(message: str) -> int:
    match = RADIUS_RE.search(message)
    if match is None:
        return DEFAULT_RADIUS_M

    value = float(match.group("value"))
    unit = match.group("unit").casefold()
    multiplier = 1_000 if unit.startswith("k") else 1
    return max(1, int(round(value * multiplier)))


def _extract_min_kw(message: str) -> int | None:
    match = MIN_KW_RE.search(message)
    if match is None:
        return None
    return int(match.group("value"))


def _extract_connector_type(normalized: str) -> str | None:
    if any(phrase in normalized for phrase in CHADEMO_PHRASES):
        return "CHAdeMO"
    if "dc combo" in normalized:
        return "DC Combo"
    if "ac type 2" in normalized:
        return "AC Type 2"
    if any(phrase in normalized for phrase in DC_PHRASES):
        return "DC"
    if any(phrase in normalized for phrase in AC_PHRASES):
        return "AC"
    return None


def _extract_status(normalized: str) -> str | None:
    for phrase, status in STATUS_PHRASES:
        if normalize_place_name(phrase) in normalized:
            return status
    return None


def _extract_sort(normalized: str, min_kw: int | None) -> str:
    if any(phrase in normalized for phrase in AVAILABILITY_SORT_PHRASES):
        return "availability"
    if any(phrase in normalized for phrase in POWER_SORT_PHRASES):
        return "power"
    if min_kw is not None and not any(phrase in normalized for phrase in DISTANCE_SORT_PHRASES):
        return "power"
    return "distance"
