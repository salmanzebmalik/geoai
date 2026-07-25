from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_lang_sam_model
from app.schemas.prediction import ZeroShotPredictionRequest, PredictionResponse
from app.services.storage_service import (
    read_image_from_shared_storage,
    save_geojson_to_shared_storage,
)
from app.services.inference_service import run_zero_shot_detection


router = APIRouter()


@router.post("/zeroshot", response_model=PredictionResponse)
async def predict_zero_shot(
    request: ZeroShotPredictionRequest,
    lang_sam=Depends(get_lang_sam_model),
):
    query_id = request.query_id or str(uuid4())

    print("ML Service: Running Zero-Shot Query:", query_id)

    try:
        image_bytes = read_image_from_shared_storage(
            input_image_path=request.input_image_path,
            output_dir=request.output_dir,
        )

        geojson_dict = run_zero_shot_detection(
            pipeline=lang_sam,
            image_bytes=image_bytes,
            keyword=request.keyword,
        )

        feature_count = len(geojson_dict.get("features", []))

        result_path = save_geojson_to_shared_storage(
            query_id=query_id,
            geojson=geojson_dict,
            output_dir=request.output_dir,
        )

        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="lang-sam",
            prediction_type="zero_shot_detection",
            result_path=result_path,
            feature_count=feature_count,
            summary=f"Found {feature_count} {request.keyword} polygons/clusters",
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failed --- error: {str(e)}",
        )