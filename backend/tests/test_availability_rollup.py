from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from availability_rollup import (
    aggregate_by_time_window,
    calculate_available_ratio_by_region,
    count_stale_connectors,
    normalize_status,
)


KST = timezone(timedelta(hours=9))
RAW_HASH = "sha256:9bcbf53c2d3d1f1e7cc04b5c6f8c8e7d97b3a89c5a482bb3d1d52f8e91c2a6d0"


def ts(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, minute, tzinfo=KST)


def event(
    connector_id: str,
    region_code: str,
    status: str,
    observed_at: datetime,
    *,
    received_at: datetime | None = None,
) -> dict:
    return {
        "connector_id": connector_id,
        "region_code": region_code,
        "status": status,
        "source": "synthetic-status-file-sample",
        "snapshot_date": "2026-05-19",
        "observed_at": observed_at.isoformat(),
        "received_at": (received_at or observed_at + timedelta(minutes=5)).isoformat(),
        "raw_file_hash": RAW_HASH,
    }


def test_normalize_status_accepts_source_aliases() -> None:
    assert normalize_status("Available") == "available"
    assert normalize_status("charging") == "occupied"
    assert normalize_status("out_of_service") == "offline"
    assert normalize_status("unknown") == "unknown"


def test_calculates_available_ratio_by_region_from_latest_connector_events() -> None:
    start = ts(19, 8)
    end = ts(19, 10)
    events = [
        event("A", "KR-11", "occupied", ts(19, 8, 5)),
        event("A", "KR-11", "available", ts(19, 8, 30)),
        event("B", "KR-11", "occupied", ts(19, 8, 10)),
        event("C", "KR-11", "offline", ts(19, 8, 20)),
        event("D", "KR-26", "available", ts(19, 8, 40)),
    ]

    assert calculate_available_ratio_by_region(events, start, end) == {
        "KR-11": pytest.approx(1 / 3),
        "KR-26": 1.0,
    }


def test_counts_stale_connectors_from_latest_event_only() -> None:
    reference = ts(19, 10)
    events = [
        event("stale", "KR-11", "available", ts(10, 9)),
        event("fresh", "KR-11", "available", ts(18, 9)),
        event("boundary", "KR-11", "available", ts(12, 10)),
        event("updated", "KR-26", "offline", ts(10, 9)),
        event("updated", "KR-26", "available", ts(19, 9)),
    ]

    assert count_stale_connectors(events, reference) == 1


def test_aggregate_by_time_window_uses_inclusive_start_exclusive_end() -> None:
    start = ts(19, 8)
    end = ts(19, 9)
    rollups = aggregate_by_time_window(
        [
            event("start", "KR-11", "available", start),
            event("end", "KR-11", "occupied", end),
        ],
        start,
        end,
    )

    assert rollups == [
        {
            "region_code": "KR-11",
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "available_count": 1,
            "occupied_count": 0,
            "offline_count": 0,
            "unknown_count": 0,
            "stale_count": 0,
            "total_count": 1,
            "available_ratio": 1.0,
            "source": "synthetic-status-file-sample",
            "snapshot_date": "2026-05-19",
            "raw_file_hash": RAW_HASH,
            "calculated_at": end.isoformat(),
        }
    ]


def test_aggregate_by_time_window_separates_stale_from_status_counts() -> None:
    start = ts(10, 0)
    end = ts(19, 10)
    rollups = aggregate_by_time_window(
        [
            event("old", "KR-11", "available", ts(10, 9)),
            event("fresh", "KR-11", "available", ts(19, 9)),
        ],
        start,
        end,
    )

    assert rollups[0]["available_count"] == 1
    assert rollups[0]["stale_count"] == 1
    assert rollups[0]["total_count"] == 2
    assert rollups[0]["available_ratio"] == 0.5


@pytest.mark.parametrize(
    ("bad_event", "message"),
    [
        ({}, "connector_id"),
        (event("A", "KR-11", "unmapped", ts(19, 8)), "unsupported status"),
        (
            {
                **event("A", "KR-11", "available", ts(19, 8)),
                "observed_at": "not-a-timestamp",
            },
            "observed_at",
        ),
        (
            {
                **event("A", "KR-11", "available", ts(19, 8)),
                "received_at": "2026-05-19T08:00:00",
            },
            "received_at must include timezone",
        ),
    ],
)
def test_malformed_events_fail_with_clear_errors(bad_event: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        aggregate_by_time_window([bad_event], ts(19, 8), ts(19, 9))
