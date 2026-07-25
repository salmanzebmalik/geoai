import json
import os
from pathlib import Path
from uuid import UUID
from app.core.config import settings

from sqlmodel import Session, select

from app.db.models import SegmentationQuery
from app.schemas.segmentation import (
    BoundingBox,
    ImageInfo,
    PredictionHistoryItem,
    PredictionOutput,
    PredictionRequest,
    PredictionResponse,
)
from app.services.ml_service_client import call_ml_service
from app.services.satellite_image_service import fetch_satellite_image_from_titiler

from pyproj import Geod
from shapely.geometry import box as shp_box, mapping, shape
from shapely.ops import unary_union

# Geodesic area on the WGS84 ellipsoid, used to re-measure trimmed polygons.
_GEOD = Geod(ellps="WGS84")


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

def build_result_url(query_id: UUID | str) -> str:
    return f"/api/segmentation/results/{query_id}/geojson"


def build_prediction_output_from_ml_result(
    query_id: UUID | str,
    ml_result: dict,
) -> PredictionOutput:
    """
    Build the public response sent to the frontend.

    The internal result_path is deliberately excluded.
    """

    return PredictionOutput(
        prediction_type=ml_result["prediction_type"],
        model_name=ml_result["model_name"],
        result_url=build_result_url(query_id),
        feature_count=ml_result["feature_count"],
        summary=ml_result.get("summary"),
    )


def build_stored_prediction_metadata(
    ml_result: dict,
    request: PredictionRequest | None = None,
) -> dict:
    """
    Build the lightweight metadata stored in PostgreSQL.

    The database stores the internal result_path but not the GeoJSON.
    """

    metadata = {
        "prediction_type": ml_result["prediction_type"],
        "model_name": ml_result["model_name"],
        "result_path": ml_result["result_path"],
        "feature_count": ml_result["feature_count"],
        "summary": ml_result.get("summary"),
    }
    if request is not None:
        metadata.update(
            model_type=request.model_type,
            keywords=request.requested_keywords(),
            source_type=request.source_type,
        )
    return metadata


def run_prediction_models(
    query_id: str,
    image_path: str,
    request: PredictionRequest,
) -> dict:
    """Run one tree model or all requested zero-shot terms."""
    keywords = request.requested_keywords() if request.model_type == "zeroshot" else [None]
    results: list[dict] = []
    merged_features: list[dict] = []

    for keyword in keywords:
        result = call_ml_service(
            query_id=query_id,
            input_image_path=image_path,
            model_type=request.model_type,
            keyword=keyword,
        )
        result_path = resolve_prediction_result_path(result["result_path"])
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        for feature in payload.get("features", []):
            if keyword:
                properties = feature.setdefault("properties", {})
                properties.setdefault("class", keyword)
                properties["keyword"] = keyword
            merged_features.append(feature)
        results.append(result)

    if len(results) == 1:
        final = results[0]
    else:
        final_path = resolve_prediction_result_path(results[-1]["result_path"])
        temporary = final_path.with_suffix(final_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "name": "zero_shot_predictions",
                    "features": merged_features,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, final_path)
        final = {
            **results[-1],
            "feature_count": len(merged_features),
            "summary": (
                f"Found {len(merged_features)} polygons/clusters for "
                + ", ".join(keywords)
            ),
        }

    # Trim predictions to the drawn AOI. tiTiler reprojects the crop to UTM, so it
    # comes back a few metres larger than the lon/lat box and the model can detect
    # features just past it; clip every polygon so nothing renders outside the box.
    final["feature_count"] = clip_geojson_to_bbox(final["result_path"], request.bbox)
    return final


def _polygonal(geom):
    """Keep only the polygonal part of a clip result (drop line/point tangencies)."""
    if geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        return unary_union(polys) if polys else None
    return None


