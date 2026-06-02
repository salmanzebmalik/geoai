from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON, Index, event
from sqlalchemy.exc import IntegrityError


class SegmentationQuery(SQLModel, table=True):
    __tablename__ = "segmentation_queries"

    # Optional: index for created_at
    __table_args__ = (
        Index("idx_created_at", "created_at"),
    )

    # Primary Key
    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)

    # Bounding Box
    max_lat: float
    min_lat: float
    max_lon: float
    min_lon: float

    status: str = Field(default="completed")

    # Optional image info
    image_url: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None

    # ML service prediction result stored as JSON
    prediction_result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ---------------------------
    # Validators for bounding box
    # ---------------------------
    @staticmethod
    def validate_bbox(instance: "SegmentationQuery", *args, **kwargs):
        if instance.min_lat >= instance.max_lat:
            raise ValueError("min_lat must be less than max_lat")
        if instance.min_lon >= instance.max_lon:
            raise ValueError("min_lon must be less than max_lon")
        return instance


# Use SQLAlchemy event to automatically validate before insert
@event.listens_for(SegmentationQuery, "before_insert")
def validate_before_insert(mapper, connection, target):
    SegmentationQuery.validate_bbox(target)


@event.listens_for(SegmentationQuery, "before_update")
def validate_before_update(mapper, connection, target):
    SegmentationQuery.validate_bbox(target)