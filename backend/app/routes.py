from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.db_models import SegmentationQuery
from app.schemas import (
    BoundingBox,
    ImageInfo,
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
    PredictionOutput,
)
from app.services import create_prediction  # your ML service handler
from app.satellite_image_service import fetch_satellite_image_from_titiler

router = APIRouter(
    prefix="/api/segmentation",
    tags=["segmentation prediction"],
)

# ----------------------------
# New route: fetch & save image only
# ----------------------------
@router.post("/fetch-image", response_model=ImageInfo)
def fetch_image(
    bbox: BoundingBox,
    session: Session = Depends(get_session),  # optional, in case you want to log requests
):
    """
    Given a bounding box, fetch the satellite image via tiTiler
    and save it in the static folder.
    """
    try:
        # Generate a unique query ID for naming
        from uuid import uuid4
        query_id = str(uuid4())

        # Call the satellite image service
        image_path, image_info = fetch_satellite_image_from_titiler(
            query_id=query_id,
            bbox=bbox,
            source_type="satellite"  # or "ortho" if needed
        )

        return image_info

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch satellite image: {str(e)}"
        )
        
# ----------------------------
# POST /predict
# ----------------------------
@router.post("/predict", response_model=PredictionResponse)
def predict_segmentation(
    request: PredictionRequest,
    session: Session = Depends(get_session),
):
    try:
        # create_prediction should return SegmentationQuery object or compatible dict
        return create_prediction(request, session)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(error)}",
        )


# ----------------------------
# GET /results
# ----------------------------
@router.get("/results", response_model=list[PredictionHistoryItem])
def get_all_results(session: Session = Depends(get_session)):
    statement = select(SegmentationQuery).order_by(
        SegmentationQuery.created_at.desc()
    )
    results = session.exec(statement).all()

    history = []
    for item in results:
        history.append(
            PredictionHistoryItem(
                query_id=item.id,
                status=item.status,
                bbox=BoundingBox(
                    min_lat=item.min_lat,
                    max_lat=item.max_lat,
                    min_lon=item.min_lon,
                    max_lon=item.max_lon,
                ),
                created_at=item.created_at,
            )
        )

    return history


# ----------------------------
# GET /results/{query_id}
# ----------------------------
@router.get("/results/{query_id}", response_model=PredictionResponse)
def get_result_by_id(
    query_id: UUID,
    session: Session = Depends(get_session),
):
    result = session.get(SegmentationQuery, query_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Prediction result not found",
        )

    # Convert stored JSON into PredictionOutput schema
    prediction_output = PredictionOutput(**result.prediction_result)

    return PredictionResponse(
        query_id=result.id,
        status=result.status,
        bbox=BoundingBox(
            min_lat=result.min_lat,
            max_lat=result.max_lat,
            min_lon=result.min_lon,
            max_lon=result.max_lon,
        ),
        image=ImageInfo(
            image_url=result.image_url,
            width=result.image_width,
            height=result.image_height,
            format="tiff",
        ),
        prediction=prediction_output,
        created_at=result.created_at,
    )