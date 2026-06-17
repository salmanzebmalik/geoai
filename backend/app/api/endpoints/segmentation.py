from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.database import get_session
from app.schemas.segmentation import (
    FetchImageRequest,
    ImageInfo,
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
)
from app.services.satellite_image_service import fetch_satellite_image_from_titiler
from app.services.segmentation_service import (
    create_prediction,
    get_prediction_by_id,
    get_prediction_history,
)


router = APIRouter()


@router.post("/fetch-image", response_model=ImageInfo)
def fetch_image(
    request: FetchImageRequest,
):
    """
    Fetch and save an image from tiTiler without running ML inference.
    Useful for debugging image fetching.
    """

    try:
        query_id = str(uuid4())

        image_path, image_info = fetch_satellite_image_from_titiler(
            query_id=query_id,
            bbox=request.bbox,
            source_type=request.source_type,
        )

        return image_info

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch satellite image: {str(e)}",
        )


@router.post("/predict", response_model=PredictionResponse)
def predict_segmentation(
    request: PredictionRequest,
    session: Session = Depends(get_session),
):
    """
    Run segmentation prediction.

    Default:
        model_type = "tree"

    For zero-shot:
        model_type = "zeroshot"
        keyword = "solar panel" / "tree" / etc.
    """

    try:
        return create_prediction(request=request, session=session)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}",
        )


@router.get("/results", response_model=list[PredictionHistoryItem])
def get_all_results(
    session: Session = Depends(get_session),
):
    return get_prediction_history(session=session)


@router.get("/results/{query_id}", response_model=PredictionResponse)
def get_result_by_id(
    query_id: UUID,
    session: Session = Depends(get_session),
):
    result = get_prediction_by_id(
        query_id=query_id,
        session=session,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Prediction result not found",
        )

    return result