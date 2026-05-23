from __future__ import annotations

import pytest

from vehicle_profile import SUPPORTED_VEHICLE_CONNECTOR_TYPES, VehicleProfile, VehicleProfileError


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


@pytest.mark.parametrize(
    "profile_kwargs",
    [
        {
            "battery_kwh": 58.0,
            "current_soc": 0.0,
            "target_arrival_soc": 0.0,
            "consumption_kwh_per_km": 0.16,
            "preferred_connector_types": ("DC Combo",),
            "max_charging_kw": 120.0,
        },
        {
            "battery_kwh": 99.8,
            "current_soc": 1.0,
            "target_arrival_soc": 1.0,
            "consumption_kwh_per_km": 0.24,
            "preferred_connector_types": ("AC Type 2", "CHAdeMO"),
            "max_charging_kw": 250.0,
        },
    ],
)
def test_valid_vehicle_profiles_accept_route_planner_contract_values(
    profile_kwargs: dict[str, object],
) -> None:
    profile = VehicleProfile(**profile_kwargs)  # type: ignore[arg-type]

    assert profile.to_dict() == {
        **profile_kwargs,
        "preferred_connector_types": list(profile_kwargs["preferred_connector_types"]),
    }


def test_preferred_connector_types_accept_json_style_list() -> None:
    profile = VehicleProfile(
        battery_kwh=77.4,
        current_soc=0.64,
        target_arrival_soc=0.15,
        consumption_kwh_per_km=0.18,
        preferred_connector_types=["DC Combo", "CHAdeMO"],  # type: ignore[arg-type]
        max_charging_kw=180.0,
    )

    assert profile.preferred_connector_types == ("DC Combo", "CHAdeMO")
    assert profile.to_dict()["preferred_connector_types"] == ["DC Combo", "CHAdeMO"]


@pytest.mark.parametrize("battery_kwh", [0, -1, float("nan"), float("inf"), "77.4", True])
def test_invalid_battery_kwh_rejects(battery_kwh: object) -> None:
    with pytest.raises(VehicleProfileError, match="battery_kwh"):
        VehicleProfile(
            battery_kwh=battery_kwh,  # type: ignore[arg-type]
            current_soc=0.64,
            target_arrival_soc=0.15,
            consumption_kwh_per_km=0.18,
            preferred_connector_types=("DC Combo",),
            max_charging_kw=180.0,
        )


@pytest.mark.parametrize("consumption_kwh_per_km", [0, -0.1, float("nan"), float("inf"), "0.18", False, True])
def test_invalid_consumption_kwh_per_km_rejects(consumption_kwh_per_km: object) -> None:
    with pytest.raises(VehicleProfileError, match="consumption_kwh_per_km"):
        VehicleProfile(
            battery_kwh=77.4,
            current_soc=0.64,
            target_arrival_soc=0.15,
            consumption_kwh_per_km=consumption_kwh_per_km,  # type: ignore[arg-type]
            preferred_connector_types=("DC Combo",),
            max_charging_kw=180.0,
        )


@pytest.mark.parametrize("max_charging_kw", [0, -1, float("inf"), "180", True])
def test_invalid_max_charging_kw_rejects(max_charging_kw: object) -> None:
    with pytest.raises(VehicleProfileError, match="max_charging_kw"):
        VehicleProfile(
            battery_kwh=77.4,
            current_soc=0.64,
            target_arrival_soc=0.15,
            consumption_kwh_per_km=0.18,
            preferred_connector_types=("DC Combo",),
            max_charging_kw=max_charging_kw,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "preferred_connector_types",
    [
        (),
        [],
        None,
        "DC Combo",
        b"DC Combo",
        ("",),
        ("   ",),
        (3,),
        (b"DC Combo",),
        ("Tesla NACS",),
        ("DC Combo", "Tesla NACS"),
    ],
)
def test_invalid_preferred_connector_types_rejects(preferred_connector_types: object) -> None:
    with pytest.raises(VehicleProfileError, match="preferred_connector_types"):
        VehicleProfile(
            battery_kwh=77.4,
            current_soc=0.64,
            target_arrival_soc=0.15,
            consumption_kwh_per_km=0.18,
            preferred_connector_types=preferred_connector_types,  # type: ignore[arg-type]
            max_charging_kw=180.0,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_soc", -0.01),
        ("current_soc", 1.01),
        ("current_soc", float("nan")),
        ("current_soc", float("inf")),
        ("current_soc", "0.64"),
        ("current_soc", False),
        ("target_arrival_soc", -0.01),
        ("target_arrival_soc", 1.01),
        ("target_arrival_soc", float("nan")),
        ("target_arrival_soc", float("inf")),
        ("target_arrival_soc", "0.15"),
        ("target_arrival_soc", True),
    ],
)
def test_invalid_soc_rejects(field: str, value: object) -> None:
    kwargs = {
        "battery_kwh": 77.4,
        "current_soc": 0.64,
        "target_arrival_soc": 0.15,
        "consumption_kwh_per_km": 0.18,
        "preferred_connector_types": ("DC Combo",),
        "max_charging_kw": 180.0,
    }
    kwargs[field] = value

    with pytest.raises(VehicleProfileError, match=field):
        VehicleProfile(**kwargs)  # type: ignore[arg-type]


def test_target_arrival_soc_may_exceed_current_soc() -> None:
    profile = VehicleProfile(
        battery_kwh=77.4,
        current_soc=0.2,
        target_arrival_soc=0.8,
        consumption_kwh_per_km=0.18,
        preferred_connector_types=("DC Combo",),
        max_charging_kw=180.0,
    )

    assert profile.target_arrival_soc == 0.8
