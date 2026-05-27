"""Seed DB-backed place lookup rows for natural-language search."""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from place_normalization import normalize_place_name

DEFAULT_OVERPASS_URL = "https://overpass.private.coffee/api/interpreter"
DEFAULT_ARCGIS_EMD_URL = "https://portal.esrikr.com/arcgis/rest/services/Hosted/EMD_view/FeatureServer/0/query"
KOREA_OSM_AREA_ID = 3_600_307_756
ARCGIS_PAGE_SIZE = 2000

OSM_STATIONS_QUERY = f"""
[out:json][timeout:120];
area({KOREA_OSM_AREA_ID})->.kr;
(
  node(area.kr)["railway"~"station|halt"];
  way(area.kr)["railway"~"station|halt"];
  relation(area.kr)["railway"~"station|halt"];
  node(area.kr)["public_transport"="station"]["station"~"subway|train|light_rail"];
  way(area.kr)["public_transport"="station"]["station"~"subway|train|light_rail"];
  relation(area.kr)["public_transport"="station"]["station"~"subway|train|light_rail"];
);
out center tags;
"""

SOURCE_STATIONS = "osm-overpass:kr-railway-stations"
SOURCE_REGIONS = "arcgis-emd:2025-12"
SOURCE_MANUAL = "manual-region"
OWNED_SOURCES = (SOURCE_STATIONS, SOURCE_REGIONS, SOURCE_MANUAL)

PLACE_UPSERT_SQL = """
INSERT INTO places (id, name, place_type, region_code, geom, bbox, source, source_ref, updated_at)
VALUES (
    %s,
    %s,
    %s,
    %s,
    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
    CASE WHEN %s THEN ST_MakeEnvelope(%s, %s, %s, %s, 4326) ELSE NULL END,
    %s,
    %s,
    now()
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    place_type = EXCLUDED.place_type,
    region_code = EXCLUDED.region_code,
    geom = EXCLUDED.geom,
    bbox = EXCLUDED.bbox,
    source = EXCLUDED.source,
    source_ref = EXCLUDED.source_ref,
    updated_at = EXCLUDED.updated_at
"""

ALIAS_INSERT_SQL = """
INSERT INTO place_aliases (place_id, alias, normalized_alias, language, priority)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (place_id, normalized_alias) DO UPDATE SET
    alias = EXCLUDED.alias,
    language = EXCLUDED.language,
    priority = LEAST(place_aliases.priority, EXCLUDED.priority)
"""

DELETE_OWNED_PLACES_SQL = "DELETE FROM places WHERE source = ANY(%s::text[])"

KOREAN_CITY_WITH_GU_RE = re.compile(r"^(?P<city>[가-힣]+시)\s+[가-힣]+구$")

PROVINCE_ALIASES = {
    "서울특별시": ("서울",),
    "부산광역시": ("부산",),
    "대구광역시": ("대구",),
    "인천광역시": ("인천",),
    "광주광역시": ("광주",),
    "대전광역시": ("대전",),
    "울산광역시": ("울산",),
    "세종특별자치시": ("세종",),
    "경기도": ("경기",),
    "강원특별자치도": ("강원",),
    "충청북도": ("충북",),
    "충청남도": ("충남",),
    "전북특별자치도": ("전북", "전라북도"),
    "전라남도": ("전남",),
    "경상북도": ("경북",),
    "경상남도": ("경남",),
    "제주특별자치도": ("제주",),
}


@dataclass(frozen=True)
class AliasSeed:
    alias: str
    language: str = "ko"
    priority: int = 100


@dataclass(frozen=True)
class PlaceSeed:
    place_id: str
    name: str
    place_type: str
    lon: float
    lat: float
    bbox: tuple[float, float, float, float] | None
    region_code: str | None
    source: str
    source_ref: str | None
    aliases: tuple[AliasSeed, ...]


@dataclass(frozen=True)
class SeedSummary:
    place_count: int
    alias_count: int
    station_count: int
    region_count: int


