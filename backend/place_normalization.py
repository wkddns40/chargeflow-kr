from __future__ import annotations


def normalize_place_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def compact_place_name(value: str) -> str:
    return normalize_place_name(value).replace(" ", "")


def place_lookup_keys(value: str) -> tuple[str, ...]:
    normalized = normalize_place_name(value)
    compact = normalized.replace(" ", "")
    if compact == normalized:
        return (normalized,)
    return (normalized, compact)
