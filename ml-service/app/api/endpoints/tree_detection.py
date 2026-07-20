from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_segformer_model, get_satlas_tree_model
from app.schemas.prediction import TreePredictionRequest, PredictionResponse
from app.services.storage_service import (
    read_image_from_shared_storage,
    save_geojson_to_shared_storage,
)
from app.services.inference_service import run_tree_detection


router = APIRouter()


def _predict(request: TreePredictionRequest, pipeline, model_name: str) -> PredictionResponse:
    query_id = request.query_id or str(uuid4())
    print("ML Service: Running Tree Detection Query:", query_id)
    try:
        image_bytes = read_image_from_shared_storage(
            input_image_path=request.input_image_path,
            output_dir=request.output_dir,
        )
        bbox = (request.min_lon, request.min_lat, request.max_lon, request.max_lat)

        geojson_dict = run_tree_detection(pipeline=pipeline, image_bytes=image_bytes, bbox_coords=bbox)
        feature_count = len(geojson_dict.get("features", []))

        result_path = save_geojson_to_shared_storage(
            query_id=query_id, geojson=geojson_dict, output_dir=request.output_dir,
        )
        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name=model_name,
            prediction_type="tree_detection",
            result_path=result_path,
            feature_count=feature_count,
            summary=f"Found {feature_count} tree polygons/clusters",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed --- error: {str(e)}")


@router.post("/tree", response_model=PredictionResponse)
async def predict_tree(request: TreePredictionRequest, segformer=Depends(get_segformer_model)):
    return _predict(request, segformer, "tcd-segformer-mit-b2")


@router.post("/tree/satellite", response_model=PredictionResponse)
async def predict_tree_satellite(request: TreePredictionRequest, satlas=Depends(get_satlas_tree_model)):
    return _predict(request, satlas, "satlas-tree-5m")
