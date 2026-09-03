from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from app.models.yolo11_pipeline import YOLO11Pipeline
from app.core.config import settings

router = APIRouter()
pipeline = YOLO11Pipeline()


class YoloPredictionRequest(BaseModel):
    query_id: str
    input_image_path: str
    output_dir: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@router.post("/yolo")
async def predict_yolo(payload: YoloPredictionRequest):
    try:
        # Reconstruct full absolute path using shared storage root
        full_image_path = Path(settings.shared_storage_path) / payload.input_image_path

        detections = pipeline.predict(str(full_image_path))

        return {
            "success": True,
            "query_id": payload.query_id,
            "detections": detections
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))