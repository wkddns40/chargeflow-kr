from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.stations import load_station_features
from route_planner_graph import build_route_planner_graph
from station_query import Feature

router = APIRouter(tags=["routes"])


@lru_cache(maxsize=1)
def compiled_route_planner_graph() -> Any:
    return build_route_planner_graph()


@router.post("/routes/charging-plan")
def create_charging_plan(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        station_features = load_station_features()
        reference_time = reference_time_from_payload(payload, station_features)
        result = compiled_route_planner_graph().invoke(
            {
                "request": payload,
                "station_features": station_features,
                "reference_time": reference_time,
            }
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    errors = result.get("errors")
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)

    response = result.get("response")
    if not isinstance(response, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="route planner graph did not produce a response",
        )
    return response


def reference_time_from_payload(payload: object, station_features: list[Feature]) -> object:
    if isinstance(payload, Mapping):
        requested_reference_time = payload.get("reference_time")
        if requested_reference_time is not None:
            return requested_reference_time.strip() if isinstance(requested_reference_time, str) else requested_reference_time

    return latest_station_status_time(station_features)


def latest_station_status_time(station_features: list[Feature]) -> str:
    observed_times: list[datetime] = []
    for feature in station_features:
        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            continue
        status_updated_at = properties.get("status_updated_at")
        if not isinstance(status_updated_at, str) or not status_updated_at.strip():
            continue
        observed_at = datetime.fromisoformat(status_updated_at.strip())
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("station status_updated_at must include timezone")
        observed_times.append(observed_at.astimezone(timezone.utc))

    if not observed_times:
        raise ValueError("station features must include status_updated_at")
    return max(observed_times).isoformat()
