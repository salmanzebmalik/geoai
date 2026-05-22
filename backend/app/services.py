from uuid import uuid4

from sqlmodel import Session

from app.db_models import SegmentationQuery
from app.ml_service_client import call_ml_service
from app.satellite_image_service import fetch_satellite_image_placeholder
from app.schemas import (
    BoundingBox,
    BuildingFootprintPrediction,
    PredictionRequest,
    PredictionResponse,
)


def validate_bbox(bbox: BoundingBox) -> None:
    if bbox.north <= bbox.south:
        raise ValueError("north must be greater than south")

    if bbox.east <= bbox.west:
        raise ValueError("east must be greater than west")

    if not (-90 <= bbox.north <= 90):
        raise ValueError("north latitude must be between -90 and 90")

    if not (-90 <= bbox.south <= 90):
        raise ValueError("south latitude must be between -90 and 90")

    if not (-180 <= bbox.east <= 180):
        raise ValueError("east longitude must be between -180 and 180")

    if not (-180 <= bbox.west <= 180):
        raise ValueError("west longitude must be between -180 and 180")


def create_prediction(
    request: PredictionRequest,
    session: Session,
) -> PredictionResponse:
    """
    Main backend workflow:

    1. Validate bbox
    2. Create database record with status = processing
    3. Fetch/create satellite image as .tiff
    4. Send .tiff image to ML service
    5. Receive GeoJSON building polygons
    6. Store prediction in Supabase
    7. Return response to frontend
    """

    validate_bbox(request.bbox)

    db_query = SegmentationQuery(
        north=request.bbox.north,
        south=request.bbox.south,
        east=request.bbox.east,
        west=request.bbox.west,
        status="processing",
        image_url=None,
        image_width=None,
        image_height=None,
        prediction_result={},
        summary="Building footprint prediction is being processed.",
    )

    session.add(db_query)
    session.commit()
    session.refresh(db_query)

    query_id = str(db_query.id)

    try:
        image_path, image_info = fetch_satellite_image_placeholder(
            query_id=query_id,
            bbox=request.bbox,
        )

        ml_result = call_ml_service(
            image_path=image_path,
            query_id=query_id,
        )

        prediction = BuildingFootprintPrediction(
            prediction_type=ml_result["prediction_type"],
            model_name=ml_result["model_name"],
            geojson=ml_result["geojson"],
            summary=ml_result["summary"],
        )

        db_query.status = "completed"
        db_query.image_url = image_info.image_url
        db_query.image_width = image_info.width
        db_query.image_height = image_info.height
        db_query.prediction_result = prediction.model_dump()
        db_query.summary = prediction.summary

        session.add(db_query)
        session.commit()
        session.refresh(db_query)

        return PredictionResponse(
            query_id=db_query.id,
            status=db_query.status,
            bbox=request.bbox,
            image=image_info,
            prediction=prediction,
            created_at=db_query.created_at,
        )

    except Exception as error:
        db_query.status = "failed"
        db_query.summary = f"Prediction failed: {str(error)}"
        session.add(db_query)
        session.commit()

        raise