from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import (
    acquire_inference_slot,
    get_prithvi_water_model,
)
from app.schemas.prediction import TreePredictionRequest, PredictionResponse
from app.services.inference_service import run_water_detection
from app.services.storage_service import (
    read_image_from_shared_storage,
    save_geojson_to_shared_storage,
)

router = APIRouter()


@router.post("/water/prithvi", response_model=PredictionResponse)
def predict_water_prithvi(
    request: TreePredictionRequest,
    prithvi=Depends(get_prithvi_water_model),
    _inference_slot=Depends(acquire_inference_slot),
):
    query_id = request.query_id or str(uuid4())
    print("ML Service: Running Water Detection Query:", query_id)
    try:
        image_bytes = read_image_from_shared_storage(
            input_image_path=request.input_image_path,
            output_dir=request.output_dir,
        )

        geojson_dict = run_water_detection(prithvi, image_bytes)
        feature_count = len(geojson_dict.get("features", []))

        result_path = save_geojson_to_shared_storage(
            query_id=query_id, geojson=geojson_dict, output_dir=request.output_dir,
        )
        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="prithvi-eo-v2-300m-sen1floods11",
            prediction_type="water_detection",
            result_path=result_path,
            feature_count=feature_count,
            summary=f"Found {feature_count} water polygons",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed --- error: {str(e)}")
