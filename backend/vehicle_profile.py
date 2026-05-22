"""Vehicle profile structures for Phase 6D route planning."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Any, Literal, cast


VehicleConnectorType = Literal["DC Combo", "AC Type 2", "CHAdeMO"]
SUPPORTED_VEHICLE_CONNECTOR_TYPES: tuple[VehicleConnectorType, ...] = (
    "DC Combo",
    "AC Type 2",
    "CHAdeMO",
)


class VehicleProfileError(ValueError):
    """Raised when a vehicle profile does not match route planning constraints."""


@dataclass(frozen=True)
class VehicleProfile:
    battery_kwh: float
    current_soc: float
    target_arrival_soc: float
    consumption_kwh_per_km: float
    preferred_connector_types: tuple[VehicleConnectorType, ...]
    max_charging_kw: float

    def __post_init__(self) -> None:
        _validate_positive_number(self.battery_kwh, "battery_kwh")
        _validate_soc(self.current_soc, "current_soc")
        _validate_soc(self.target_arrival_soc, "target_arrival_soc")
        _validate_positive_number(self.consumption_kwh_per_km, "consumption_kwh_per_km")
        object.__setattr__(
            self,
            "preferred_connector_types",
            _normalize_connector_preferences(self.preferred_connector_types),
        )
        _validate_positive_number(self.max_charging_kw, "max_charging_kw")

    def to_dict(self) -> dict[str, Any]:
        return {
            "battery_kwh": self.battery_kwh,
            "current_soc": self.current_soc,
            "target_arrival_soc": self.target_arrival_soc,
            "consumption_kwh_per_km": self.consumption_kwh_per_km,
            "preferred_connector_types": list(self.preferred_connector_types),
            "max_charging_kw": self.max_charging_kw,
        }


def _validate_positive_number(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise VehicleProfileError(f"{field} must be a number")
    if not math.isfinite(float(value)) or value <= 0:
        raise VehicleProfileError(f"{field} must be positive")


def _validate_soc(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise VehicleProfileError(f"{field} must be a number")
    if not math.isfinite(float(value)) or not 0.0 <= value <= 1.0:
        raise VehicleProfileError(f"{field} must be between 0.0 and 1.0")


def _normalize_connector_preferences(value: object) -> tuple[VehicleConnectorType, ...]:
    field = "preferred_connector_types"
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise VehicleProfileError(f"{field} must be a sequence")
    if len(value) == 0:
        raise VehicleProfileError(f"{field} must include at least one connector")

    connectors: list[VehicleConnectorType] = []
    for connector in value:
        if not isinstance(connector, str) or not connector.strip():
            raise VehicleProfileError(f"{field} must contain connector strings")
        normalized = connector.strip()
        if normalized not in SUPPORTED_VEHICLE_CONNECTOR_TYPES:
            raise VehicleProfileError(f"unsupported {field}: {connector}")
        connectors.append(cast(VehicleConnectorType, normalized))

    return tuple(connectors)
