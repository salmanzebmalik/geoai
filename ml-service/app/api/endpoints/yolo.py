from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.models.yolo11_pipeline import YOLO11Pipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Instantiate the pipeline on startup
pipeline = YOLO11Pipeline()


class YoloPredictionRequest(BaseModel):
    query_id: str
    input_image_path: str
    output_dir: Optional[str] = None
    min_lon: Optional[float] = None
    min_lat: Optional[float] = None
    max_lon: Optional[float] = None
    max_lat: Optional[float] = None


@router.post("/yolo")
async def predict_yolo(payload: YoloPredictionRequest):
    """Run YOLO11 detection on a raster image from shared storage

    and return a GeoJSON FeatureCollection.
    """
    try:
        # Resolve full absolute path using shared storage root
        full_image_path = Path(settings.shared_storage_path) / payload.input_image_path

        if not full_image_path.exists():
            logger.error(f"Image not found at path: {full_image_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Image file not found: {payload.input_image_path}",
            )

        logger.info(
            f"Processing YOLO11 request for query_id={payload.query_id} on {full_image_path}"
        )

        # Read spatial image file as bytes for the rasterio pipeline
        with open(full_image_path, "rb") as f:
            image_bytes = f.read()

        geojson_results = pipeline.predict_boxes_geojson(image_bytes)

        return geojson_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"YOLO11 prediction failed for query_id={payload.query_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")