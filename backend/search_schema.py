"""Typed command schema for Phase 6C charger search."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


SUPPORTED_INTENTS = ("find_chargers",)
SUPPORTED_STATUSES = ("available", "occupied", "offline", "unknown")
SUPPORTED_CONNECTOR_TYPES = ("DC", "AC", "DC Combo", "AC Type 2", "CHAdeMO")
SUPPORTED_SORTS = ("distance", "power", "availability")

MIN_RADIUS_M = 1
MAX_RADIUS_M = 50_000
MAX_PLACE_LENGTH = 80
MAX_MIN_KW = 1_000

TOP_LEVEL_FIELDS = {"intent", "place", "radius_m", "filters", "sort"}
FILTER_FIELDS = {"min_kw", "status", "connector_type"}
STATUS_ALIASES = {
    "available": "available",
    "사용가능": "available",
    "사용 가능": "available",
    "occupied": "occupied",
    "charging": "occupied",
    "사용중": "occupied",
    "사용 중": "occupied",
    "offline": "offline",
    "out_of_service": "offline",
    "운영중지": "offline",
    "운영 중지": "offline",
    "unknown": "unknown",
    "알수없음": "unknown",
    "알 수 없음": "unknown",
}
CONNECTOR_ALIASES = {
    "dc": "DC",
    "급속": "DC",
    "ac": "AC",
    "완속": "AC",
    "dc combo": "DC Combo",
    "dc콤보": "DC Combo",
    "dc 콤보": "DC Combo",
    "ac type 2": "AC Type 2",
    "chademo": "CHAdeMO",
}
SUSPICIOUS_TEXT = (
    "select",
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "union",
    "join",
    "--",
    "/*",
    "*/",
    ";",
    "api_key",
    "apikey",
    "servicekey",
    "password",
    "secret",
    "token",
    "prompt",
)


class SearchCommandError(ValueError):
    """Raised when an LLM search command does not match the typed schema."""


@dataclass(frozen=True)
class SearchFilters:
    min_kw: int | None = None
    status: str | None = None
    connector_type: str | None = None

    def to_dict(self) -> dict[str, int | str]:
        result: dict[str, int | str] = {}
        if self.min_kw is not None:
            result["min_kw"] = self.min_kw
        if self.status is not None:
            result["status"] = self.status
        if self.connector_type is not None:
            result["connector_type"] = self.connector_type
        return result


@dataclass(frozen=True)
class SearchCommand:
    intent: str
    place: str
    radius_m: int
    filters: SearchFilters
    sort: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "place": self.place,
            "radius_m": self.radius_m,
            "filters": self.filters.to_dict(),
            "sort": self.sort,
        }


def validate_search_command(payload: Mapping[str, Any]) -> SearchCommand:
    if not isinstance(payload, Mapping):
        raise SearchCommandError("search command must be an object")

    _reject_unknown_fields(set(payload), TOP_LEVEL_FIELDS, "command")

    intent = _parse_enum(payload.get("intent"), SUPPORTED_INTENTS, "intent")
    place = _parse_place(payload.get("place"))
    radius_m = _parse_positive_int(payload.get("radius_m"), "radius_m", maximum=MAX_RADIUS_M)
    filters = _parse_filters(payload.get("filters", {}))
    sort = _parse_enum(payload.get("sort", "distance"), SUPPORTED_SORTS, "sort")

    return SearchCommand(intent=intent, place=place, radius_m=radius_m, filters=filters, sort=sort)


def _parse_filters(value: Any) -> SearchFilters:
    if value is None:
        return SearchFilters()
    if not isinstance(value, Mapping):
        raise SearchCommandError("filters must be an object")

    _reject_unknown_fields(set(value), FILTER_FIELDS, "filters")

    min_kw = None
    if "min_kw" in value:
        min_kw = _parse_positive_int(value.get("min_kw"), "filters.min_kw", maximum=MAX_MIN_KW)

    status = None
    if "status" in value:
        status = _parse_alias_enum(value.get("status"), STATUS_ALIASES, SUPPORTED_STATUSES, "filters.status")

    connector_type = None
    if "connector_type" in value:
        connector_type = _parse_alias_enum(
            value.get("connector_type"),
            CONNECTOR_ALIASES,
            SUPPORTED_CONNECTOR_TYPES,
            "filters.connector_type",
        )

    return SearchFilters(min_kw=min_kw, status=status, connector_type=connector_type)


def _parse_place(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SearchCommandError("place is required")
    place = value.strip()
    if len(place) > MAX_PLACE_LENGTH:
        raise SearchCommandError(f"place must be {MAX_PLACE_LENGTH} characters or fewer")
    _reject_suspicious_text(place, "place")
    return place


def _parse_positive_int(value: Any, field: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SearchCommandError(f"{field} must be an integer")
    if value < MIN_RADIUS_M:
        raise SearchCommandError(f"{field} must be positive")
    if value > maximum:
        raise SearchCommandError(f"{field} must be {maximum} or less")
    return value


def _parse_enum(value: Any, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SearchCommandError(f"{field} is required")
    normalized = value.strip().lower()
    _reject_suspicious_text(normalized, field)
    if normalized not in allowed:
        raise SearchCommandError(f"unsupported {field}: {value}")
    return normalized


def _parse_alias_enum(
    value: Any,
    aliases: Mapping[str, str],
    allowed: tuple[str, ...],
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SearchCommandError(f"{field} is required")

    stripped = value.strip()
    lookup_key = stripped.lower()
    _reject_suspicious_text(lookup_key, field)

    normalized = aliases.get(lookup_key, stripped)
    if normalized not in allowed:
        raise SearchCommandError(f"unsupported {field}: {value}")
    return normalized


def _reject_unknown_fields(actual: set[str], allowed: set[str], context: str) -> None:
    unknown = sorted(actual - allowed)
    if unknown:
        raise SearchCommandError(f"unsupported {context} field: {unknown[0]}")


def _reject_suspicious_text(value: str, field: str) -> None:
    lowered = value.lower()
    if any(token in lowered for token in SUSPICIOUS_TEXT):
        raise SearchCommandError(f"{field} contains unsupported control text")
