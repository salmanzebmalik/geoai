from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class GeoJSONGeometry(BaseModel):
    # type: Literal["Polygon"] 
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    name: str
    features: List[GeoJSONFeature]


class PredictionResponse(BaseModel):
    query_id: str
    status: str
    model_name: str
    prediction_type: str
    geojson: GeoJSONFeatureCollection
    summary: str