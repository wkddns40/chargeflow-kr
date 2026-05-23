from __future__ import annotations

import pytest

from stop_optimizer import StopCandidate, estimate_reachable_segment, score_charging_power
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


def candidate(route_distance_km: float, max_kw: float = 150.0) -> StopCandidate:
    return StopCandidate(
        station_id="CFL-SYN-01234",
        name="Synthetic Seoul Fast Charger",
        connector_type="DC Combo",
        max_kw=max_kw,
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


def test_score_charging_power_caps_station_power_at_vehicle_limit() -> None:
    power_score = score_charging_power(candidate(route_distance_km=42.5, max_kw=350.0), vehicle())

    assert power_score.effective_charging_kw == 180.0
    assert power_score.score == 1.0
    assert power_score.reasons == ("high_power",)


def test_score_charging_power_marks_high_power_candidate() -> None:
    power_score = score_charging_power(candidate(route_distance_km=42.5, max_kw=150.0), vehicle())

    assert power_score.effective_charging_kw == 150.0
    assert power_score.score == pytest.approx(150.0 / 180.0, abs=ESTIMATE_TOLERANCE)
    assert power_score.reasons == ("high_power",)


def test_score_charging_power_keeps_mid_power_neutral() -> None:
    power_score = score_charging_power(candidate(route_distance_km=42.5, max_kw=100.0), vehicle())

    assert power_score.effective_charging_kw == 100.0
    assert power_score.score == pytest.approx(100.0 / 180.0, abs=ESTIMATE_TOLERANCE)
    assert power_score.reasons == ()


def test_score_charging_power_marks_low_power_penalty() -> None:
    power_score = score_charging_power(candidate(route_distance_km=42.5, max_kw=50.0), vehicle())

    assert power_score.effective_charging_kw == 50.0
    assert power_score.score == pytest.approx(50.0 / 180.0, abs=ESTIMATE_TOLERANCE)
    assert power_score.reasons == ("low_power_penalty",)


@pytest.mark.parametrize("max_kw", [0, -1, float("nan"), float("inf"), "150", True])
def test_score_charging_power_rejects_invalid_candidate_power(max_kw: object) -> None:
    with pytest.raises(ValueError, match="candidate.max_kw"):
        score_charging_power(candidate(route_distance_km=42.5, max_kw=max_kw), vehicle())  # type: ignore[arg-type]


@pytest.mark.parametrize("max_charging_kw", [0, -1, float("nan"), float("inf"), "180", True])
def test_score_charging_power_rejects_invalid_vehicle_power(max_charging_kw: object) -> None:
    with pytest.raises(ValueError, match="vehicle.max_charging_kw"):
        score_charging_power(
            candidate(route_distance_km=42.5),
            malformed_vehicle(max_charging_kw=max_charging_kw),
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
def test_estimate_reachable_segment_rejects_invalid_soc_floor(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        estimate_reachable_segment(candidate(route_distance_km=42.5), malformed_vehicle(**{field: value}))
