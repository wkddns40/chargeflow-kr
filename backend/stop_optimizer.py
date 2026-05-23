"""Stop optimizer data shapes for Phase 6D route planning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Literal, TypeAlias

from vehicle_profile import VehicleConnectorType, VehicleProfile


AvailabilityStatus = Literal["available", "occupied", "offline", "unknown"]
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
