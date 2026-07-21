from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


SourceType = Literal["satellite", "ortho"]
ModelType = Literal["tree", "tree_satlas", "tree_unet", "tree_deepforest", "zeroshot"]


class BoundingBox(BaseModel):
    min_lat: float = Field(..., description="Minimum latitude boundary")
    max_lat: float = Field(..., description="Maximum latitude boundary")
    min_lon: float = Field(..., description="Minimum longitude boundary")
    max_lon: float = Field(..., description="Maximum longitude boundary")


class PredictionRequest(BaseModel):
    bbox: BoundingBox

    # Default keeps your old behavior.
    # Frontend can omit this and tree detection will run.
    model_type: ModelType = "tree"

    # Only used when model_type = "zeroshot".
    # If omitted, backend sends "tree" as default keyword.
    keyword: Optional[str] = None

    # Optional source selection for tiTiler.
    source_type: SourceType = "satellite"


class FetchImageRequest(BaseModel):
    bbox: BoundingBox
    source_type: SourceType = "satellite"


class ImageInfo(BaseModel):
    image_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = "tiff"


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]

    # Use flexible coordinates because Polygon and MultiPolygon have different nesting.
    coordinates: List[Any]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    name: Optional[str] = None
    features: List[GeoJSONFeature]


class PredictionOutput(BaseModel):
    prediction_type: str
    model_name: str
    result_url: str
    feature_count: int
    summary: Optional[str] = None


class PredictionResponse(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    image: Optional[ImageInfo] = None
    prediction: Optional[PredictionOutput] = None
    created_at: datetime


class PredictionHistoryItem(BaseModel):
    query_id: UUID
    bbox: BoundingBox
    created_at: datetime
    prediction_type: Optional[str] = None
    model_name: Optional[str] = None
    summary: Optional[str] = None