def fetch_osm_station_elements(overpass_url: str = DEFAULT_OVERPASS_URL) -> list[dict[str, Any]]:
    response = httpx.post(overpass_url, data={"data": OSM_STATIONS_QUERY}, timeout=150)
    response.raise_for_status()
    payload = response.json()
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass response must contain elements")
    return [element for element in elements if isinstance(element, dict)]


def fetch_arcgis_emd_features(arcgis_url: str = DEFAULT_ARCGIS_EMD_URL) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "emd_cd,emd_eng_nm,emd_kor_nm,ctprvn_cd,ctp_eng_nm,ctp_kor_nm,sig_cd,sig_eng_nm,sig_kor_nm",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(ARCGIS_PAGE_SIZE),
            "f": "json",
        }
        response = httpx.get(arcgis_url, params=params, timeout=120)
        response.raise_for_status()
        payload = response.json()
        page = payload.get("features")
        if not isinstance(page, list):
            raise ValueError("ArcGIS response must contain features")
        features.extend(feature for feature in page if isinstance(feature, dict))
        if len(page) < ARCGIS_PAGE_SIZE:
            return features
        offset += ARCGIS_PAGE_SIZE


def build_station_places(elements: Iterable[Mapping[str, Any]]) -> list[PlaceSeed]:
    places: list[PlaceSeed] = []
    by_name: dict[str, list[PlaceSeed]] = defaultdict(list)
    for element in elements:
        place = station_place_from_osm_element(element)
        if place is not None:
            key = normalize_place_name(place.name)
            if any(rough_distance_m(place.lon, place.lat, existing.lon, existing.lat) <= 1_000 for existing in by_name[key]):
                continue
            by_name[key].append(place)
            places.append(place)
    return places


def station_place_from_osm_element(element: Mapping[str, Any]) -> PlaceSeed | None:
    tags = element.get("tags")
    if not isinstance(tags, Mapping):
        return None

    lon_lat = osm_lon_lat(element)
    if lon_lat is None:
        return None
    lon, lat = lon_lat

    name_ko = text_or_none(tags.get("name:ko")) or text_or_none(tags.get("name"))
    name_en = text_or_none(tags.get("name:en"))
    if name_ko is None and name_en is None:
        return None

    station_name = station_display_name(name_ko or name_en or "")
    if not station_name:
        return None

    element_type = text_or_none(element.get("type")) or "osm"
    element_id = text_or_none(element.get("id"))
    if element_id is None:
        return None

    aliases = station_aliases(station_name, name_ko, name_en, tags)
    if not aliases:
        return None

    return PlaceSeed(
        place_id=f"osm-{element_type}-{element_id}",
        name=station_name,
        place_type="station",
        lon=lon,
        lat=lat,
        bbox=None,
        region_code=None,
        source=SOURCE_STATIONS,
        source_ref=f"https://www.openstreetmap.org/{element_type}/{element_id}",
        aliases=tuple(aliases),
    )


def station_display_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if re.search(r"[가-힣]", stripped) and not stripped.endswith("역"):
        return f"{stripped}역"
    if re.search(r"[A-Za-z]", stripped) and not stripped.casefold().endswith(" station"):
        return f"{stripped} Station"
    return stripped


def station_aliases(
    station_name: str,
    name_ko: str | None,
    name_en: str | None,
    tags: Mapping[str, Any],
) -> list[AliasSeed]:
    aliases: list[AliasSeed] = [AliasSeed(station_name, priority=10)]
    for value in (name_ko, name_en, text_or_none(tags.get("alt_name:ko")), text_or_none(tags.get("alt_name:en"))):
        if value:
            aliases.append(AliasSeed(value, language=alias_language(value), priority=30))
            aliases.append(AliasSeed(station_display_name(value), language=alias_language(value), priority=20))
    return dedupe_aliases(aliases)


