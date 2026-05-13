from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class SegmentationQuery(SQLModel, table=True):
    __tablename__ = "segmentation_queries"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    north: float
    south: float
    east: float
    west: float

    status: str = Field(default="completed")

    image_url: Optional[str] = None
    image_width: Optional[int] = 512
    image_height: Optional[int] = 512

    prediction_result: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON)
    )

    summary: str

    created_at: datetime = Field(default_factory=datetime.utcnow)