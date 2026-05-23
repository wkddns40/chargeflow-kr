from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

import pytest

from stop_optimizer import (
    AvailabilityScore,
    AvailabilityStatus,
    FreshnessLabel,
    RELIABILITY_SCORE_WEIGHT,
    STALE_AVAILABILITY_PENALTY,
    StopCandidate,
    UNKNOWN_FRESHNESS_PENALTY,
    estimate_reachable_segment,
    score_availability,
    score_charging_power,
    score_reliability,
    score_stale_penalty,
)
from vehicle_profile import VehicleProfile


ESTIMATE_TOLERANCE = 1e-9
REFERENCE_TIME = datetime(2026, 5, 24, 0, 0, tzinfo=timezone.utc)


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


def candidate(
    route_distance_km: float,
    max_kw: float = 150.0,
    status: AvailabilityStatus = "available",
    status_updated_at: str | None = None,
) -> StopCandidate:
    return StopCandidate(
        station_id="CFL-SYN-01234",
        name="Synthetic Seoul Fast Charger",
        connector_type="DC Combo",
        max_kw=max_kw,
        distance_from_route_km=0.8,
        route_distance_km=route_distance_km,
        status=status,
        status_updated_at=status_updated_at,
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
    ("status_updated_at", "freshness_label", "expected_score", "expected_reasons"),
    [
        ("2026-05-23T00:00:00+00:00", "fresh", 1.0, ("fresh_availability",)),
        ("2026-05-20T00:00:00+00:00", "aging", 0.8, ("aging_availability",)),
        ("2026-05-16T00:00:00+00:00", "stale", 0.45, ("stale_availability_penalty",)),
        (None, "unknown", 0.4, ("unknown_availability_penalty",)),
        ("not-a-timestamp", "unknown", 0.4, ("unknown_availability_penalty",)),
        ("2026-05-25T00:00:00+00:00", "unknown", 0.4, ("unknown_availability_penalty",)),
    ],
)
def test_score_availability_scores_available_by_freshness(
    status_updated_at: str | None,
    freshness_label: str,
    expected_score: float,
    expected_reasons: tuple[str, ...],
) -> None:
    availability = score_availability(
        candidate(route_distance_km=42.5, status="available", status_updated_at=status_updated_at),
        REFERENCE_TIME,
    )

    assert availability.freshness_label == freshness_label
    assert availability.score == expected_score
    assert availability.reasons == expected_reasons
    assert availability.fallback_only is False


@pytest.mark.parametrize(
    ("status_updated_at", "freshness_label", "expected_score", "expected_reasons"),
    [
        ("2026-05-23T00:00:00+00:00", "fresh", 0.35, ("occupied_penalty",)),
        ("2026-05-20T00:00:00+00:00", "aging", 0.35, ("occupied_penalty",)),
        (
            "2026-05-16T00:00:00+00:00",
            "stale",
            0.25,
            ("occupied_penalty", "stale_availability_penalty"),
        ),
        (None, "unknown", 0.25, ("occupied_penalty", "unknown_availability_penalty")),
    ],
)
def test_score_availability_scores_occupied_by_freshness(
    status_updated_at: str | None,
    freshness_label: str,
    expected_score: float,
    expected_reasons: tuple[str, ...],
) -> None:
    availability = score_availability(
        candidate(route_distance_km=42.5, status="occupied", status_updated_at=status_updated_at),
        REFERENCE_TIME,
    )

    assert availability.freshness_label == freshness_label
    assert availability.score == expected_score
    assert availability.reasons == expected_reasons
    assert availability.fallback_only is False


def test_score_availability_scores_unknown_status_below_known_non_offline_states() -> None:
    availability = score_availability(
        candidate(route_distance_km=42.5, status="unknown", status_updated_at="2026-05-23T00:00:00+00:00"),
        REFERENCE_TIME,
    )

    assert availability.freshness_label == "fresh"
    assert availability.score == 0.25
    assert availability.reasons == ("unknown_availability_penalty",)
    assert availability.fallback_only is False


def test_score_availability_marks_offline_as_fallback_only() -> None:
    availability = score_availability(
        candidate(route_distance_km=42.5, status="offline", status_updated_at="2026-05-23T00:00:00+00:00"),
        REFERENCE_TIME,
    )

    assert availability.freshness_label == "fresh"
    assert availability.score == 0.0
    assert availability.reasons == ("offline_fallback",)
    assert availability.fallback_only is True


