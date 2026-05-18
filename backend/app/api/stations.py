from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from app.db.connection import get_connection
from app.schemas.station import StationFeatureCollection

router = APIRouter(tags=["stations"])


@router.get("/stations", response_model=StationFeatureCollection)
def list_stations(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
    bbox: Annotated[str | None, Query(description="west,south,east,north in EPSG:4326")] = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
) -> dict:
    params: dict[str, object] = {"limit": limit}
    where = ""
    if bbox:
        west, south, east, north = [float(part) for part in bbox.split(",")]
        params.update({"west": west, "south": south, "east": east, "north": north})
        where = """
            WHERE s.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)
        """

    query = f"""
        SELECT
            s.id,
            s.name,
            s.operator,
            s.address,
            ST_X(s.geom) AS longitude,
            ST_Y(s.geom) AS latitude,
            c.connector_type,
            c.max_kw,
            c.status,
            COALESCE(c.status_updated_at, s.updated_at) AS status_updated_at
        FROM stations s
        JOIN connectors c ON c.station_id = s.id
        {where}
        ORDER BY s.id
        LIMIT %(limit)s
    """

    features = []
    with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(query, params)
        for row in cursor.fetchall():
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row["longitude"], row["latitude"]],
                    },
                    "properties": {
                        "charger_id": row["id"],
                        "charger_name": row["name"],
                        "operator": row["operator"],
                        "connector_type": row["connector_type"],
                        "max_kw": float(row["max_kw"]),
                        "address": row["address"],
                        "status": row["status"],
                        "status_updated_at": row["status_updated_at"].isoformat(),
                    },
                }
            )

    return {"type": "FeatureCollection", "features": features}