def clip_geojson_to_bbox(stored_path: str, bbox: BoundingBox) -> int:
    """Clip stored prediction polygons to the requested AOI and rewrite the file.

    Each feature is intersected with the lon/lat box the user drew: features entirely
    outside are dropped and a straddling feature is trimmed at the box edge (its
    area_m2 is refreshed geodesically). Returns the number of features kept.
    """
    path = resolve_prediction_result_path(stored_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    clip = shp_box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)

    kept: list[dict] = []
    for feature in data.get("features", []):
        raw = feature.get("geometry")
        if not raw:
            continue
        try:
            geom = shape(raw)
        except Exception:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        clipped = _polygonal(geom.intersection(clip))
        if clipped is None or clipped.is_empty:
            continue
        new_feature = {**feature, "geometry": mapping(clipped)}
        props = feature.get("properties") or {}
        if "area_m2" in props and clipped.area < geom.area * (1 - 1e-9):
            new_props = dict(props)
            area, _ = _GEOD.geometry_area_perimeter(clipped)
            new_props["area_m2"] = round(abs(area), 2)
            new_feature["properties"] = new_props
        kept.append(new_feature)

    data["features"] = kept
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
    return len(kept)


def resolve_prediction_result_path(
    stored_path: str,
) -> Path:
    """
    Resolve and validate a result path reported by the ML service.
    """

    storage_root = settings.shared_storage_path
    result_path = (storage_root / stored_path).resolve()

    try:
        result_path.relative_to(storage_root)
    except ValueError as e:
        raise RuntimeError(
            "Stored prediction path is outside shared storage"
        ) from e

    if not result_path.is_file():
        raise FileNotFoundError(
            f"Prediction result file not found: {stored_path}"
        )

    return result_path


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

        ml_result = run_prediction_models(
            query_id=query_id,
            image_path=image_path,
            request=request,
        )

        resolve_prediction_result_path(
            ml_result["result_path"]
        )

        prediction_output = build_prediction_output_from_ml_result(
            query_id=db_query.id,
            ml_result=ml_result,
        )

        db_query.status = "completed"
        db_query.image_url = image_info.image_url
        db_query.image_width = image_info.width
        db_query.image_height = image_info.height
        db_query.prediction_result = (
            build_stored_prediction_metadata(ml_result, request=request)
        )

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
    limit: int = 10,
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
            keywords=item.prediction_result.get("keywords", []),
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
        stored_result = result.prediction_result
        legacy_geojson = stored_result.get("geojson")
        result_path = stored_result.get("result_path")

        has_legacy_geojson = isinstance(
            legacy_geojson,
            dict,
        )

        if result_path or has_legacy_geojson:
            feature_count = stored_result.get(
                "feature_count",
                len(legacy_geojson.get("features", []))
                if has_legacy_geojson
                else 0,
            )

            prediction = PredictionOutput(
                prediction_type=stored_result["prediction_type"],
                model_name=stored_result["model_name"],
                result_url=build_result_url(result.id),
                feature_count=feature_count,
                summary=stored_result.get("summary"),
            )

    return PredictionResponse(
        query_id=result.id,
        status=result.status,
        bbox=bbox,
        image=image,
        prediction=prediction,
        created_at=result.created_at,
    )


def get_prediction_geojson_source(
    query_id: UUID,
    session: Session,
) -> Path | dict | None:
    """
    Return the prediction result source.

    New results return a Path to the stored GeoJSON file.
    Historical results return their embedded GeoJSON dictionary.
    """

    result = session.get(
        SegmentationQuery,
        query_id,
    )

    if result is None:
        return None

    if result.status != "completed":
        return None

    stored_result = result.prediction_result or {}
    stored_path = stored_result.get("result_path")

    if stored_path:
        try:
            return resolve_prediction_result_path(
                stored_path
            )
        except FileNotFoundError:
            return None

    legacy_geojson = stored_result.get("geojson")

    if isinstance(legacy_geojson, dict):
        return legacy_geojson

    return None
