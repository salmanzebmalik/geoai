from typing import Any

from shapely.geometry import box, shape

from app.schemas.segmentation import BoundingBox


def filter_features_by_core_bbox(
    features: list[dict[str, Any]],
    core_bbox: BoundingBox,
) -> list[dict[str, Any]]:
    """
    Keep only features whose representative point lies inside the core bbox.

    This is the key duplicate-reduction step.

    The model runs on the larger inference_bbox, but the tile only keeps
    objects that belong to its non-overlapping core_bbox.
    """

    core_polygon = box(
        core_bbox.min_lon,
        core_bbox.min_lat,
        core_bbox.max_lon,
        core_bbox.max_lat,
    )

    kept_features: list[dict[str, Any]] = []

    for feature in features:
        geometry_dict = feature.get("geometry")

        if not geometry_dict:
            continue

        try:
            geom = shape(geometry_dict)

            if geom.is_empty:
                continue

            representative_point = geom.representative_point()

            if core_polygon.covers(representative_point):
                kept_features.append(feature)

        except Exception:
            # Skip invalid geometries instead of failing the full job
            continue

    return kept_features


def merge_tile_feature_lists(
    tile_feature_lists: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    merged_features: list[dict[str, Any]] = []

    for features in tile_feature_lists:
        merged_features.extend(features)

    return {
        "type": "FeatureCollection",
        "features": merged_features,
    }