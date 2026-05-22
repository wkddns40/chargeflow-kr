from __future__ import annotations

from vehicle_profile import SUPPORTED_VEHICLE_CONNECTOR_TYPES, VehicleProfile


def test_vehicle_profile_shape_matches_route_planner_contract() -> None:
    profile = VehicleProfile(
        battery_kwh=77.4,
        current_soc=0.64,
        target_arrival_soc=0.15,
        consumption_kwh_per_km=0.18,
        preferred_connector_types=("DC Combo",),
        max_charging_kw=180.0,
    )

    assert profile.to_dict() == {
        "battery_kwh": 77.4,
        "current_soc": 0.64,
        "target_arrival_soc": 0.15,
        "consumption_kwh_per_km": 0.18,
        "preferred_connector_types": ["DC Combo"],
        "max_charging_kw": 180.0,
    }


def test_supported_vehicle_connector_types_match_local_station_values() -> None:
    assert SUPPORTED_VEHICLE_CONNECTOR_TYPES == ("DC Combo", "AC Type 2", "CHAdeMO")
