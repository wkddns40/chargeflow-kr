"""Stop optimizer data shapes for Phase 6D route planning."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from numbers import Real
from typing import Any, Literal, TypeAlias, cast

from vehicle_profile import VehicleConnectorType, VehicleProfile


AvailabilityStatus = Literal["available", "occupied", "offline", "unknown"]
FreshnessLabel = Literal["fresh", "aging", "stale", "unknown"]
OptimizerReason = Literal[
    "connector_match",
    "reachable",
    "unreachable_fallback",
    "high_power",
    "low_power_penalty",
    "fresh_availability",
    "aging_availability",
    "stale_availability_penalty",
    "unknown_availability_penalty",
    "occupied_penalty",
    "offline_fallback",
    "short_detour",
    "long_detour_penalty",
    "cluster_duplicate_penalty",
]
ReasonList: TypeAlias = tuple[OptimizerReason, ...]
FallbackEvaluation: TypeAlias = tuple["StopCandidate", "ReachableSegmentEstimate", "AvailabilityScore"]

DEFAULT_MAX_RECOMMENDATIONS = 5
HIGH_POWER_SCORE_THRESHOLD = 0.8
LOW_POWER_SCORE_THRESHOLD = 0.5
CONNECTOR_SCORE_WEIGHT = 0.10
REACHABLE_SCORE_WEIGHT = 0.25
CHARGING_POWER_SCORE_WEIGHT = 0.25
RELIABILITY_SCORE_WEIGHT = 0.30
DETOUR_SCORE_WEIGHT = 0.10
STALE_AVAILABILITY_PENALTY = 0.12
UNKNOWN_FRESHNESS_PENALTY = 0.08
FALLBACK_SCORE_CAP = 0.49
MAX_DETOUR_SCORE_DISTANCE_KM = 3.0
SHORT_DETOUR_THRESHOLD_KM = 1.0
FRESH_AVAILABILITY_MAX_AGE = timedelta(days=2)
AGING_AVAILABILITY_MAX_AGE = timedelta(days=7)
SUPPORTED_FRESHNESS_LABELS: tuple[FreshnessLabel, ...] = (
    "fresh",
    "aging",
    "stale",
    "unknown",
)
SUPPORTED_AVAILABILITY_STATUSES: tuple[AvailabilityStatus, ...] = (
    "available",
    "occupied",
    "offline",
    "unknown",
)
OPTIMIZER_REASON_ALLOWLIST: ReasonList = (
    "connector_match",
    "reachable",
    "unreachable_fallback",
    "high_power",
    "low_power_penalty",
    "fresh_availability",
    "aging_availability",
    "stale_availability_penalty",
    "unknown_availability_penalty",
    "occupied_penalty",
    "offline_fallback",
    "short_detour",
    "long_detour_penalty",
    "cluster_duplicate_penalty",
)


@dataclass(frozen=True)
class StopCandidate:
    station_id: str
    name: str
    connector_type: VehicleConnectorType
    max_kw: float
    distance_from_route_km: float
    route_distance_km: float
    status: AvailabilityStatus = "unknown"
    status_updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "station_id": self.station_id,
            "name": self.name,
            "connector_type": self.connector_type,
            "max_kw": self.max_kw,
            "distance_from_route_km": self.distance_from_route_km,
            "route_distance_km": self.route_distance_km,
            "status": self.status,
        }
        if self.status_updated_at is not None:
            result["status_updated_at"] = self.status_updated_at
        return result


@dataclass(frozen=True)
class ReachableSegmentEstimate:
    route_distance_km: float
    estimated_energy_kwh: float
    soc_delta: float
    estimated_arrival_soc: float
    target_arrival_soc: float
    reachable: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "route_distance_km": self.route_distance_km,
            "estimated_energy_kwh": self.estimated_energy_kwh,
            "soc_delta": self.soc_delta,
            "estimated_arrival_soc": self.estimated_arrival_soc,
            "target_arrival_soc": self.target_arrival_soc,
            "reachable": self.reachable,
        }


@dataclass(frozen=True)
class ChargingPowerScore:
    effective_charging_kw: float
    score: float
    reasons: ReasonList

    def to_dict(self) -> dict[str, float | list[str]]:
        return {
            "effective_charging_kw": self.effective_charging_kw,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AvailabilityScore:
    freshness_label: FreshnessLabel
    score: float
    reasons: ReasonList
    fallback_only: bool

    def to_dict(self) -> dict[str, str | float | bool | list[str]]:
        return {
            "freshness_label": self.freshness_label,
            "score": self.score,
            "reasons": list(self.reasons),
            "fallback_only": self.fallback_only,
        }


@dataclass(frozen=True)
class ReliabilityScore:
    raw_score: float
    weight: float
    score: float
    freshness_label: FreshnessLabel
    fallback_only: bool
    availability_reasons: ReasonList
    candidate_status: AvailabilityStatus
    status_updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_score": self.raw_score,
            "weight": self.weight,
            "score": self.score,
            "freshness_label": self.freshness_label,
            "fallback_only": self.fallback_only,
            "availability_reasons": list(self.availability_reasons),
            "candidate_status": self.candidate_status,
            "status_updated_at": self.status_updated_at,
        }


@dataclass(frozen=True)
class StalePenaltyScore:
    freshness_label: FreshnessLabel
    penalty: float
    adjustment: float
    reasons: ReasonList
    fallback_only: bool

    def to_dict(self) -> dict[str, str | float | bool | list[str]]:
        return {
            "freshness_label": self.freshness_label,
            "penalty": self.penalty,
            "adjustment": self.adjustment,
            "reasons": list(self.reasons),
            "fallback_only": self.fallback_only,
        }


@dataclass(frozen=True)
class FallbackCandidateSelection:
    candidate: StopCandidate
    reachability: ReachableSegmentEstimate
    availability: AvailabilityScore
    reasons: ReasonList

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "reachability": self.reachability.to_dict(),
            "availability": self.availability.to_dict(),
            "reasons": list(self.reasons),
        }


def estimate_reachable_segment(candidate: StopCandidate, vehicle: VehicleProfile) -> ReachableSegmentEstimate:
    if not math.isfinite(candidate.route_distance_km) or candidate.route_distance_km < 0:
        raise ValueError("candidate.route_distance_km must be a finite non-negative number")
    _validate_soc_floor(vehicle.current_soc, "vehicle.current_soc")
    _validate_soc_floor(vehicle.target_arrival_soc, "vehicle.target_arrival_soc")

    estimated_energy_kwh = candidate.route_distance_km * vehicle.consumption_kwh_per_km
    soc_delta = estimated_energy_kwh / vehicle.battery_kwh
    estimated_arrival_soc = vehicle.current_soc - soc_delta

    return ReachableSegmentEstimate(
        route_distance_km=candidate.route_distance_km,
        estimated_energy_kwh=estimated_energy_kwh,
        soc_delta=soc_delta,
        estimated_arrival_soc=estimated_arrival_soc,
        target_arrival_soc=vehicle.target_arrival_soc,
        reachable=estimated_arrival_soc >= vehicle.target_arrival_soc,
    )


def score_availability(candidate: StopCandidate, reference_time: datetime) -> AvailabilityScore:
    status = _validate_availability_status(candidate.status)
    freshness_label = _freshness_label(candidate.status_updated_at, reference_time)

    if status == "available":
        return _score_available_status(freshness_label)
    if status == "occupied":
        return _score_occupied_status(freshness_label)
    if status == "unknown":
        return AvailabilityScore(
            freshness_label=freshness_label,
            score=0.25,
            reasons=("unknown_availability_penalty",),
            fallback_only=False,
        )

    return AvailabilityScore(
        freshness_label=freshness_label,
        score=0.0,
        reasons=("offline_fallback",),
        fallback_only=True,
    )


def score_reliability(candidate: StopCandidate, availability: AvailabilityScore) -> ReliabilityScore:
    candidate_status = _validate_availability_status(candidate.status)
    freshness_label = _validate_freshness_label(availability.freshness_label)
    raw_score = _validate_bounded_score(availability.score, "availability.score")
    score = 0.0 if availability.fallback_only else raw_score * RELIABILITY_SCORE_WEIGHT

    return ReliabilityScore(
        raw_score=raw_score,
        weight=RELIABILITY_SCORE_WEIGHT,
        score=score,
        freshness_label=freshness_label,
        fallback_only=availability.fallback_only,
        availability_reasons=availability.reasons,
        candidate_status=candidate_status,
        status_updated_at=candidate.status_updated_at,
    )


def score_stale_penalty(availability: AvailabilityScore) -> StalePenaltyScore:
    freshness_label = _validate_freshness_label(availability.freshness_label)
    penalty = 0.0
    reasons: list[OptimizerReason] = []

    if freshness_label == "stale":
        penalty = STALE_AVAILABILITY_PENALTY
        reasons.append("stale_availability_penalty")
    elif freshness_label == "unknown":
        penalty = UNKNOWN_FRESHNESS_PENALTY
        reasons.append("unknown_availability_penalty")

    return StalePenaltyScore(
        freshness_label=freshness_label,
        penalty=penalty,
        adjustment=-penalty,
        reasons=tuple(reasons),
        fallback_only=availability.fallback_only,
    )


def select_fallback_candidates(
    evaluations: Iterable[FallbackEvaluation],
    *,
    max_results: int = DEFAULT_MAX_RECOMMENDATIONS,
) -> tuple[FallbackCandidateSelection, ...]:
    limit = _validate_positive_integer(max_results, "max_results")
    items = tuple(evaluations)

    if any(_is_primary_candidate(reachability, availability) for _, reachability, availability in items):
        return ()

    fallback_candidates = [
        FallbackCandidateSelection(
            candidate=candidate,
            reachability=reachability,
            availability=availability,
            reasons=_fallback_reasons(reachability, availability),
        )
        for candidate, reachability, availability in items
        if _fallback_reasons(reachability, availability)
    ]

    return tuple(sorted(fallback_candidates, key=_fallback_sort_key)[:limit])


def score_charging_power(candidate: StopCandidate, vehicle: VehicleProfile) -> ChargingPowerScore:
    _validate_positive_number(candidate.max_kw, "candidate.max_kw")
    _validate_positive_number(vehicle.max_charging_kw, "vehicle.max_charging_kw")

    effective_charging_kw = min(candidate.max_kw, vehicle.max_charging_kw)
    score = effective_charging_kw / vehicle.max_charging_kw
    reasons: list[OptimizerReason] = []

    if score >= HIGH_POWER_SCORE_THRESHOLD:
        reasons.append("high_power")
    elif score < LOW_POWER_SCORE_THRESHOLD:
        reasons.append("low_power_penalty")

    return ChargingPowerScore(
        effective_charging_kw=effective_charging_kw,
        score=score,
        reasons=tuple(reasons),
    )


def _score_available_status(freshness_label: FreshnessLabel) -> AvailabilityScore:
    if freshness_label == "fresh":
        return AvailabilityScore(
            freshness_label=freshness_label,
            score=1.0,
            reasons=("fresh_availability",),
            fallback_only=False,
        )
    if freshness_label == "aging":
        return AvailabilityScore(
            freshness_label=freshness_label,
            score=0.8,
            reasons=("aging_availability",),
            fallback_only=False,
        )
    if freshness_label == "stale":
        return AvailabilityScore(
            freshness_label=freshness_label,
            score=0.45,
            reasons=("stale_availability_penalty",),
            fallback_only=False,
        )

    return AvailabilityScore(
        freshness_label=freshness_label,
        score=0.4,
        reasons=("unknown_availability_penalty",),
        fallback_only=False,
    )


def _score_occupied_status(freshness_label: FreshnessLabel) -> AvailabilityScore:
    reasons: list[OptimizerReason] = ["occupied_penalty"]
    score = 0.35

    if freshness_label == "stale":
        score = 0.25
        reasons.append("stale_availability_penalty")
    elif freshness_label == "unknown":
        score = 0.25
        reasons.append("unknown_availability_penalty")

    return AvailabilityScore(
        freshness_label=freshness_label,
        score=score,
        reasons=tuple(reasons),
        fallback_only=False,
    )


def _freshness_label(status_updated_at: object, reference_time: datetime) -> FreshnessLabel:
    reference = _require_aware_datetime(reference_time, "reference_time")
    if not isinstance(status_updated_at, str) or not status_updated_at.strip():
        return "unknown"

    try:
        observed_at = datetime.fromisoformat(status_updated_at.strip())
    except ValueError:
        return "unknown"

    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        return "unknown"

    age = reference - observed_at
    if age < timedelta(0):
        return "unknown"
    if age <= FRESH_AVAILABILITY_MAX_AGE:
        return "fresh"
    if age <= AGING_AVAILABILITY_MAX_AGE:
        return "aging"
    return "stale"


def _validate_availability_status(value: object) -> AvailabilityStatus:
    if value not in SUPPORTED_AVAILABILITY_STATUSES:
        allowed = ", ".join(SUPPORTED_AVAILABILITY_STATUSES)
        raise ValueError(f"candidate.status must be one of: {allowed}")
    return cast(AvailabilityStatus, value)


def _validate_freshness_label(value: object) -> FreshnessLabel:
    if value not in SUPPORTED_FRESHNESS_LABELS:
        allowed = ", ".join(SUPPORTED_FRESHNESS_LABELS)
        raise ValueError(f"freshness_label must be one of: {allowed}")
    return cast(FreshnessLabel, value)


def _validate_bounded_score(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"{field} must be between 0.0 and 1.0")
    return score


def _validate_positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _is_primary_candidate(reachability: ReachableSegmentEstimate, availability: AvailabilityScore) -> bool:
    return reachability.reachable and not availability.fallback_only


def _fallback_reasons(reachability: ReachableSegmentEstimate, availability: AvailabilityScore) -> ReasonList:
    reasons: list[OptimizerReason] = []
    if not reachability.reachable:
        reasons.append("unreachable_fallback")
    if availability.fallback_only:
        reasons.append("offline_fallback")
    return tuple(reasons)


def _fallback_sort_key(selection: FallbackCandidateSelection) -> tuple[bool, float, float, str]:
    return (
        selection.availability.fallback_only,
        selection.reachability.route_distance_km,
        selection.candidate.distance_from_route_km,
        selection.candidate.station_id,
    )


def _require_aware_datetime(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone")
    return value


def _validate_soc_floor(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(float(value)) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be between 0.0 and 1.0")


def _validate_positive_number(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(float(value)) or value <= 0:
        raise ValueError(f"{field} must be positive")


@dataclass(frozen=True)
class StopOptimizerInput:
    route_id: str
    route_distance_km: float
    vehicle: VehicleProfile
    candidates: tuple[StopCandidate, ...]
    max_results: int = DEFAULT_MAX_RECOMMENDATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_distance_km": self.route_distance_km,
            "vehicle": self.vehicle.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "max_results": self.max_results,
        }


@dataclass(frozen=True)
class StopRecommendation:
    station_id: str
    name: str
    connector_type: VehicleConnectorType
    max_kw: float
    distance_from_route_km: float
    route_distance_km: float
    estimated_arrival_soc: float
    score: float
    reasons: ReasonList

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "connector_type": self.connector_type,
            "max_kw": self.max_kw,
            "distance_from_route_km": self.distance_from_route_km,
            "route_distance_km": self.route_distance_km,
            "estimated_arrival_soc": self.estimated_arrival_soc,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class StopOptimizerSummary:
    distance_km: float
    estimated_energy_kwh: float
    start_soc: float
    target_arrival_soc: float
    minimum_required_soc: float
    reachable_without_stop: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "distance_km": self.distance_km,
            "estimated_energy_kwh": self.estimated_energy_kwh,
            "start_soc": self.start_soc,
            "target_arrival_soc": self.target_arrival_soc,
            "minimum_required_soc": self.minimum_required_soc,
            "reachable_without_stop": self.reachable_without_stop,
        }


@dataclass(frozen=True)
class StopOptimizerResponse:
    route_id: str
    summary: StopOptimizerSummary
    recommendations: tuple[StopRecommendation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "summary": self.summary.to_dict(),
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
        }


@dataclass(frozen=True)
class _CandidateEvaluation:
    candidate: StopCandidate
    reachability: ReachableSegmentEstimate
    charging_power: ChargingPowerScore
    availability: AvailabilityScore
    reliability: ReliabilityScore
    stale_penalty: StalePenaltyScore
    score: float
    reasons: ReasonList

    def to_fallback_evaluation(self) -> FallbackEvaluation:
        return (self.candidate, self.reachability, self.availability)

    def to_recommendation(self) -> StopRecommendation:
        return StopRecommendation(
            station_id=self.candidate.station_id,
            name=self.candidate.name,
            connector_type=self.candidate.connector_type,
            max_kw=self.candidate.max_kw,
            distance_from_route_km=self.candidate.distance_from_route_km,
            route_distance_km=self.candidate.route_distance_km,
            estimated_arrival_soc=self.reachability.estimated_arrival_soc,
            score=self.score,
            reasons=self.reasons,
        )


def build_stop_optimizer_response(
    optimizer_input: StopOptimizerInput,
    reference_time: datetime,
) -> StopOptimizerResponse:
    limit = _validate_positive_integer(optimizer_input.max_results, "max_results")
    summary = _build_optimizer_summary(optimizer_input.route_distance_km, optimizer_input.vehicle)
    reference = _require_aware_datetime(reference_time, "reference_time")
    evaluations = tuple(
        _score_candidate(candidate, optimizer_input.vehicle, reference)
        for candidate in optimizer_input.candidates
        if _connector_matches(candidate, optimizer_input.vehicle)
    )

    primary_recommendations = tuple(
        evaluation.to_recommendation()
        for evaluation in evaluations
        if _is_primary_candidate(evaluation.reachability, evaluation.availability)
    )

    if primary_recommendations:
        recommendations = tuple(sorted(primary_recommendations, key=_recommendation_sort_key)[:limit])
    else:
        fallback_selections = select_fallback_candidates(
            (evaluation.to_fallback_evaluation() for evaluation in evaluations),
            max_results=limit,
        )
        fallback_recommendations = tuple(
            recommendation
            for selection in fallback_selections
            for recommendation in (_recommendation_for_selection(selection, evaluations),)
            if recommendation is not None
        )
        recommendations = tuple(
            sorted(fallback_recommendations, key=_recommendation_sort_key)[:limit]
        )

    return StopOptimizerResponse(
        route_id=optimizer_input.route_id,
        summary=summary,
        recommendations=recommendations,
    )


def _build_optimizer_summary(route_distance_km: float, vehicle: VehicleProfile) -> StopOptimizerSummary:
    _validate_positive_number(route_distance_km, "route_distance_km")
    estimated_energy_kwh = route_distance_km * vehicle.consumption_kwh_per_km
    soc_delta = estimated_energy_kwh / vehicle.battery_kwh
    minimum_required_soc = vehicle.target_arrival_soc + soc_delta
    estimated_arrival_soc = vehicle.current_soc - soc_delta

    return StopOptimizerSummary(
        distance_km=route_distance_km,
        estimated_energy_kwh=estimated_energy_kwh,
        start_soc=vehicle.current_soc,
        target_arrival_soc=vehicle.target_arrival_soc,
        minimum_required_soc=minimum_required_soc,
        reachable_without_stop=estimated_arrival_soc >= vehicle.target_arrival_soc,
    )


def _score_candidate(
    candidate: StopCandidate,
    vehicle: VehicleProfile,
    reference_time: datetime,
) -> _CandidateEvaluation:
    reachability = estimate_reachable_segment(candidate, vehicle)
    charging_power = score_charging_power(candidate, vehicle)
    availability = score_availability(candidate, reference_time)
    reliability = score_reliability(candidate, availability)
    stale_penalty = score_stale_penalty(availability)
    detour_score, detour_reasons = _score_detour(candidate.distance_from_route_km)
    score = _cap_fallback_score(
        _clamp_score(
            CONNECTOR_SCORE_WEIGHT
            + (REACHABLE_SCORE_WEIGHT if reachability.reachable else 0.0)
            + (charging_power.score * CHARGING_POWER_SCORE_WEIGHT)
            + reliability.score
            + (detour_score * DETOUR_SCORE_WEIGHT)
            + stale_penalty.adjustment
        ),
        reachability,
        availability,
    )
    reasons = _merge_reasons(
        ("connector_match",),
        ("reachable",) if reachability.reachable else ("unreachable_fallback",),
        charging_power.reasons,
        availability.reasons,
        stale_penalty.reasons,
        detour_reasons,
    )

    return _CandidateEvaluation(
        candidate=candidate,
        reachability=reachability,
        charging_power=charging_power,
        availability=availability,
        reliability=reliability,
        stale_penalty=stale_penalty,
        score=score,
        reasons=reasons,
    )


def _recommendation_for_selection(
    selection: FallbackCandidateSelection,
    evaluations: tuple[_CandidateEvaluation, ...],
) -> StopRecommendation | None:
    for evaluation in evaluations:
        if evaluation.candidate == selection.candidate:
            return evaluation.to_recommendation()
    return None


def _score_detour(distance_from_route_km: float) -> tuple[float, ReasonList]:
    _validate_non_negative_number(distance_from_route_km, "candidate.distance_from_route_km")
    detour_score = max(
        0.0,
        1.0 - min(distance_from_route_km, MAX_DETOUR_SCORE_DISTANCE_KM) / MAX_DETOUR_SCORE_DISTANCE_KM,
    )
    if distance_from_route_km <= SHORT_DETOUR_THRESHOLD_KM:
        return detour_score, ("short_detour",)
    return detour_score, ("long_detour_penalty",)


def _merge_reasons(*reason_groups: ReasonList) -> ReasonList:
    reasons: list[OptimizerReason] = []
    for group in reason_groups:
        for reason in group:
            if reason not in reasons:
                reasons.append(reason)
    return tuple(reasons)


def _recommendation_sort_key(recommendation: StopRecommendation) -> tuple[float, float, float, str]:
    return (
        -recommendation.score,
        recommendation.route_distance_km,
        recommendation.distance_from_route_km,
        recommendation.station_id,
    )


def _connector_matches(candidate: StopCandidate, vehicle: VehicleProfile) -> bool:
    return candidate.connector_type in vehicle.preferred_connector_types


def _validate_non_negative_number(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{field} must be non-negative")


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _cap_fallback_score(
    score: float,
    reachability: ReachableSegmentEstimate,
    availability: AvailabilityScore,
) -> float:
    if not _is_primary_candidate(reachability, availability):
        return min(score, FALLBACK_SCORE_CAP)
    return score
