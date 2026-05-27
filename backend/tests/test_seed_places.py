from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_places.py"
SPEC = importlib.util.spec_from_file_location("seed_places", SCRIPT_PATH)
assert SPEC is not None
seed_places = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = seed_places
SPEC.loader.exec_module(seed_places)


def test_station_place_from_osm_element_adds_station_aliases() -> None:
    place = seed_places.station_place_from_osm_element(
        {
            "type": "node",
            "id": 1,
            "lat": 37.5572,
            "lon": 126.9237,
            "tags": {
                "name:ko": "홍대입구",
                "name:en": "Hongik Univ",
                "railway": "station",
            },
        }
    )

    assert place is not None
    assert place.place_id == "osm-node-1"
    assert place.name == "홍대입구역"
    assert {alias.alias for alias in place.aliases} >= {"홍대입구역", "홍대입구", "Hongik Univ Station"}


def test_build_region_places_adds_hierarchy_aliases() -> None:
    places = seed_places.build_region_places(
        [
            {
                "attributes": {
                    "emd_cd": "11680101",
                    "emd_kor_nm": "역삼동",
                    "emd_eng_nm": "Yeoksam-dong",
                    "ctprvn_cd": "11",
                    "ctp_kor_nm": "서울특별시",
                    "ctp_eng_nm": "Seoul",
                    "sig_cd": "11680",
                    "sig_kor_nm": "강남구",
                    "sig_eng_nm": "Gangnam-gu",
                },
                "geometry": {
                    "rings": [
                        [
                            [127.02, 37.49],
                            [127.04, 37.49],
                            [127.04, 37.51],
                            [127.02, 37.51],
                            [127.02, 37.49],
                        ]
                    ]
                },
            }
        ]
    )

    by_name = {place.name: place for place in places}
    assert "서울특별시 강남구 역삼동" in by_name
    assert "서울특별시 강남구" in by_name
    assert "서울특별시" in by_name
    assert {alias.alias for alias in by_name["서울특별시 강남구 역삼동"].aliases} >= {"역삼동", "강남구 역삼동"}
    assert {alias.alias for alias in by_name["서울특별시"].aliases} >= {"서울"}
