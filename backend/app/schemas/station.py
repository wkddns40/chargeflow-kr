from pydantic import BaseModel, Field


class StationProperties(BaseModel):
    charger_id: str
    charger_name: str
    operator: str
    connector_type: str
    max_kw: float = Field(ge=0)
    address: str
    status: str
    status_updated_at: str


class PointGeometry(BaseModel):
    type: str = "Point"
    coordinates: tuple[float, float]


class StationFeature(BaseModel):
    type: str = "Feature"
    geometry: PointGeometry
    properties: StationProperties


class StationFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[StationFeature]
