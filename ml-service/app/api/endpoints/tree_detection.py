from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_segformer_model
from app.schemas.prediction import TreePredictionRequest, PredictionResponse
from app.schemas.geojson import GeoJSONFeatureCollection
from app.services.storage_service import read_image_from_shared_storage
from app.services.inference_service import run_tree_detection


router = APIRouter()


@router.post("/tree", response_model=PredictionResponse)
async def predict_tree(
    request: TreePredictionRequest,
    segformer=Depends(get_segformer_model),
):
    query_id = request.query_id or str(uuid4())

    print("ML Service: Running Tree Detection Query:", query_id)

    try:
        image_bytes = read_image_from_shared_storage(
            input_image_path=request.input_image_path,
            output_dir=request.output_dir,
        )

        bbox = (
            request.min_lon,
            request.min_lat,
            request.max_lon,
            request.max_lat,
        )

        geojson_dict = run_tree_detection(
            pipeline=segformer,
            image_bytes=image_bytes,
            bbox_coords=bbox,
        )

        feature_collection = GeoJSONFeatureCollection(**geojson_dict)

        return PredictionResponse(
            query_id=query_id,
            status="completed",
            model_name="tcd-segformer-mit-b2",
            prediction_type="tree_detection",
            geojson=feature_collection,
            summary=f"Found {len(feature_collection.features)} tree polygons/clusters",
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failed --- error: {str(e)}",
        )