def build_region_places(features: Iterable[Mapping[str, Any]]) -> list[PlaceSeed]:
    subdistricts: list[PlaceSeed] = []
    province_boxes: dict[str, tuple[str, str, str | None, list[tuple[float, float, float, float]]]] = {}
    district_boxes: dict[str, tuple[str, str, str | None, list[tuple[float, float, float, float]]]] = {}
    city_boxes: dict[str, tuple[str, str, str | None, list[tuple[float, float, float, float]]]] = {}

    for feature in features:
        attrs = feature.get("attributes")
        geometry = feature.get("geometry")
        if not isinstance(attrs, Mapping) or not isinstance(geometry, Mapping):
            continue
        bbox = bbox_from_arcgis_geometry(geometry)
        if bbox is None:
            continue

        emd_code = text_or_none(attrs.get("emd_cd"))
        emd_name = text_or_none(attrs.get("emd_kor_nm"))
        emd_eng = text_or_none(attrs.get("emd_eng_nm"))
        ctp_code = text_or_none(attrs.get("ctprvn_cd"))
        ctp_name = text_or_none(attrs.get("ctp_kor_nm"))
        ctp_eng = text_or_none(attrs.get("ctp_eng_nm"))
        sig_code = text_or_none(attrs.get("sig_cd"))
        sig_name = text_or_none(attrs.get("sig_kor_nm"))
        sig_eng = text_or_none(attrs.get("sig_eng_nm"))
        if not all((emd_code, emd_name, ctp_code, ctp_name, sig_code, sig_name)):
            continue

        full_emd_name = f"{ctp_name} {sig_name} {emd_name}"
        lon, lat = bbox_center(bbox)
        subdistricts.append(
            PlaceSeed(
                place_id=f"region-emd-{emd_code}",
                name=full_emd_name,
                place_type="subdistrict",
                lon=lon,
                lat=lat,
                bbox=bbox,
                region_code=emd_code,
                source=SOURCE_REGIONS,
                source_ref=DEFAULT_ARCGIS_EMD_URL,
                aliases=tuple(
                    dedupe_aliases(
                        [
                            AliasSeed(full_emd_name, priority=10),
                            AliasSeed(f"{full_emd_name} 전체", priority=8),
                            AliasSeed(f"{sig_name} {emd_name}", priority=20),
                            AliasSeed(f"{sig_name} {emd_name} 전체", priority=18),
                            AliasSeed(emd_name, priority=90),
                            AliasSeed(f"{emd_name} 전체", priority=88),
                            *(english_aliases(emd_eng, sig_eng, ctp_eng, priority=80)),
                        ]
                    )
                ),
            )
        )

        append_bbox(province_boxes, ctp_code, ctp_name, ctp_eng, bbox)
        append_bbox(district_boxes, sig_code, f"{ctp_name} {sig_name}", sig_eng, bbox)

        city_match = KOREAN_CITY_WITH_GU_RE.match(sig_name)
        if city_match:
            city_name = city_match.group("city")
            append_bbox(city_boxes, f"{ctp_code}-{city_name}", f"{ctp_name} {city_name}", None, bbox)

    places = [*subdistricts]
    places.extend(aggregate_region_places(province_boxes, "province", "region-ctp"))
    places.extend(aggregate_region_places(district_boxes, "district", "region-sig"))
    places.extend(aggregate_region_places(city_boxes, "district", "region-city"))
    places.extend(manual_region_places(places))
    return places


