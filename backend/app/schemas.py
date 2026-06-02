from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ----------------------------
# Bounding Box Model
# ----------------------------
class BoundingBox(BaseModel):
    max_lat: float = Field(..., description="Maximum latitude boundary")
    min_lat: float = Field(..., description="Minimum latitude boundary")
    max_lon: float = Field(..., description="Maximum longitude boundary")
    min_lon: float = Field(..., description="Minimum longitude boundary")


# ----------------------------
# Prediction Request Model
# ----------------------------
class PredictionRequest(BaseModel):
    bbox: BoundingBox


# ----------------------------
# Image Metadata Model
# ----------------------------
class ImageInfo(BaseModel):
    image_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = "tiff"


# ----------------------------
# GeoJSON Models
# ----------------------------
class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    name: Optional[str] = None
    features: List[GeoJSONFeature]


# ----------------------------
# Prediction Output Model
# ----------------------------
class PredictionOutput(BaseModel):
    prediction_type: str
    model_name: str
    geojson: GeoJSONFeatureCollection


# ----------------------------
# Full Prediction Response Model
# ----------------------------
class PredictionResponse(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    image: Optional[ImageInfo] = None
    prediction: PredictionOutput
    created_at: datetime


# ----------------------------
# Prediction History Model
# ----------------------------
class PredictionHistoryItem(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    created_at: datetime