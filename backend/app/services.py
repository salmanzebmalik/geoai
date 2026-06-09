from uuid import uuid4

from sqlmodel import Session

from app.db_models import SegmentationQuery
from app.ml_service_client import call_ml_service
from app.satellite_image_service import fetch_satellite_image_from_titiler
from app.schemas import (
    BoundingBox,
    PredictionRequest,
    PredictionResponse,
    PredictionOutput,
    ImageInfo,
    GeoJSONFeatureCollection,
)


def validate_bbox(bbox: BoundingBox) -> None:
    if bbox.max_lat <= bbox.min_lat:
        raise ValueError("max_lat must be greater than min_lat")
    if bbox.max_lon <= bbox.min_lon:
        raise ValueError("max_lon must be greater than min_lon")
    if not (-90 <= bbox.max_lat <= 90) or not (-90 <= bbox.min_lat <= 90):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180 <= bbox.max_lon <= 180) or not (-180 <= bbox.min_lon <= 180):
        raise ValueError("Longitude must be between -180 and 180")


def create_prediction(
    request: PredictionRequest,
    session: Session,
) -> PredictionResponse:
    """
    Backend workflow:

    1. Validate bounding box.
    2. Create DB record with status='processing'.
    3. Fetch satellite image from tiTiler.
    4. Send bounding box to ML service (form POST).
    5. Parse ML response and save to DB.
    6. Return PredictionResponse.
    """
    validate_bbox(request.bbox)

    # Create initial DB record
    db_query = SegmentationQuery(
        min_lat=request.bbox.min_lat,
        max_lat=request.bbox.max_lat,
        min_lon=request.bbox.min_lon,
        max_lon=request.bbox.max_lon,
        status="processing",
        image_url=None,
        image_width=None,
        image_height=None,
        prediction_result={},
    )
    session.add(db_query)
    session.commit()
    session.refresh(db_query)

    query_id = str(db_query.id)

    try:
        # Step 1: fetch satellite image
        image_path, image_info = fetch_satellite_image_from_titiler(
            query_id=query_id,
            bbox=request.bbox,
        )

        # Step 2: send bbox & query_id to ML service
        ml_result = call_ml_service(
            query_id=query_id,
            bbox=request.bbox,
            input_image_path=image_path,
        )
        
        # Step 3: parse ML response into PredictionOutput
        prediction_output = PredictionOutput(
            prediction_type=ml_result["prediction_type"],
            model_name=ml_result["model_name"],
            geojson=GeoJSONFeatureCollection(**ml_result["geojson"]),
        )

        # Step 4: update DB record
        db_query.status = "completed"
        db_query.image_url = image_info.image_url
        db_query.image_width = image_info.width
        db_query.image_height = image_info.height
        db_query.prediction_result = prediction_output.model_dump()

        session.add(db_query)
        session.commit()
        session.refresh(db_query)

        # Step 5: return PredictionResponse
        return PredictionResponse(
            query_id=db_query.id,
            status=db_query.status,
            bbox=request.bbox,
            image=image_info,
            prediction=prediction_output,
            created_at=db_query.created_at,
        )

    except Exception as e:
        db_query.status = "failed"
        db_query.prediction_result = {}
        session.add(db_query)
        session.commit()
        raise RuntimeError(f"Prediction failed: {str(e)}") from e