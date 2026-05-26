from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.db import station_repository


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query: str | None = None
        self.params: tuple[Any, ...] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cursor_instance = FakeCursor(rows)
        self.row_factory: object | None = None

    def cursor(self, *, row_factory: object | None = None) -> FakeCursor:
        self.row_factory = row_factory
        return self.cursor_instance


def station_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "charger_id": "CFL-SYN-00001",
        "charger_name": "Gangnam Demo Charger",
        "operator": "ChargeFlow KR",
        "address": "Seoul Gangnam-gu Teheran-ro 123",
        "lon": Decimal("127.0276"),
        "lat": Decimal("37.4979"),
        "connector_type": "DC Combo",
        "max_kw": Decimal("150.0"),
        "status": "available",
        "status_updated_at": datetime(2026, 5, 19, 8, 0, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


def test_query_station_features_uses_postgis_bbox_and_limit_params() -> None:
    connection = FakeConnection([station_row()])

    features = station_repository.query_station_features(
        connection,
        (126.0, 33.0, 128.0, 38.0),
        50,
    )

    cursor = connection.cursor_instance
    assert "ST_MakeEnvelope" in str(cursor.query)
    assert "ST_Intersects" in str(cursor.query)
    assert "LIMIT %s" in str(cursor.query)
    assert cursor.params == (126.0, 33.0, 128.0, 38.0, 126.0, 33.0, 128.0, 38.0, 50)
    assert features[0]["properties"]["charger_id"] == "CFL-SYN-00001"


def test_station_feature_from_row_preserves_geojson_response_shape() -> None:
    feature = station_repository.station_feature_from_row(station_row())

    assert feature == {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [127.0276, 37.4979],
        },
        "properties": {
            "charger_id": "CFL-SYN-00001",
            "charger_name": "Gangnam Demo Charger",
            "operator": "ChargeFlow KR",
            "connector_type": "DC Combo",
            "max_kw": 150.0,
            "address": "Seoul Gangnam-gu Teheran-ro 123",
            "status": "available",
            "status_updated_at": "2026-05-19T08:00:00+00:00",
        },
    }


def test_station_feature_from_row_rejects_missing_required_values() -> None:
    with pytest.raises(ValueError, match="charger_id is required"):
        station_repository.station_feature_from_row(station_row(charger_id=""))


def test_station_feature_from_row_rejects_naive_status_time() -> None:
    with pytest.raises(ValueError, match="status_updated_at must include timezone"):
        station_repository.station_feature_from_row(
            station_row(status_updated_at=datetime(2026, 5, 19, 8, 0))
        )
