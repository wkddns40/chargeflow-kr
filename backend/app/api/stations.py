from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.station import StationFeatureCollection
from station_query import (
    DEFAULT_LIMIT,
    Feature,
    filter_by_bbox,
    load_feature_collection,
    normalize_limit,
    parse_bbox,
)

router = APIRouter(tags=["stations"])

MAX_LIMIT = 7000
STATION_SOURCE = "synthetic-stations-7k"
STATION_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / f"{STATION_SOURCE}.geojson"


@lru_cache(maxsize=4)
def load_station_features(path: str = str(STATION_FIXTURE_PATH)) -> list[Feature]:
    fixture_path = Path(path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Synthetic station fixture not found: {fixture_path}")
    return load_feature_collection(fixture_path)


@router.get("/stations", response_model=StationFeatureCollection)
def list_stations(
    bbox: Annotated[str | None, Query(description="west,south,east,north in EPSG:4326")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> dict:
    if bbox is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox is required as west,south,east,north",
        )

    try:
        parsed_bbox = parse_bbox(bbox)
        normalized_limit = normalize_limit(limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        features = load_station_features()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    filtered = filter_by_bbox(features, parsed_bbox, normalized_limit)
    return {
        "type": "FeatureCollection",
        "features": filtered,
        "meta": {
            "count": len(filtered),
            "limit": normalized_limit,
            "source": STATION_SOURCE,
        },
    }
