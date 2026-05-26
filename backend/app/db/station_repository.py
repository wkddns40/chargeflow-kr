from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from station_query import BBox, Feature


STATION_FEATURES_SQL = """
SELECT
    s.id AS charger_id,
    s.name AS charger_name,
    s.operator,
    s.address,
    ST_X(s.geom) AS lon,
    ST_Y(s.geom) AS lat,
    c.connector_type,
    c.max_kw,
    c.status,
    c.status_updated_at
FROM stations s
JOIN LATERAL (
    SELECT connector_type, max_kw, status, status_updated_at
    FROM connectors
    WHERE station_id = s.id
    ORDER BY id
    LIMIT 1
) c ON true
WHERE s.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
  AND ST_Intersects(s.geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
ORDER BY s.id
LIMIT %s
"""


def query_station_features(connection: Any, bbox: BBox, limit: int) -> list[Feature]:
    params = (*bbox, *bbox, limit)
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(STATION_FEATURES_SQL, params)
        return [station_feature_from_row(row) for row in cursor.fetchall()]


def station_feature_from_row(row: Mapping[str, Any]) -> Feature:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                _required_float(row, "lon"),
                _required_float(row, "lat"),
            ],
        },
        "properties": {
            "charger_id": _required_text(row, "charger_id"),
            "charger_name": _required_text(row, "charger_name"),
            "operator": _required_text(row, "operator"),
            "connector_type": _required_text(row, "connector_type"),
            "max_kw": _required_float(row, "max_kw"),
            "address": _required_text(row, "address"),
            "status": _required_text(row, "status"),
            "status_updated_at": _timestamp_text(row, "status_updated_at"),
        },
    }


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"station row {key} is required")
    return value.strip()


def _required_float(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"station row {key} must be numeric") from exc


def _timestamp_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"station row {key} must include timezone")
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"station row {key} is required")
