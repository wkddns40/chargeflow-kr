"""Vehicle profile structures for Phase 6D route planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


VehicleConnectorType = Literal["DC Combo", "AC Type 2", "CHAdeMO"]
SUPPORTED_VEHICLE_CONNECTOR_TYPES: tuple[VehicleConnectorType, ...] = (
    "DC Combo",
    "AC Type 2",
    "CHAdeMO",
)


@dataclass(frozen=True)
class VehicleProfile:
    battery_kwh: float
    current_soc: float
    target_arrival_soc: float
    consumption_kwh_per_km: float
    preferred_connector_types: tuple[VehicleConnectorType, ...]
    max_charging_kw: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "battery_kwh": self.battery_kwh,
            "current_soc": self.current_soc,
            "target_arrival_soc": self.target_arrival_soc,
            "consumption_kwh_per_km": self.consumption_kwh_per_km,
            "preferred_connector_types": list(self.preferred_connector_types),
            "max_charging_kw": self.max_charging_kw,
        }
