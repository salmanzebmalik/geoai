from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session

from app.db.database import get_session
from app.db.models import SegmentationQuery
from app.services.ml_service_client import MLServiceBusyError
from app.dependencies import acquire_prediction_slot

from app.schemas.segmentation import (
    ExportArtifact,
    ExportRequest,
    ExportResponse,
    FetchImageRequest,
    ImageInfo,
    PredictionHistoryItem,
    PredictionExportRequest,
    PredictionExportResponse,
    PredictionRequest,
    PredictionResponse,
    RasterEstimateRequest,
    RasterEstimateResponse,
)
from app.services.annotation_export_service import (
    export_annotations,
    get_export,
    get_export_artifact,
    list_exports,
)
from app.services.satellite_image_service import fetch_satellite_image_from_titiler

from app.services.segmentation_service import (
    create_prediction,
    get_prediction_by_id,
    get_prediction_geojson_source,
    get_prediction_history,
    validate_bbox,
    PredictionDeletionError,
    PredictionNotDeletableError,
    delete_prediction,
)

from app.core.config import settings
from app.utils.raster_budget import (
    RasterBudgetExceededError,
    estimate_raster_size,
    get_raster_budget,
    raster_fits_budget,
    validate_raster_budget,
)

router = APIRouter()

def build_ml_busy_http_exception(
    error: MLServiceBusyError,
) -> HTTPException:
    retry_after = error.retry_after_seconds

    return HTTPException(
        status_code=429,
        detail=(
            "GPU inference is currently busy. "
            f"Try again in approximately {retry_after} seconds."
        ),
        headers={
            "Retry-After": str(retry_after),
        },
    )
    
def build_export_response(manifest: dict) -> ExportResponse:
    export_id = manifest["export_id"]
    prediction = manifest.get("prediction") or {}
    return ExportResponse(
        export_id=export_id,
        query_id=manifest["query_id"],
        created_at=manifest["created_at"],
        model_type=prediction.get("model_type"),
        keywords=prediction.get("keywords", []),
        source_feature_count=manifest["source_feature_count"],
        exported_feature_count=manifest["exported_feature_count"],
        output_crs=manifest["output_crs"],
        artifacts=[
            ExportArtifact(
                name=artifact["name"],
                media_type=artifact["media_type"],
                download_url=(
                    f"/api/segmentation/exports/{export_id}/download/"
                    f"{artifact['name']}"
                ),
            )
            for artifact in manifest["artifacts"]
        ],
    )


def prediction_export_metadata(query: SegmentationQuery) -> dict:
    stored = query.prediction_result or {}
    return {
        "model_type": stored.get("model_type"),
        "model_name": stored.get("model_name"),
        "prediction_type": stored.get("prediction_type"),
        "keywords": stored.get("keywords", []),
        "source_type": stored.get("source_type"),
        "bbox": {
            "min_lat": query.min_lat,
            "max_lat": query.max_lat,
            "min_lon": query.min_lon,
            "max_lon": query.max_lon,
        },
        "feature_count": stored.get("feature_count"),
        "summary": stored.get("summary"),
        "prediction_created_at": query.created_at.isoformat(),
    }


def create_export_for_query(
    request: ExportRequest,
    session: Session,
) -> ExportResponse:
    query = session.get(SegmentationQuery, request.query_id)
    if query is None or query.status != "completed":
        raise HTTPException(status_code=404, detail="Completed prediction not found")
    annotations = get_prediction_geojson_source(request.query_id, session)
    if annotations is None:
        raise HTTPException(status_code=404, detail="Prediction GeoJSON file not found")
    manifest = export_annotations(
        query_id=request.query_id,
        annotations=annotations,
        options=request.options,
        prediction_metadata=prediction_export_metadata(query),
    )
    return build_export_response(manifest)

