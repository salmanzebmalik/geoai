from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    north: float = Field(..., description="Northern latitude boundary")
    south: float = Field(..., description="Southern latitude boundary")
    east: float = Field(..., description="Eastern longitude boundary")
    west: float = Field(..., description="Western longitude boundary")


class PredictionRequest(BaseModel):
    bbox: BoundingBox


class ImageInfo(BaseModel):
    image_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = "tiff"


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    name: str
    features: List[GeoJSONFeature]


class BuildingFootprintPrediction(BaseModel):
    prediction_type: str = "building_footprint_geojson"
    model_name: str
    geojson: GeoJSONFeatureCollection
    summary: str


class PredictionResponse(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    image: ImageInfo
    prediction: BuildingFootprintPrediction
    created_at: datetime


class PredictionHistoryItem(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    summary: str
    created_at: datetime