def aggregate_region_places(
    boxes_by_key: Mapping[str, tuple[str, str, str | None, list[tuple[float, float, float, float]]]],
    place_type: str,
    id_prefix: str,
) -> list[PlaceSeed]:
    places: list[PlaceSeed] = []
    for key, (code, name, english_name, boxes) in boxes_by_key.items():
        bbox = union_bboxes(boxes)
        lon, lat = bbox_center(bbox)
        short_name = name.split()[-1]
        aliases = [
            AliasSeed(name, priority=10),
            AliasSeed(f"{name} 전체", priority=8),
            AliasSeed(short_name, priority=50),
            AliasSeed(f"{short_name} 전체", priority=48),
        ]
        if place_type == "province":
            aliases.extend(AliasSeed(alias, priority=20) for alias in PROVINCE_ALIASES.get(name, ()))
            aliases.extend(AliasSeed(f"{alias} 전체", priority=18) for alias in PROVINCE_ALIASES.get(name, ()))
        if english_name:
            aliases.append(AliasSeed(english_name, language="en", priority=80))

        places.append(
            PlaceSeed(
                place_id=f"{id_prefix}-{safe_id(key)}",
                name=name,
                place_type=place_type,
                lon=lon,
                lat=lat,
                bbox=bbox,
                region_code=code,
                source=SOURCE_REGIONS,
                source_ref=DEFAULT_ARCGIS_EMD_URL,
                aliases=tuple(dedupe_aliases(aliases)),
            )
        )
    return places


def manual_region_places(existing_places: Sequence[PlaceSeed]) -> list[PlaceSeed]:
    metropolitan_boxes = [
        place.bbox
        for place in existing_places
        if place.place_type == "province" and place.name in {"서울특별시", "인천광역시", "경기도"} and place.bbox is not None
    ]
    if len(metropolitan_boxes) != 3:
        return []

    bbox = union_bboxes(metropolitan_boxes)
    lon, lat = bbox_center(bbox)
    return [
        PlaceSeed(
            place_id="region-custom-sudogwon",
            name="수도권",
            place_type="province",
            lon=lon,
            lat=lat,
            bbox=bbox,
            region_code="KR-SUDOGWON",
            source=SOURCE_MANUAL,
            source_ref="서울특별시+인천광역시+경기도 aggregate",
            aliases=(
                AliasSeed("수도권", priority=10),
                AliasSeed("수도권 전체", priority=8),
                AliasSeed("서울 경기 인천", priority=20),
                AliasSeed("서울경기인천", priority=20),
            ),
        )
    ]


def seed_places(database_url: str, places: Sequence[PlaceSeed]) -> SeedSummary:
    import psycopg

    alias_rows = alias_params(places)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DELETE_OWNED_PLACES_SQL, (list(OWNED_SOURCES),))
            cursor.executemany(PLACE_UPSERT_SQL, place_params(places))
            cursor.executemany(ALIAS_INSERT_SQL, alias_rows)

    return SeedSummary(
        place_count=len(places),
        alias_count=len(alias_rows),
        station_count=sum(1 for place in places if place.place_type == "station"),
        region_count=sum(1 for place in places if place.place_type != "station"),
    )


def build_places_from_sources(
    *,
    overpass_url: str = DEFAULT_OVERPASS_URL,
    arcgis_emd_url: str = DEFAULT_ARCGIS_EMD_URL,
    include_stations: bool = True,
    include_regions: bool = True,
) -> list[PlaceSeed]:
    places: list[PlaceSeed] = []
    if include_stations:
        places.extend(build_station_places(fetch_osm_station_elements(overpass_url)))
    if include_regions:
        places.extend(build_region_places(fetch_arcgis_emd_features(arcgis_emd_url)))
    return places


def place_params(places: Sequence[PlaceSeed]) -> list[tuple[Any, ...]]:
    params: list[tuple[Any, ...]] = []
    for place in places:
        has_bbox = place.bbox is not None
        west, south, east, north = place.bbox or (None, None, None, None)
        params.append(
            (
                place.place_id,
                place.name,
                place.place_type,
                place.region_code,
                place.lon,
                place.lat,
                has_bbox,
                west,
                south,
                east,
                north,
                place.source,
                place.source_ref,
            )
        )
    return params


def alias_params(places: Sequence[PlaceSeed]) -> list[tuple[str, str, str, str, int]]:
    rows: list[tuple[str, str, str, str, int]] = []
    for place in places:
        for alias in place.aliases:
            normalized = normalize_place_name(alias.alias)
            if normalized:
                rows.append((place.place_id, alias.alias.strip(), normalized, alias.language, alias.priority))
    return rows


