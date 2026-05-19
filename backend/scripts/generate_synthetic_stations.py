"""Generate deterministic synthetic charger GeoJSON for map benchmarks."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_COUNT = 7000
DEFAULT_SEED = 42

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_ROOT / "fixtures" / "synthetic-stations-7k.geojson"
PROTECTED_SAMPLE = REPO_ROOT / "frontend" / "public" / "sample-chargers.json"

SOUTH_KOREA_BOUNDS = {
    "west": 124.5,
    "south": 33.0,
    "east": 131.9,
    "north": 38.7,
}

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Area:
    name: str
    address_prefix: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float


@dataclass(frozen=True)
class Region:
    key: str
    share: float
    areas: tuple[Area, ...]


REGIONS = (
    Region(
        "seoul_metro",
        0.50,
        (
            Area("Seoul Gangnam", "Seoul Gangnam-gu Teheran-ro", 127.020, 127.075, 37.490, 37.525),
            Area("Seoul Mapo", "Seoul Mapo-gu World Cup buk-ro", 126.885, 126.940, 37.545, 37.585),
            Area("Seoul Jongno", "Seoul Jongno-gu Sejong-daero", 126.970, 127.020, 37.565, 37.595),
            Area("Incheon Songdo", "Incheon Yeonsu-gu Songdo-dong", 126.625, 126.690, 37.360, 37.405),
            Area("Suwon", "Gyeonggi-do Suwon-si Gwanggyo-ro", 127.015, 127.080, 37.250, 37.315),
            Area("Seongnam Pangyo", "Gyeonggi-do Seongnam-si Pangyo-ro", 127.090, 127.135, 37.380, 37.425),
        ),
    ),
    Region(
        "other_metro",
        0.35,
        (
            Area("Busan Haeundae", "Busan Haeundae-gu Centum jungang-ro", 129.120, 129.175, 35.145, 35.190),
            Area("Daegu Suseong", "Daegu Suseong-gu Dongdaegu-ro", 128.600, 128.660, 35.830, 35.875),
            Area("Daejeon Yuseong", "Daejeon Yuseong-gu Daehak-ro", 127.320, 127.380, 36.340, 36.390),
            Area("Gwangju Sangmu", "Gwangju Seo-gu Sangmujayu-ro", 126.830, 126.890, 35.135, 35.175),
            Area("Ulsan Samsan", "Ulsan Nam-gu Samsan-ro", 129.315, 129.365, 35.525, 35.560),
            Area("Sejong", "Sejong-si Hanuri-daero", 127.240, 127.305, 36.480, 36.525),
        ),
    ),
    Region(
        "jeju",
        0.15,
        (
            Area("Jeju City", "Jeju-si Airport-ro", 126.485, 126.555, 33.480, 33.525),
            Area("Seogwipo", "Seogwipo-si Jungang-ro", 126.540, 126.590, 33.235, 33.270),
            Area("Aewol", "Jeju-si Aewol-eup", 126.300, 126.380, 33.445, 33.485),
        ),
    ),
)

OPERATORS = (
    "Korea Electric Power",
    "Seoul Energy",
    "ChargeFlow Partner",
    "Jeju EV Service",
    "Korea Expressway",
    "Green Charge Korea",
)
CONNECTOR_TYPES = ("DC Combo", "AC Type 2", "CHAdeMO")
STATUS_VALUES = ("available", "occupied", "offline", "unknown")
MAX_KW_BY_CONNECTOR = {
    "DC Combo": (50, 100, 150, 200, 350),
    "AC Type 2": (7, 11, 22),
    "CHAdeMO": (50, 100),
}


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def allocate_region_counts(count: int) -> dict[str, int]:
    raw_counts = [(region.key, count * region.share) for region in REGIONS]
    counts = {key: int(raw) for key, raw in raw_counts}
    remainder = count - sum(counts.values())
    ranked = sorted(raw_counts, key=lambda item: item[1] - int(item[1]), reverse=True)
    for key, _ in ranked[:remainder]:
        counts[key] += 1
    return counts


def region_sequence(count: int, rng: random.Random) -> list[Region]:
    counts = allocate_region_counts(count)
    by_key = {region.key: region for region in REGIONS}
    sequence = [by_key[key] for key, total in counts.items() for _ in range(total)]
    rng.shuffle(sequence)
    return sequence


def point_in_area(area: Area, rng: random.Random) -> tuple[float, float]:
    lon = round(rng.uniform(area.lon_min, area.lon_max), 6)
    lat = round(rng.uniform(area.lat_min, area.lat_max), 6)
    return lon, lat


def generate_feature(index: int, region: Region, rng: random.Random, base_time: datetime) -> dict[str, object]:
    area = rng.choice(region.areas)
    lon, lat = point_in_area(area, rng)
    connector_type = rng.choice(CONNECTOR_TYPES)
    updated_at = base_time - timedelta(minutes=rng.randint(0, 60 * 24 * 14))

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": {
            "charger_id": f"CFL-SYN-{index:05d}",
            "charger_name": f"{area.name} Synthetic Charger {index:05d}",
            "operator": rng.choice(OPERATORS),
            "connector_type": connector_type,
            "max_kw": rng.choice(MAX_KW_BY_CONNECTOR[connector_type]),
            "address": f"{area.address_prefix} {rng.randint(1, 999)}",
            "status": rng.choice(STATUS_VALUES),
            "status_updated_at": updated_at.isoformat(),
        },
    }


def generate_collection(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> dict[str, object]:
    rng = random.Random(seed)
    base_time = datetime(2026, 5, 19, 8, 0, 0, tzinfo=KST)
    features = [
        generate_feature(index, region, rng, base_time)
        for index, region in enumerate(region_sequence(count, rng), start=1)
    ]
    return {"type": "FeatureCollection", "features": features}


def validate_output_path(output_path: Path) -> Path:
    resolved = output_path.resolve()
    if resolved == PROTECTED_SAMPLE.resolve():
        raise ValueError("refusing to overwrite frontend/public/sample-chargers.json")
    return resolved


def write_collection(collection: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate synthetic Korean EV charger GeoJSON.")
    parser.add_argument("--count", type=positive_int, default=DEFAULT_COUNT, help="feature count")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="deterministic random seed")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="output GeoJSON path")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        output_path = validate_output_path(args.out)
    except ValueError as exc:
        parser.error(str(exc))

    collection = generate_collection(count=args.count, seed=args.seed)
    write_collection(collection, output_path)
    print(f"wrote {len(collection['features'])} features to {output_path}")


if __name__ == "__main__":
    main()