def test_score_availability_orders_available_before_unavailable_statuses() -> None:
    scored_candidates = [
        (
            "available",
            score_availability(
                candidate(
                    route_distance_km=42.5,
                    status="available",
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
                REFERENCE_TIME,
            ),
        ),
        (
            "occupied",
            score_availability(
                candidate(
                    route_distance_km=42.5,
                    status="occupied",
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
                REFERENCE_TIME,
            ),
        ),
        (
            "unknown",
            score_availability(
                candidate(
                    route_distance_km=42.5,
                    status="unknown",
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
                REFERENCE_TIME,
            ),
        ),
        (
            "offline",
            score_availability(
                candidate(
                    route_distance_km=42.5,
                    status="offline",
                    status_updated_at="2026-05-23T00:00:00+00:00",
                ),
                REFERENCE_TIME,
            ),
        ),
    ]

    ordered_statuses = [
        status for status, _ in sorted(scored_candidates, key=lambda item: item[1].score, reverse=True)
    ]

    assert ordered_statuses == ["available", "occupied", "unknown", "offline"]
    assert [score.fallback_only for _, score in scored_candidates] == [False, False, False, True]


def test_score_availability_orders_stale_available_above_unavailable_candidates() -> None:
    stale_available = score_availability(
        candidate(route_distance_km=42.5, status="available", status_updated_at="2026-05-16T00:00:00+00:00"),
        REFERENCE_TIME,
    )
    fresh_occupied = score_availability(
        candidate(route_distance_km=42.5, status="occupied", status_updated_at="2026-05-23T00:00:00+00:00"),
        REFERENCE_TIME,
    )
    unknown_status = score_availability(
        candidate(route_distance_km=42.5, status="unknown", status_updated_at="2026-05-23T00:00:00+00:00"),
        REFERENCE_TIME,
    )
    offline = score_availability(
        candidate(route_distance_km=42.5, status="offline", status_updated_at="2026-05-23T00:00:00+00:00"),
        REFERENCE_TIME,
    )

    assert stale_available.score > fresh_occupied.score > unknown_status.score > offline.score
    assert stale_available.fallback_only is False
    assert offline.fallback_only is True


def test_score_reliability_weights_available_candidate() -> None:
    station = candidate(
        route_distance_km=42.5,
        status="available",
        status_updated_at="2026-05-23T00:00:00+00:00",
    )
    availability = score_availability(station, REFERENCE_TIME)

    reliability = score_reliability(station, availability)

    assert reliability.raw_score == 1.0
    assert reliability.weight == RELIABILITY_SCORE_WEIGHT
    assert reliability.score == pytest.approx(1.0 * RELIABILITY_SCORE_WEIGHT, abs=ESTIMATE_TOLERANCE)
    assert reliability.freshness_label == "fresh"
    assert reliability.availability_reasons == ("fresh_availability",)
    assert reliability.candidate_status == "available"
    assert reliability.status_updated_at == "2026-05-23T00:00:00+00:00"


def test_score_reliability_preserves_availability_ordering() -> None:
    fresh_available = candidate(
        route_distance_km=42.5,
        status="available",
        status_updated_at="2026-05-23T00:00:00+00:00",
    )
    stale_available = candidate(
        route_distance_km=42.5,
        status="available",
        status_updated_at="2026-05-16T00:00:00+00:00",
    )
    fresh_occupied = candidate(
        route_distance_km=42.5,
        status="occupied",
        status_updated_at="2026-05-23T00:00:00+00:00",
    )

    reliability_scores = [
        score_reliability(station, score_availability(station, REFERENCE_TIME)).score
        for station in (fresh_available, stale_available, fresh_occupied)
    ]

    assert reliability_scores[0] > reliability_scores[1] > reliability_scores[2]


def test_score_reliability_keeps_offline_fallback_zero_weighted() -> None:
    station = candidate(
        route_distance_km=42.5,
        status="offline",
        status_updated_at="2026-05-23T00:00:00+00:00",
    )
    availability = score_availability(station, REFERENCE_TIME)

    reliability = score_reliability(station, availability)

    assert reliability.raw_score == 0.0
    assert reliability.score == 0.0
    assert reliability.fallback_only is True
    assert reliability.availability_reasons == ("offline_fallback",)
    assert reliability.to_dict() == {
        "raw_score": 0.0,
        "weight": RELIABILITY_SCORE_WEIGHT,
        "score": 0.0,
        "freshness_label": "fresh",
        "fallback_only": True,
        "availability_reasons": ["offline_fallback"],
        "candidate_status": "offline",
        "status_updated_at": "2026-05-23T00:00:00+00:00",
    }


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf"), "1.0", True])
def test_score_reliability_rejects_invalid_availability_score(score: object) -> None:
    with pytest.raises(ValueError, match="availability.score"):
        score_reliability(
            candidate(route_distance_km=42.5),
            AvailabilityScore(
                freshness_label="fresh",
                score=score,  # type: ignore[arg-type]
                reasons=("fresh_availability",),
                fallback_only=False,
            ),
        )


@pytest.mark.parametrize(
    ("freshness_label", "reasons"),
    [
        ("fresh", ("fresh_availability",)),
        ("aging", ("aging_availability",)),
    ],
)
def test_score_stale_penalty_keeps_fresh_and_aging_neutral(
    freshness_label: FreshnessLabel,
    reasons: tuple[str, ...],
) -> None:
    stale_penalty = score_stale_penalty(
        AvailabilityScore(
            freshness_label=freshness_label,
            score=1.0,
            reasons=reasons,  # type: ignore[arg-type]
            fallback_only=False,
        )
    )

    assert stale_penalty.penalty == 0.0
    assert stale_penalty.adjustment == 0.0
    assert stale_penalty.reasons == ()
    assert stale_penalty.fallback_only is False


def test_score_stale_penalty_applies_stale_adjustment() -> None:
    stale_penalty = score_stale_penalty(
        AvailabilityScore(
            freshness_label="stale",
            score=0.45,
            reasons=("stale_availability_penalty",),
            fallback_only=False,
        )
    )

    assert stale_penalty.freshness_label == "stale"
    assert stale_penalty.penalty == STALE_AVAILABILITY_PENALTY
    assert stale_penalty.adjustment == -STALE_AVAILABILITY_PENALTY
    assert stale_penalty.reasons == ("stale_availability_penalty",)
    assert stale_penalty.fallback_only is False


def test_score_stale_penalty_applies_unknown_freshness_adjustment() -> None:
    stale_penalty = score_stale_penalty(
        AvailabilityScore(
            freshness_label="unknown",
            score=0.4,
            reasons=("unknown_availability_penalty",),
            fallback_only=False,
        )
    )

    assert stale_penalty.freshness_label == "unknown"
    assert stale_penalty.penalty == UNKNOWN_FRESHNESS_PENALTY
    assert stale_penalty.adjustment == -UNKNOWN_FRESHNESS_PENALTY
    assert stale_penalty.reasons == ("unknown_availability_penalty",)
    assert stale_penalty.fallback_only is False


def test_score_stale_penalty_preserves_fallback_only() -> None:
    stale_penalty = score_stale_penalty(
        AvailabilityScore(
            freshness_label="stale",
            score=0.0,
            reasons=("offline_fallback",),
            fallback_only=True,
        )
    )

    assert stale_penalty.penalty == STALE_AVAILABILITY_PENALTY
    assert stale_penalty.adjustment == -STALE_AVAILABILITY_PENALTY
    assert stale_penalty.fallback_only is True
    assert stale_penalty.to_dict() == {
        "freshness_label": "stale",
        "penalty": STALE_AVAILABILITY_PENALTY,
        "adjustment": -STALE_AVAILABILITY_PENALTY,
        "reasons": ["stale_availability_penalty"],
        "fallback_only": True,
    }


def test_score_stale_penalty_rejects_invalid_freshness_label() -> None:
    with pytest.raises(ValueError, match="freshness_label"):
        score_stale_penalty(
            AvailabilityScore(
                freshness_label=cast(FreshnessLabel, "future"),
                score=0.4,
                reasons=("unknown_availability_penalty",),
                fallback_only=False,
            )
        )


def test_score_availability_rejects_invalid_status() -> None:
    with pytest.raises(ValueError, match="candidate.status"):
        score_availability(
            candidate(route_distance_km=42.5, status=cast(AvailabilityStatus, "maintenance")),
            REFERENCE_TIME,
        )


def test_score_availability_rejects_naive_reference_time() -> None:
    with pytest.raises(ValueError, match="reference_time"):
        score_availability(
            candidate(route_distance_km=42.5, status_updated_at="2026-05-23T00:00:00+00:00"),
            datetime(2026, 5, 24, 0, 0),
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
