from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import acquire_inference_slot, get_yolo11_model
from app.schemas.prediction import PredictionResponse
from app.services.storage_service import (
    read_image_from_shared_storage,
    save_geojson_to_shared_storage,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class YoloPredictionRequest(BaseModel):
    query_id: Optional[str] = None
    input_image_path: str
    output_dir: Optional[str] = None
    min_lon: Optional[float] = None
    min_lat: Optional[float] = None
    max_lon: Optional[float] = None
    max_lat: Optional[float] = None


@router.post("/yolo", response_model=PredictionResponse)
def predict_yolo(
    payload: YoloPredictionRequest,
    yolo11=Depends(get_yolo11_model),
    _inference_slot=Depends(acquire_inference_slot),
):
    """Run YOLO11 detection on a raster from shared storage and store the GeoJSON."""
    query_id = payload.query_id or str(uuid4())

    try:
        logger.info(f"YOLO11 query {query_id} on {payload.input_image_path}")

        image_bytes = read_image_from_shared_storage(
            input_image_path=payload.input_image_path,
            output_dir=payload.output_dir,
        )

        geojson_dict = yolo11.predict_boxes_geojson(image_bytes)
        feature_count = len(geojson_dict.get("features", []))

        result_path = save_geojson_to_shared_storage(
            query_id=query_id,
            geojson=geojson_dict,
            output_dir=payload.output_dir,
        )

        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="yolo11",
            prediction_type="object_detection",
            result_path=result_path,
            feature_count=feature_count,
            summary=f"Found {feature_count} objects",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YOLO11 prediction failed for query_id={query_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
