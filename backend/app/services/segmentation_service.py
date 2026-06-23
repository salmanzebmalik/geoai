from typing import Literal
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

from app.services.geojson_merge_service import (
    filter_features_by_core_bbox,
    merge_tile_feature_lists,
)
from app.services.tiling_service import create_tile_plan

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------
def choose_prediction_strategy(bbox: BoundingBox) -> str:
    lat_span = bbox.max_lat - bbox.min_lat
    lon_span = bbox.max_lon - bbox.min_lon
    max_span = max(lat_span, lon_span)

    if max_span <= 0.01:
        return "direct_tile"

    return "distributed_tiles"


# ---------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------
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


def create_initial_db_query(
    request: PredictionRequest,
    session: Session,
) -> SegmentationQuery:
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

    return db_query


def mark_query_as_failed(
    db_query: SegmentationQuery,
    session: Session,
) -> None:
    db_query.status = "failed"
    db_query.prediction_result = {}

    session.add(db_query)
    session.commit()


# ---------------------------------------------------------
# Main entry point
# ---------------------------------------------------------
def create_prediction(
    request: PredictionRequest,
    session: Session,
) -> PredictionResponse:
    """
    Small bbox:
        one tile

    Larger bbox:
        multiple tiles

    Both return final PredictionResponse synchronously.
    """

    validate_bbox(request.bbox)

    
    # choosing the strategy for small and large bounding boxes.
    strategy = choose_prediction_strategy(request.bbox)

    print("\n========== Prediction Strategy ==========")
    print("Strategy:", strategy)
    print("Model type:", request.model_type)
    print("Source type:", request.source_type)
    print("========================================\n")

    return run_tile_based_prediction(
        request=request,
        session=session,
    )
    
def run_tile_based_prediction(
    request: PredictionRequest,
    session: Session,
) -> PredictionResponse:
    """
    Unified tile-based prediction.

    Important idea:
        - ML runs on inference_bbox
        - duplicate filtering uses core_bbox

    This reduces duplicate polygons caused by overlapping tiles.
    """

    db_query = create_initial_db_query(
        request=request,
        session=session,
    )

    query_id = str(db_query.id)

    try:
        tile_plan = create_tile_plan(
            bbox=request.bbox,
            tile_size_deg=0.01,
            overlap_deg=0.001,
            direct_threshold_deg=0.01,
        )

        max_tiles = 500

        if len(tile_plan) > max_tiles:
            raise ValueError(
                f"Selected area is too large for direct prediction. "
                f"Generated {len(tile_plan)} tiles, but the current limit is {max_tiles}. "
                f"Please select a smaller area."
            )

        print("\n========== Tile Plan Debug ==========")
        print("Parent query ID:", query_id)
        print("Number of tiles:", len(tile_plan))
        print("=====================================\n")

        filtered_tile_feature_lists = []

        prediction_type = None
        model_name = None
        first_image_info = None

        total_raw_features = 0
        total_kept_features = 0

        for tile in tile_plan:
            print("\n========== Processing Tile ==========")
            print("Tile:", tile.tile_id)
            print("Core bbox:", tile.core_bbox)
            print("Inference bbox:", tile.inference_bbox)
            print("=====================================\n")

            # Fetch image using inference bbox
            image_path, image_info = fetch_satellite_image_from_titiler(
                query_id=query_id,
                bbox=tile.inference_bbox,
                source_type=request.source_type,
                tile_id=tile.tile_id,
            )

            if first_image_info is None:
                first_image_info = image_info

            # Important:
            # bbox passed to ML must be inference_bbox because the image
            # was fetched using inference_bbox.
            ml_result = call_ml_service(
                query_id=f"{query_id}_{tile.tile_id}",
                bbox=tile.inference_bbox,
                input_image_path=image_path,
                model_type=request.model_type,
                keyword=request.keyword,
            )

            if prediction_type is None:
                prediction_type = ml_result.get("prediction_type")

            if model_name is None:
                model_name = ml_result.get("model_name")

            tile_geojson = ml_result.get("geojson", {})
            raw_features = tile_geojson.get("features", [])

            # Duplicate reduction:
            # only keep predictions owned by this tile's core area
            filtered_features = filter_features_by_core_bbox(
                features=raw_features,
                core_bbox=tile.core_bbox,
            )

            filtered_tile_feature_lists.append(filtered_features)

            total_raw_features += len(raw_features)
            total_kept_features += len(filtered_features)

            print("\n========== Tile Result ==========")
            print("Tile:", tile.tile_id)
            print("Raw features:", len(raw_features))
            print("Kept after core filter:", len(filtered_features))
            print("Total raw features so far:", total_raw_features)
            print("Total kept features so far:", total_kept_features)
            print("=================================\n")

        merged_geojson = merge_tile_feature_lists(
            filtered_tile_feature_lists
        )

        prediction_output = PredictionOutput(
            prediction_type=prediction_type or request.model_type,
            model_name=model_name or "tile-based-ml-service",
            geojson=GeoJSONFeatureCollection(**merged_geojson),
            summary=(
                f"Processed {len(tile_plan)} tile(s). "
                f"Raw features before filtering: {total_raw_features}. "
                f"Features after core-area filtering: {total_kept_features}."
            ),
        )

        db_query.status = "completed"

        if len(tile_plan) == 1 and first_image_info is not None:
            db_query.image_url = first_image_info.image_url
            db_query.image_width = first_image_info.width
            db_query.image_height = first_image_info.height
        else:
            db_query.image_url = None
            db_query.image_width = None
            db_query.image_height = None

        db_query.prediction_result = prediction_output.model_dump()

        session.add(db_query)
        session.commit()
        session.refresh(db_query)

        return PredictionResponse(
            query_id=db_query.id,
            status=db_query.status,
            bbox=request.bbox,
            image=first_image_info if len(tile_plan) == 1 else None,
            prediction=prediction_output,
            created_at=db_query.created_at,
        )

    except Exception as e:
        mark_query_as_failed(
            db_query=db_query,
            session=session,
        )

        raise RuntimeError(f"Tile-based prediction failed: {str(e)}") from e
       
# ---------------------------------------------------------
# Result/history functions
# ---------------------------------------------------------
def get_prediction_history(session: Session) -> list[PredictionHistoryItem]:
    statement = select(SegmentationQuery).order_by(
        SegmentationQuery.created_at.desc()
    )

    results = session.exec(statement).all()

    return [
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