@router.post(
    "/estimate",
    response_model=RasterEstimateResponse,
)
def estimate_prediction_raster(
    request: RasterEstimateRequest,
):
    """Estimate the raster workload without starting processing."""

    try:
        validate_bbox(request.bbox)

        estimate = estimate_raster_size(
            bbox=request.bbox,
            source_type=request.source_type,
        )

        budget = get_raster_budget(
            source_type=request.source_type,
            model_type=request.model_type,
        )
        
        return RasterEstimateResponse(
            source_type=request.source_type,
            model_type=request.model_type,
            width_pixels=estimate.width_pixels,
            height_pixels=estimate.height_pixels,
            total_pixels=estimate.total_pixels,
            megapixels=round(estimate.megapixels, 2),
            resolution_meters=estimate.resolution_meters,
            projected_crs=estimate.projected_crs,
            allowed=raster_fits_budget(
                estimate,
                source_type=request.source_type,
                model_type=request.model_type,
            ),
            max_total_pixels=budget.max_total_pixels,
            max_side_pixels=budget.max_side_pixels,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
        
@router.post("/fetch-image", response_model=ImageInfo)
def fetch_image(
    request: FetchImageRequest,
):
    """
    Fetch and save an image from tiTiler without running ML inference.
    Useful for debugging image fetching.
    """

    try:
        validate_bbox(request.bbox)

        validate_raster_budget(
            bbox=request.bbox,
            source_type=request.source_type,
            model_type=None,
        )
        
        query_id = str(uuid4())

        image_path, image_info = fetch_satellite_image_from_titiler(
            query_id=query_id,
            bbox=request.bbox,
            source_type=request.source_type,
        )

        return image_info
    
    except RasterBudgetExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch satellite image: {str(e)}",
        )


@router.post("/predict", response_model=PredictionResponse)
def predict_segmentation(
    request: PredictionRequest,
    _prediction_slot: None = Depends(
        acquire_prediction_slot
    ),
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

    except MLServiceBusyError as error:
        raise build_ml_busy_http_exception(error) from error

    except RasterBudgetExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(error),
        ) from error
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}",
        ) from e


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

@router.delete(
    "/results/{query_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_result_by_id(
    query_id: UUID,
    session: Session = Depends(get_session),
) -> Response:
    try:
        deleted = delete_prediction(
            query_id=query_id,
            session=session,
        )

    except PredictionNotDeletableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except PredictionDeletionError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The prediction could not be deleted safely. "
                "Please try again."
            ),
        ) from error

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
    
@router.get("/results/{query_id}/geojson")
def get_result_geojson(
    query_id: UUID,
    session: Session = Depends(get_session),
):
    try:
        result_source = get_prediction_geojson_source(
            query_id=query_id,
            session=session,
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e

    if result_source is None:
        raise HTTPException(
            status_code=404,
            detail="Prediction GeoJSON file not found",
        )

    # Compatibility for historical database records.
    if isinstance(result_source, dict):
        return JSONResponse(
            content=result_source,
            media_type="application/geo+json",
        )

    # New results are streamed from shared storage.
    return FileResponse(
        path=result_source,
        media_type="application/geo+json",
        filename=f"prediction_{query_id}.geojson",
    )


@router.post("/exports", response_model=ExportResponse)
def create_annotation_export(
    request: ExportRequest,
    session: Session = Depends(get_session),
):
    try:
        return create_export_for_query(request, session)
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Annotation export failed: {error}",
        ) from error


@router.post("/export", response_model=ExportResponse, include_in_schema=False)
def create_annotation_export_compatibility(
    request: ExportRequest,
    session: Session = Depends(get_session),
):
    return create_annotation_export(request, session)


@router.post(
    "/export/predict",
    response_model=PredictionExportResponse,
)
def predict_and_export_annotations(
    request: PredictionExportRequest,
    _prediction_slot: None = Depends(
        acquire_prediction_slot
    ),
    session: Session = Depends(get_session),
):
    """
    Run segmentation prediction and export the results in one request.
    """
    try:
        prediction = create_prediction(request=request, session=session)
        exported = create_export_for_query(
            ExportRequest(query_id=prediction.query_id, options=request.export),
            session,
        )
        return PredictionExportResponse(prediction=prediction, export=exported)
    
    except MLServiceBusyError as error:
        raise build_ml_busy_http_exception(error) from error
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction export failed: {error}",
        ) from error


@router.get("/exports", response_model=list[ExportResponse])
def get_export_history(
    query_id: UUID | None = Query(default=None),
):
    return [build_export_response(item) for item in list_exports(query_id)]


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export_by_id(export_id: UUID):
    export = get_export(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="Export not found")
    manifest, _ = export
    return build_export_response(manifest)


@router.get("/exports/{export_id}/download/{artifact_name}")
def download_export_artifact(export_id: UUID, artifact_name: str):
    artifact_result = get_export_artifact(export_id, artifact_name)
    if artifact_result is None:
        raise HTTPException(status_code=404, detail="Export artifact not found")
    artifact, path = artifact_result
    return FileResponse(
        path=path,
        media_type=artifact["media_type"],
        filename=path.name,
    )


@router.get("/export/{query_id}/{artifact_name}")
def download_latest_query_export(query_id: UUID, artifact_name: str):
    exports = list_exports(query_id)
    if not exports:
        raise HTTPException(status_code=404, detail="No export found for prediction")
    return download_export_artifact(exports[0]["export_id"], artifact_name)
