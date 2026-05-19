"""Availability rollup helpers for imported status-event snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any


StatusEvent = Mapping[str, Any]
Rollup = dict[str, Any]

DEFAULT_STALE_THRESHOLD = timedelta(days=7)
NORMALIZED_STATUSES = ("available", "occupied", "offline", "unknown")
STATUS_ALIASES = {
    "available": "available",
    "avail": "available",
    "available_now": "available",
    "occupied": "occupied",
    "busy": "occupied",
    "charging": "occupied",
    "in_use": "occupied",
    "offline": "offline",
    "out_of_service": "offline",
    "unavailable": "offline",
    "unknown": "unknown",
}


def normalize_status(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("status is required")

    status = value.strip().lower()
    normalized = STATUS_ALIASES.get(status)
    if normalized is None:
        raise ValueError(f"unsupported status: {value}")
    return normalized


def calculate_available_ratio_by_region(
    events: Iterable[StatusEvent],
    window_start: datetime,
    window_end: datetime,
    *,
    stale_cutoff: datetime | None = None,
) -> dict[str, float]:
    rollups = aggregate_by_time_window(events, window_start, window_end, stale_cutoff=stale_cutoff)
    return {rollup["region_code"]: rollup["available_ratio"] for rollup in rollups}


def count_stale_connectors(
    events: Iterable[StatusEvent],
    reference_time: datetime,
    *,
    stale_threshold: timedelta = DEFAULT_STALE_THRESHOLD,
) -> int:
    reference = _require_aware_datetime(reference_time, "reference_time")
    if stale_threshold <= timedelta(0):
        raise ValueError("stale_threshold must be positive")

    latest: dict[str, Rollup] = {}
    for index, event in enumerate(events):
        normalized = _normalize_event(event, index)
        if normalized["observed_at"] > reference:
            continue
        _keep_latest(latest, normalized)

    stale_cutoff = reference - stale_threshold
    return sum(1 for event in latest.values() if event["observed_at"] < stale_cutoff)


def aggregate_by_time_window(
    events: Iterable[StatusEvent],
    window_start: datetime,
    window_end: datetime,
    *,
    stale_cutoff: datetime | None = None,
    calculated_at: datetime | None = None,
) -> list[Rollup]:
    start = _require_aware_datetime(window_start, "window_start")
    end = _require_aware_datetime(window_end, "window_end")
    if end <= start:
        raise ValueError("window_end must be after window_start")

    calculated = _require_aware_datetime(calculated_at or end, "calculated_at")
    cutoff = _require_aware_datetime(stale_cutoff or calculated - DEFAULT_STALE_THRESHOLD, "stale_cutoff")

    latest = _latest_events_in_window(events, start, end)
    grouped: dict[str, Rollup] = {}
    metadata_events: dict[str, Rollup] = {}

    for event in latest.values():
        region_code = event["region_code"]
        rollup = grouped.setdefault(region_code, _empty_rollup(region_code, start, end, calculated))
        rollup["total_count"] += 1

        if event["observed_at"] < cutoff:
            rollup["stale_count"] += 1
        else:
            rollup[f"{event['status']}_count"] += 1

        current = metadata_events.get(region_code)
        if current is None or _event_sort_key(event) > _event_sort_key(current):
            metadata_events[region_code] = event

    results: list[Rollup] = []
    for region_code in sorted(grouped):
        rollup = grouped[region_code]
        metadata_event = metadata_events[region_code]
        total_count = rollup["total_count"]
        rollup["available_ratio"] = rollup["available_count"] / total_count if total_count else 0.0
        rollup["source"] = metadata_event["source"]
        rollup["snapshot_date"] = metadata_event["snapshot_date"]
        rollup["raw_file_hash"] = metadata_event["raw_file_hash"]
        results.append(rollup)

    return results


def _latest_events_in_window(events: Iterable[StatusEvent], start: datetime, end: datetime) -> dict[str, Rollup]:
    latest: dict[str, Rollup] = {}
    for index, event in enumerate(events):
        normalized = _normalize_event(event, index)
        if start <= normalized["observed_at"] < end:
            _keep_latest(latest, normalized)
    return latest


def _normalize_event(event: StatusEvent, index: int) -> Rollup:
    if not isinstance(event, Mapping):
        raise ValueError(f"event at index {index}: event must be an object")

    try:
        normalized = {
            "connector_id": _require_text(event, "connector_id"),
            "region_code": _require_text(event, "region_code"),
            "status": normalize_status(event.get("status")),
            "source": _require_text(event, "source"),
            "snapshot_date": _optional_text(event, "snapshot_date"),
            "observed_at": _parse_event_datetime(event, "observed_at"),
            "received_at": _parse_event_datetime(event, "received_at"),
            "raw_file_hash": _require_text(event, "raw_file_hash"),
        }
    except ValueError as exc:
        raise ValueError(f"event at index {index}: {exc}") from exc

    return normalized


def _keep_latest(latest: dict[str, Rollup], event: Rollup) -> None:
    connector_id = event["connector_id"]
    current = latest.get(connector_id)
    if current is None or _event_sort_key(event) > _event_sort_key(current):
        latest[connector_id] = event


def _event_sort_key(event: Rollup) -> tuple[datetime, datetime, str]:
    return event["observed_at"], event["received_at"], event["connector_id"]


def _empty_rollup(region_code: str, start: datetime, end: datetime, calculated_at: datetime) -> Rollup:
    return {
        "region_code": region_code,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "available_count": 0,
        "occupied_count": 0,
        "offline_count": 0,
        "unknown_count": 0,
        "stale_count": 0,
        "total_count": 0,
        "available_ratio": 0.0,
        "source": "",
        "snapshot_date": "",
        "raw_file_hash": "",
        "calculated_at": calculated_at.isoformat(),
    }


def _require_text(event: StatusEvent, field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_text(event: StatusEvent, field: str) -> str:
    value = event.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value.strip()


def _parse_event_datetime(event: StatusEvent, field: str) -> datetime:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    return _require_aware_datetime(parsed, field)


def _require_aware_datetime(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone")
    return value
