from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RouteChargingPlanRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    route: Any = None
    vehicle: Any = None
    constraints: Any = None
    reference_time: Any = None

    def to_graph_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RoutePlannerSummary(BaseModel):
    distance_km: float = Field(gt=0)
    estimated_energy_kwh: float = Field(ge=0)
    start_soc: float = Field(ge=0, le=1)
    target_arrival_soc: float = Field(ge=0, le=1)
    minimum_required_soc: float = Field(ge=0)
    reachable_without_stop: bool


class RoutePlannerRecommendation(BaseModel):
    station_id: str
    name: str
    connector_type: str
    max_kw: float = Field(gt=0)
    distance_from_route_km: float = Field(ge=0)
    route_distance_km: float = Field(ge=0)
    estimated_arrival_soc: float
    score: float
    reasons: list[str]


class RoutePlannerResponseMeta(BaseModel):
    source: str
    limitations: list[str]
    snapshot_date: str | None = None
    freshness_label: str | None = None


class RouteChargingPlanResponse(BaseModel):
    route_id: str
    summary: RoutePlannerSummary
    recommendations: list[RoutePlannerRecommendation]
    meta: RoutePlannerResponseMeta