def bbox_from_arcgis_geometry(geometry: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    rings = geometry.get("rings")
    if not isinstance(rings, list):
        return None
    points: list[tuple[float, float]] = []
    for ring in rings:
        if not isinstance(ring, list):
            continue
        for point in ring:
            if not isinstance(point, list) or len(point) < 2:
                continue
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def osm_lon_lat(element: Mapping[str, Any]) -> tuple[float, float] | None:
    lon = element.get("lon")
    lat = element.get("lat")
    center = element.get("center")
    if (lon is None or lat is None) and isinstance(center, Mapping):
        lon = center.get("lon")
        lat = center.get("lat")
    try:
        return float(lon), float(lat)
    except (TypeError, ValueError):
        return None


def append_bbox(
    target: dict[str, tuple[str, str, str | None, list[tuple[float, float, float, float]]]],
    code: str,
    name: str,
    english_name: str | None,
    bbox: tuple[float, float, float, float],
) -> None:
    if code not in target:
        target[code] = (code, name, english_name, [])
    target[code][3].append(bbox)


def union_bboxes(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    boxes = list(boxes)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    west, south, east, north = bbox
    return (west + east) / 2, (south + north) / 2


def rough_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2)
    x = (lon2 - lon1) * 111_320 * math.cos(mean_lat)
    y = (lat2 - lat1) * 111_320
    return math.hypot(x, y)


def dedupe_aliases(aliases: Iterable[AliasSeed]) -> list[AliasSeed]:
    best_by_key: dict[str, AliasSeed] = {}
    for alias in aliases:
        clean = alias.alias.strip()
        if not clean:
            continue
        key = normalize_place_name(clean)
        existing = best_by_key.get(key)
        if existing is None or alias.priority < existing.priority:
            best_by_key[key] = AliasSeed(clean, alias.language, alias.priority)
    return sorted(best_by_key.values(), key=lambda item: (item.priority, item.alias))


def english_aliases(*values: str | None, priority: int) -> list[AliasSeed]:
    return [AliasSeed(value, language="en", priority=priority) for value in values if value]


def text_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return None


def alias_language(value: str) -> str:
    return "ko" if re.search(r"[가-힣]", value) else "en"


def safe_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value.strip()).strip("-").lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed DB-backed Korean place lookup rows.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Postgres connection URL")
    parser.add_argument("--overpass-url", default=DEFAULT_OVERPASS_URL, help="Overpass interpreter URL")
    parser.add_argument("--arcgis-emd-url", default=DEFAULT_ARCGIS_EMD_URL, help="ArcGIS EMD query URL")
    parser.add_argument("--skip-stations", action="store_true", help="skip OSM railway station seed")
    parser.add_argument("--skip-regions", action="store_true", help="skip ArcGIS region seed")
    parser.add_argument("--dry-run", action="store_true", help="fetch and parse sources without DB writes")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.skip_stations and args.skip_regions:
        parser.error("at least one source must run")
    if not args.dry_run and not args.database_url:
        parser.error("--database-url or DATABASE_URL is required unless --dry-run is used")

    places = build_places_from_sources(
        overpass_url=args.overpass_url,
        arcgis_emd_url=args.arcgis_emd_url,
        include_stations=not args.skip_stations,
        include_regions=not args.skip_regions,
    )

    if args.dry_run:
        summary = SeedSummary(
            place_count=len(places),
            alias_count=len(alias_params(places)),
            station_count=sum(1 for place in places if place.place_type == "station"),
            region_count=sum(1 for place in places if place.place_type != "station"),
        )
    else:
        summary = seed_places(args.database_url, places)

    print(
        "seeded "
        f"{summary.place_count} places, "
        f"{summary.alias_count} aliases "
        f"({summary.station_count} stations, {summary.region_count} regions)"
    )


if __name__ == "__main__":
    main()
