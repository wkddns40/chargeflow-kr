"""Stop optimizer data shapes for Phase 6D route planning."""

from __future__ import annotations

import math
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

DEFAULT_MAX_RECOMMENDATIONS = 5
HIGH_POWER_SCORE_THRESHOLD = 0.8
LOW_POWER_SCORE_THRESHOLD = 0.5
FRESH_AVAILABILITY_MAX_AGE = timedelta(days=2)
AGING_AVAILABILITY_MAX_AGE = timedelta(days=7)
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
