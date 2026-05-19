from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "status-events.sample.json"
REQUIRED_STATUSES = {"available", "occupied", "offline", "unknown"}
REQUIRED_EVENT_KEYS = {
    "connector_id",
    "status",
    "source",
    "observed_at",
    "received_at",
    "raw_file_hash",
    "raw_row_number",
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_status_events_fixture_has_file_import_shape() -> None:
    payload = load_fixture()

    assert set(payload) == {"metadata", "events"}
    assert payload["metadata"]["source_type"] == "file-import-output"
    assert payload["metadata"]["source_file_name"].endswith(".csv")
    assert payload["metadata"]["raw_file_hash"].startswith("sha256:")
    assert payload["metadata"]["event_count"] == len(payload["events"])


def test_status_events_fixture_covers_required_statuses() -> None:
    payload = load_fixture()
    events = payload["events"]

    assert len(events) >= 100
    assert set(payload["metadata"]["allowed_statuses"]) == REQUIRED_STATUSES
    assert {event["status"] for event in events} == REQUIRED_STATUSES


def test_status_events_fixture_rows_have_required_fields() -> None:
    payload = load_fixture()
    expected_hash = payload["metadata"]["raw_file_hash"]

    for event in payload["events"]:
        assert REQUIRED_EVENT_KEYS <= set(event)
        assert event["raw_file_hash"] == expected_hash
        assert isinstance(event["raw_row_number"], int)
        assert datetime.fromisoformat(event["observed_at"])
        assert datetime.fromisoformat(event["received_at"])


def test_status_events_fixture_has_no_credential_material() -> None:
    serialized = json.dumps(load_fixture(), sort_keys=True).lower()

    for forbidden in ("servicekey", "apikey", "api_key", "password", "secret", "token"):
        assert forbidden not in serialized
