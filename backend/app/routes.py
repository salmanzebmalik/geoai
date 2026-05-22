from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.db_models import SegmentationQuery
from app.schemas import (
    BoundingBox,
    BuildingFootprintPrediction,
    ImageInfo,
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
)
from app.services import create_prediction


router = APIRouter(
    prefix="/api/segmentation",
    tags=["Building Footprint Prediction"],
)


@router.post("/predict", response_model=PredictionResponse)
def predict_building_footprints(
    request: PredictionRequest,
    session: Session = Depends(get_session),
):
    try:
        return create_prediction(request, session)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(error)}",
        )


@router.get("/results", response_model=list[PredictionHistoryItem])
def get_all_results(
    session: Session = Depends(get_session),
):
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
                    north=item.north,
                    south=item.south,
                    east=item.east,
                    west=item.west,
                ),
                summary=item.summary,
                created_at=item.created_at,
            )
        )

    return history


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

    prediction = BuildingFootprintPrediction(**result.prediction_result)

    return PredictionResponse(
        query_id=result.id,
        status=result.status,
        bbox=BoundingBox(
            north=result.north,
            south=result.south,
            east=result.east,
            west=result.west,
        ),
        image=ImageInfo(
            image_url=result.image_url,
            width=result.image_width,
            height=result.image_height,
            format="tiff",
        ),
        prediction=prediction,
        created_at=result.created_at,
    )