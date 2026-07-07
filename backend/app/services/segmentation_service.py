from uuid import UUID

from sqlmodel import Session, select

from app.db.models import SegmentationQuery
from app.schemas.segmentation import (
    BoundingBox,
    GeoJSONFeatureCollection,
    ImageInfo,
    PredictionHistoryItem,
    PredictionOutput,
    PredictionRequest,
    PredictionResponse,
)
from app.services.ml_service_client import call_ml_service
from app.services.satellite_image_service import fetch_satellite_image_from_titiler


def validate_bbox(bbox: BoundingBox) -> None:
    if bbox.max_lat <= bbox.min_lat:
        raise ValueError("max_lat must be greater than min_lat")

    if bbox.max_lon <= bbox.min_lon:
        raise ValueError("max_lon must be greater than min_lon")

    if not (-90 <= bbox.min_lat <= 90):
        raise ValueError("min_lat must be between -90 and 90")

    if not (-90 <= bbox.max_lat <= 90):
        raise ValueError("max_lat must be between -90 and 90")

    if not (-180 <= bbox.min_lon <= 180):
        raise ValueError("min_lon must be between -180 and 180")

    if not (-180 <= bbox.max_lon <= 180):
        raise ValueError("max_lon must be between -180 and 180")


def create_empty_geojson() -> GeoJSONFeatureCollection:
    return GeoJSONFeatureCollection(
        type="FeatureCollection",
        features=[],
    )


def build_prediction_output_from_ml_result(ml_result: dict) -> PredictionOutput:
    return PredictionOutput(
        prediction_type=ml_result["prediction_type"],
        model_name=ml_result["model_name"],
        geojson=GeoJSONFeatureCollection(**ml_result["geojson"]),
        summary=ml_result.get("summary"),
    )


def create_prediction(
    request: PredictionRequest,
    session: Session,
) -> PredictionResponse:
    """
    Main backend orchestration workflow:

    1. Validate bbox.
    2. Create DB record with status='processing'.
    3. Fetch image from tiTiler.
    4. Save image in shared storage.
    5. Call ML service with input_image_path.
    6. Parse ML response.
    7. Store result in DB.
    8. Return response.
    """

    validate_bbox(request.bbox)

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
        image_path, image_info = fetch_satellite_image_from_titiler(
            query_id=query_id,
            bbox=request.bbox,
            source_type=request.source_type,
        )

        ml_result = call_ml_service(
            query_id=query_id,
            bbox=request.bbox,
            input_image_path=image_path,
            model_type=request.model_type,
            keyword=request.keyword,
        )

        prediction_output = build_prediction_output_from_ml_result(ml_result)

        db_query.status = "completed"
        db_query.image_url = image_info.image_url
        db_query.image_width = image_info.width
        db_query.image_height = image_info.height
        db_query.prediction_result = prediction_output.model_dump()

        session.add(db_query)
        session.commit()
        session.refresh(db_query)

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


def get_prediction_history(
    session: Session,
    limit: int = 5,
) -> list[PredictionHistoryItem]:
    statement = (
        select(SegmentationQuery)
        .where(SegmentationQuery.status == "completed")
        .order_by(SegmentationQuery.created_at.desc())
        .limit(limit)
    )

    results = session.exec(statement).all()

    return [
        PredictionHistoryItem(
            query_id=item.id,
            bbox=BoundingBox(
                min_lat=item.min_lat,
                max_lat=item.max_lat,
                min_lon=item.min_lon,
                max_lon=item.max_lon,
            ),
            created_at=item.created_at,
            prediction_type=item.prediction_result.get("prediction_type"),
            model_name=item.prediction_result.get("model_name"),
            summary=item.prediction_result.get("summary"),
        )
        for item in results
    ]


def get_prediction_by_id(
    query_id: UUID,
    session: Session,
) -> PredictionResponse | None:
    result = session.get(SegmentationQuery, query_id)

    if result is None:
        return None

    bbox = BoundingBox(
        min_lat=result.min_lat,
        max_lat=result.max_lat,
        min_lon=result.min_lon,
        max_lon=result.max_lon,
    )

    image = ImageInfo(
        image_url=result.image_url,
        width=result.image_width,
        height=result.image_height,
        format="tiff",
    )

    prediction = None

    if result.prediction_result:
        prediction = PredictionOutput(**result.prediction_result)

    return PredictionResponse(
        query_id=result.id,
        status=result.status,
        bbox=bbox,
        image=image,
        prediction=prediction,
        created_at=result.created_at,
    )