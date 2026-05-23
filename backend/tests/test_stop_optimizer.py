from __future__ import annotations

import pytest

from stop_optimizer import StopCandidate, estimate_reachable_segment
from vehicle_profile import VehicleProfile


ESTIMATE_TOLERANCE = 1e-9


def vehicle() -> VehicleProfile:
    return VehicleProfile(
        battery_kwh=77.4,
        current_soc=0.64,
        target_arrival_soc=0.15,
        consumption_kwh_per_km=0.18,
        preferred_connector_types=("DC Combo",),
        max_charging_kw=180.0,
    )


def malformed_vehicle(**overrides: object) -> VehicleProfile:
    profile = object.__new__(VehicleProfile)
    fields: dict[str, object] = {
        "battery_kwh": 77.4,
        "current_soc": 0.64,
        "target_arrival_soc": 0.15,
        "consumption_kwh_per_km": 0.18,
        "preferred_connector_types": ("DC Combo",),
        "max_charging_kw": 180.0,
    }
    fields.update(overrides)

    for field, value in fields.items():
        object.__setattr__(profile, field, value)

    return profile


def candidate(route_distance_km: float) -> StopCandidate:
    return StopCandidate(
        station_id="CFL-SYN-01234",
        name="Synthetic Seoul Fast Charger",
        connector_type="DC Combo",
        max_kw=150.0,
        distance_from_route_km=0.8,
        route_distance_km=route_distance_km,
        status="available",
    )


def test_estimate_reachable_segment_marks_reachable_candidate() -> None:
    estimate = estimate_reachable_segment(candidate(route_distance_km=42.5), vehicle())

    assert estimate.estimated_energy_kwh == pytest.approx(7.65, abs=ESTIMATE_TOLERANCE)
    assert estimate.soc_delta == pytest.approx(7.65 / 77.4, abs=ESTIMATE_TOLERANCE)
    assert estimate.estimated_arrival_soc == pytest.approx(0.64 - (7.65 / 77.4), abs=ESTIMATE_TOLERANCE)
    assert estimate.target_arrival_soc == 0.15
    assert estimate.reachable is True


def test_estimate_reachable_segment_marks_unreachable_candidate() -> None:
    estimate = estimate_reachable_segment(candidate(route_distance_km=230.0), vehicle())

    assert estimate.estimated_energy_kwh == pytest.approx(41.4, abs=ESTIMATE_TOLERANCE)
    assert estimate.soc_delta == pytest.approx(41.4 / 77.4, abs=ESTIMATE_TOLERANCE)
    assert estimate.estimated_arrival_soc == pytest.approx(0.64 - (41.4 / 77.4), abs=ESTIMATE_TOLERANCE)
    assert estimate.estimated_arrival_soc < estimate.target_arrival_soc
    assert estimate.reachable is False


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
def test_estimate_reachable_segment_rejects_invalid_soc_floor(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        estimate_reachable_segment(candidate(route_distance_km=42.5), malformed_vehicle(**{field: value}))
