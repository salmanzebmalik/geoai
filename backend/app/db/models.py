from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Index, event
from sqlmodel import Field, SQLModel
from enum import StrEnum

class PredictionStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    INFERENCING = "inferencing"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
class SegmentationQuery(SQLModel, table=True):
    __tablename__ = "segmentation_queries"

    __table_args__ = (
        Index(
            "idx_created_at", 
            "created_at"
        ),
        Index(
            "idx_segmentation_queries_status_created_at",
            "status",
            "created_at",
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
    )

    # Bounding box
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    # Query status: Queued, Preparing, Inferencing, Postprocessing, Completed, Failed, Cancelled
    status: str = Field(
        default=PredictionStatus.QUEUED.value
    )

    request_payload: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    progress_percent: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    status_message: Optional[str] = None

    error_code: Optional[str] = None
    error_message: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    # Image metadata
    image_url: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None

    # ML result
    prediction_result: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def validate_bbox(instance: "SegmentationQuery") -> None:
        if instance.min_lat >= instance.max_lat:
            raise ValueError("min_lat must be less than max_lat")

        if instance.min_lon >= instance.max_lon:
            raise ValueError("min_lon must be less than max_lon")


@event.listens_for(SegmentationQuery, "before_insert")
def validate_before_insert(mapper, connection, target):
    SegmentationQuery.validate_bbox(target)


@event.listens_for(SegmentationQuery, "before_update")
def validate_before_update(mapper, connection, target):
    SegmentationQuery.validate_bbox(target)