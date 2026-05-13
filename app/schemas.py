from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Bounding Box -> how the front-end should structure it and why?
class BoundingBox(BaseModel):
    north: float = Field(..., description="Northern latitude boundary")
    south: float = Field(..., description="Southern latitude boundary")
    east: float = Field(..., description="Eastern longitude boundary")
    west: float = Field(..., description="Western longitude boundary")


class SegmentationRequest(BaseModel):
    bbox: BoundingBox


class ImageInfo(BaseModel):
    image_url: Optional[str] = Field(
        default=None,
        description="URL of the satellite image used for prediction"
    )
    width: Optional[int] = Field(
        default=512,
        description="Image width in pixels"
    )
    height: Optional[int] = Field(
        default=512,
        description="Image height in pixels"
    )


class SegmentationClassResult(BaseModel):
    class_name: str = Field(..., description="Predicted class name")
    coverage_percent: float = Field(
        ...,
        description="Percentage of the selected area covered by this class"
    )


class SegmentationPrediction(BaseModel):
    task: str = Field(default="semantic_segmentation")
    model_name: str = Field(default="default_land_cover_segmentation")
    classes: List[SegmentationClassResult]
    mask_url: Optional[str] = Field(
        default=None,
        description="URL of the segmentation mask image"
    )
    summary: str


class SegmentationResponse(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    image: ImageInfo
    prediction: SegmentationPrediction
    created_at: datetime


class SegmentationHistoryItem(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    summary: str
    created_at: datetime