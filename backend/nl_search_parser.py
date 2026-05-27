"""Free-text charger search parser with optional OpenAI extraction."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from geocoding import normalize_place_name
from search_schema import MAX_RESULT_LIMIT, SUSPICIOUS_TEXT


DEFAULT_RADIUS_M = 2_000
MAX_MESSAGE_LENGTH = 500
PARSER_VERSION = "deterministic-v1"
OPENAI_PARSER_VERSION = "openai-responses-v1"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
NEAREST_QUERY_LIMIT = 3

RADIUS_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>km|kilometers?|m|meters?)\b", re.IGNORECASE)
MIN_KW_RE = re.compile(r"(?P<value>\d{1,4})\s*(?:kw|kilowatts?)\b", re.IGNORECASE)
LIMIT_RE = re.compile(
    r"(?:\b(?:top|nearest|closest)\s*(?P<english_value>\d{1,2})\b)"
    r"|(?:(?P<korean_value>\d{1,2})\s*(?:\uac1c|\uacf3|\uc21c\uc704|\uc704))",
    re.IGNORECASE,
)
AREA_CONTEXT_RE = re.compile(r"(전체|전역|지역|일대|도시)")
PLACE_TRAILING_CONTEXT_RE = re.compile(r"\s*(근처|주변|인근|부근|nearby|near)\s*$", re.IGNORECASE)
ENGLISH_PLACE_RE = re.compile(
    r"\b(?P<place>[A-Z][A-Za-z0-9 .'-]{1,40}\s(?:Station|Airport|Terminal|City|District|County|Province))\b"
)
KOREAN_PLACE_RE = re.compile(
    r"(?P<place>[가-힣A-Za-z0-9·.'-]{1,32}(?:역|공항|터미널|특별시|광역시|특별자치시|특별자치도|자치도|도|시|군|구|읍|면|동))"
)

EXTRA_PLACE_ALIASES = {
    "\uac15\ub0a8\uc5ed": "Gangnam Station",
    "\uac15\ub0a8 \uc5ed": "Gangnam Station",
    "\uc11c\uc6b8\uc5ed": "Seoul Station",
    "\uc11c\uc6b8 \uc5ed": "Seoul Station",
    "\uc81c\uc8fc\uacf5\ud56d": "Jeju Airport",
    "\uc81c\uc8fc \uacf5\ud56d": "Jeju Airport",
    "\uc81c\uc8fc\uad6d\uc81c\uacf5\ud56d": "Jeju Airport",
}

KOREA_REGION_TERMS = (
    "수도권",
    "서울특별시",
    "서울",
    "부산광역시",
    "부산",
    "대구광역시",
    "대구",
    "인천광역시",
    "인천",
    "광주광역시",
    "광주",
    "대전광역시",
    "대전",
    "울산광역시",
    "울산",
    "세종특별자치시",
    "세종",
    "경기도",
    "경기",
    "강원특별자치도",
    "강원",
    "충청북도",
    "충북",
    "충청남도",
    "충남",
    "전북특별자치도",
    "전북",
    "전라남도",
    "전남",
    "경상북도",
    "경북",
    "경상남도",
    "경남",
    "제주특별자치도",
    "제주",
)

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
DC_COMBO_PHRASES = ("dc combo", "dc콤보", "dc 콤보", "디씨콤보", "디씨 콤보")

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
NEAREST_LIMIT_PHRASES = ("nearest", "closest", "\uac00\uc7a5 \uac00\uae4c\uc6b4")


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
    place = _extract_place(message)
    if place is None:
        return ClarificationRequired(
            message="Search needs a place. Try: 홍대입구역 근처 급속 충전기.",
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
    limit = _extract_limit(message, normalized)
    if limit is not None:
        command["limit"] = limit
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
    clean_command = _clean_openai_command(command)
    clean_command["place"] = _apply_area_context_to_place(message, clean_command.get("place"))
    clean_command = _enforce_explicit_filters(message, clean_command)
    clean_command = _enforce_nearest_limit(message, clean_command)
    return ParsedNaturalLanguageSearch(
        message=message,
        command=clean_command,
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
    clean_command = {
        "intent": command.get("intent"),
        "place": _clean_openai_place(command.get("place")),
        "radius_m": command.get("radius_m"),
        "filters": clean_filters,
        "sort": command.get("sort"),
    }
    if command.get("limit") is not None:
        clean_command["limit"] = command.get("limit")
    return clean_command


def _clean_openai_place(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _clean_place_phrase(value)


def _apply_area_context_to_place(message: str, place: Any) -> Any:
    if not isinstance(place, str) or not place.strip() or not AREA_CONTEXT_RE.search(message):
        return place
    stripped = place.strip()
    if AREA_CONTEXT_RE.search(stripped) or stripped.endswith(("역", "공항", "터미널", "Station", "Airport", "Terminal")):
        return stripped
    return f"{stripped} 전체"


def _enforce_explicit_filters(message: str, command: dict[str, Any]) -> dict[str, Any]:
    filters = command.get("filters")
    if not isinstance(filters, dict):
        return command

    normalized = normalize_place_name(message)
    if filters.get("min_kw") is not None and _extract_min_kw(message) is None:
        filters.pop("min_kw", None)
    if filters.get("status") is not None and _extract_status(normalized) != filters.get("status"):
        filters.pop("status", None)
    if filters.get("connector_type") is not None and _extract_connector_type(normalized) != filters.get("connector_type"):
        filters.pop("connector_type", None)
    return command


def _enforce_nearest_limit(message: str, command: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_place_name(message)
    limit = _extract_limit(message, normalized)
    if limit is None:
        return command

    command["sort"] = "distance"
    command["limit"] = limit
    return command


def _openai_system_prompt() -> str:
    return (
        "You parse user free text into a local EV charger search command. "
        "Supported intent is only find_chargers. Extract only the user's place phrase into command.place; "
        "do not geocode it, translate it, canonicalize it, choose coordinates, or decide whether it is supported. "
        "The backend resolver owns place lookup and disambiguation. "
        "For Korean input, keep Korean station/region phrases such as 홍대입구역, 강남구, 서울, 부산역. "
        "If the user asks for a whole area with words like 전체, 전역, 지역, or 도시, keep that qualifier "
        "in the place phrase, for example 서울 전체, 부산 전체, or 수도권 전체. "
        "For English input, keep concise phrases such as Gangnam Station or Busan Station. "
        "If the place phrase is missing, "
        "return clarification_required with missing_fields containing place. "
        "Use radius_m from text; default to 2000 for nearby searches. "
        "If the user asks for nearest/closest chargers without an explicit count, set limit=3. "
        "If nearest/closest text includes an explicit count, set limit to that count up to 50. "
        "Otherwise set limit to null. "
        "Map Korean and English charger wording to filters: fast/rapid/quick/DC "
        "and Korean fast-charger words -> DC, slow/AC and Korean slow-charger words -> AC, "
        "available/free and Korean available words -> available, occupied/busy/in-use words -> occupied, "
        "offline/broken/fault words -> offline, unknown/no-status words -> unknown. "
        "Only set status when availability, occupancy, offline, or unknown status is explicitly requested. "
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
                "required": ["intent", "place", "radius_m", "filters", "sort", "limit"],
                "properties": {
                    "intent": {"type": "string", "enum": ["find_chargers"]},
                    "place": {"type": "string"},
                    "radius_m": {"type": "integer", "minimum": 1, "maximum": 50000},
                    "sort": {"type": "string", "enum": ["distance", "power", "availability"]},
                    "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 50},
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


def _extract_place(message: str) -> str | None:
    matches: list[tuple[int, str]] = []
    normalized = normalize_place_name(message)

    for match in KOREAN_PLACE_RE.finditer(message):
        place = _clean_place_phrase(match.group("place"))
        if place:
            matches.append((len(place), place))

    for match in ENGLISH_PLACE_RE.finditer(message):
        place = _clean_place_phrase(match.group("place"))
        if place:
            matches.append((len(place), place))

    for alias, canonical_name in EXTRA_PLACE_ALIASES.items():
        normalized_alias = normalize_place_name(alias)
        if normalized_alias in normalized:
            matches.append((len(normalized_alias), canonical_name))

    for term in KOREA_REGION_TERMS:
        if term in message:
            place_phrase = f"{term} 전체" if AREA_CONTEXT_RE.search(message) else term
            matches.append((len(place_phrase), place_phrase))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][1]


def _clean_place_phrase(place: str) -> str:
    cleaned = place.strip(" ,.;:()[]{}\"'")
    while True:
        next_value = PLACE_TRAILING_CONTEXT_RE.sub("", cleaned).strip(" ,.;:()[]{}\"'")
        if next_value == cleaned:
            return cleaned
        cleaned = next_value


def _extract_radius_m(message: str) -> int:
    match = RADIUS_RE.search(message)
    if match is None:
        return DEFAULT_RADIUS_M

    value = float(match.group("value"))
    unit = match.group("unit").casefold()
    multiplier = 1_000 if unit.startswith("k") else 1
    return max(1, int(round(value * multiplier)))


def _extract_limit(message: str, normalized: str) -> int | None:
    if not _is_nearest_limit_query(normalized):
        return None

    match = LIMIT_RE.search(message)
    if match is not None:
        value_text = match.group("english_value") or match.group("korean_value")
        if value_text is not None:
            value = int(value_text)
            return min(max(value, 1), MAX_RESULT_LIMIT)

    return NEAREST_QUERY_LIMIT


def _is_nearest_limit_query(normalized: str) -> bool:
    return any(normalize_place_name(phrase) in normalized for phrase in NEAREST_LIMIT_PHRASES)


def _extract_min_kw(message: str) -> int | None:
    match = MIN_KW_RE.search(message)
    if match is None:
        return None
    return int(match.group("value"))


def _extract_connector_type(normalized: str) -> str | None:
    if any(phrase in normalized for phrase in CHADEMO_PHRASES):
        return "CHAdeMO"
    if any(phrase in normalized for phrase in DC_COMBO_PHRASES):
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
