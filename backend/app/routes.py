from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.db_models import SegmentationQuery
from app.schemas import (
    BoundingBox,
    ImageInfo,
    SegmentationHistoryItem,
    SegmentationPrediction,
    SegmentationRequest,
    SegmentationResponse,
)
from app.services import create_segmentation_prediction


router = APIRouter(
    prefix="/api/segmentation",
    tags=["Segmentation"]
)


@router.post("/predict", response_model=SegmentationResponse)
def predict_segmentation(
    request: SegmentationRequest,
    session: Session = Depends(get_session)
):
    try:
        result = create_segmentation_prediction(request, session)
        return result

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/results", response_model=list[SegmentationHistoryItem])
def get_all_segmentation_results(
    session: Session = Depends(get_session)
):
    statement = select(SegmentationQuery).order_by(SegmentationQuery.created_at.desc())
    results = session.exec(statement).all()

    history = []

    for item in results:
        history.append(
            SegmentationHistoryItem(
                query_id=item.id,
                status=item.status,
                bbox=BoundingBox(
                    north=item.north,
                    south=item.south,
                    east=item.east,
                    west=item.west
                ),
                summary=item.summary,
                created_at=item.created_at
            )
        )

    return history


@router.get("/results/{query_id}", response_model=SegmentationResponse)
def get_segmentation_result(
    query_id: UUID,
    session: Session = Depends(get_session)
):
    result = session.get(SegmentationQuery, query_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Segmentation result not found"
        )

    prediction = SegmentationPrediction(**result.prediction_result)

    return SegmentationResponse(
        query_id=result.id,
        status=result.status,
        bbox=BoundingBox(
            north=result.north,
            south=result.south,
            east=result.east,
            west=result.west
        ),
        image=ImageInfo(
            image_url=result.image_url,
            width=result.image_width,
            height=result.image_height
        ),
        prediction=prediction,
        created_at=result.created_at
    )