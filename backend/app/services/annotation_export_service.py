from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from shapely.geometry import shape

from app.core.config import settings
from app.schemas.segmentation import ExportOptions


SOURCE_CRS = "EPSG:4326"
GEOD = Geod(ellps="WGS84")
MEDIA_TYPES = {
    ".geojson": "application/geo+json",
    ".gpkg": "application/geopackage+sqlite3",
    ".fgb": "application/x-flatgeobuf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".json": "application/json",
    ".zip": "application/zip",
}


def _inside_storage(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(settings.shared_storage_path)
    except ValueError as error:
        raise RuntimeError("Export path is outside shared storage") from error
    return resolved


def _read_geojson(source: Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        payload = source
    else:
        payload = json.loads(_inside_storage(source).read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Prediction result must be a GeoJSON FeatureCollection")
    return payload


def _feature_label(feature: dict[str, Any]) -> str:
    properties = feature.get("properties") or {}
    for key in ("class", "label", "keyword", "category", "name"):
        value = properties.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "annotation"


def _feature_confidence(feature: dict[str, Any]) -> float | None:
    properties = feature.get("properties") or {}
    for key in ("confidence", "score", "probability"):
        value = properties.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _feature_area_m2(feature: dict[str, Any]) -> float:
    properties = feature.get("properties") or {}
    try:
        stored_area = float(properties.get("area_m2"))
        if stored_area >= 0:
            return stored_area
    except (TypeError, ValueError):
        pass
    geometry = shape(feature["geometry"])
    area, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(float(area))


def filter_features(
    feature_collection: dict[str, Any],
    options: ExportOptions,
) -> dict[str, Any]:
    filters = options.filters
    allowed_labels = {label.casefold() for label in filters.labels}
    allowed_geometries = set(filters.geometry_types)
    result: list[dict[str, Any]] = []

    for feature in feature_collection.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        if allowed_geometries and geometry.get("type") not in allowed_geometries:
            continue
        if allowed_labels and _feature_label(feature).casefold() not in allowed_labels:
            continue

        if filters.min_confidence is not None:
            confidence = _feature_confidence(feature)
            if confidence is None or confidence < filters.min_confidence:
                continue

        if filters.min_area_m2 is not None or filters.max_area_m2 is not None:
            area = _feature_area_m2(feature)
            if filters.min_area_m2 is not None and area < filters.min_area_m2:
                continue
            if filters.max_area_m2 is not None and area > filters.max_area_m2:
                continue

        result.append(feature)

    return {
        "type": "FeatureCollection",
        "name": feature_collection.get("name", "annotations"),
        "features": result,
    }


def _transform_collection(
    feature_collection: dict[str, Any],
    output_crs: str,
) -> dict[str, Any]:
    features = []
    for feature in feature_collection["features"]:
        transformed = dict(feature)
        transformed["geometry"] = transform_geom(
            SOURCE_CRS,
            output_crs,
            feature["geometry"],
            precision=8,
        )
        features.append(transformed)
    result = {
        "type": "FeatureCollection",
        "name": feature_collection.get("name", "annotations"),
        "features": features,
    }
    if output_crs != SOURCE_CRS:
        result["crs"] = {
            "type": "name",
            "properties": {"name": output_crs},
        }
    return result


def _json_safe_properties(properties: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in properties.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            result[str(key)] = value
        else:
            result[str(key)] = json.dumps(value, ensure_ascii=False)
    return result


def _write_vector_formats(
    feature_collection: dict[str, Any],
    export_dir: Path,
    options: ExportOptions,
) -> list[dict[str, str]]:
    transformed = _transform_collection(feature_collection, options.output_crs)
    artifacts: list[dict[str, str]] = []

    if "geojson" in options.vector_formats:
        path = export_dir / "annotations.geojson"
        path.write_text(
            json.dumps(transformed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        artifacts.append(_artifact("geojson", path, export_dir))

    non_geojson = set(options.vector_formats) - {"geojson"}
    if not non_geojson:
        return artifacts

    import geopandas as gpd

    normalized = {
        **transformed,
        "features": [
            {
                **feature,
                "properties": _json_safe_properties(feature.get("properties") or {}),
            }
            for feature in transformed["features"]
        ],
    }
    gdf = gpd.GeoDataFrame.from_features(
        normalized["features"],
        crs=options.output_crs,
    )

    if "gpkg" in non_geojson:
        path = export_dir / "annotations.gpkg"
        gdf.to_file(path, driver="GPKG", layer="annotations")
        artifacts.append(_artifact("gpkg", path, export_dir))

    if "flatgeobuf" in non_geojson:
        path = export_dir / "annotations.fgb"
        gdf.to_file(path, driver="FlatGeobuf")
        artifacts.append(_artifact("flatgeobuf", path, export_dir))

    if "shapefile" in non_geojson:
        directory = export_dir / "shapefile"
        directory.mkdir()
        gdf.to_file(directory / "annotations.shp", driver="ESRI Shapefile")
        archive = export_dir / "annotations_shapefile.zip"
        _zip_paths(archive, directory.rglob("*"), directory)
        artifacts.append(_artifact("shapefile", archive, export_dir))

    return artifacts


def _hex_rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def _scaled_rgb(value: str, dtype: np.dtype) -> np.ndarray:
    rgb = np.asarray(_hex_rgb(value), dtype=np.float64) / 255
    if np.issubdtype(dtype, np.integer):
        rgb *= np.iinfo(dtype).max
    return rgb.astype(dtype)


def _blend_overlay(
    rgb: np.ndarray,
    pixels: np.ndarray,
    hex_color: str,
    opacity: float,
) -> None:
    """Blend one flat colour into the selected pixels of `rgb`, in place."""
    color = _scaled_rgb(hex_color, rgb.dtype)[:, None]
    overlay = rgb[:, pixels].astype(np.float64)
    overlay *= 1 - opacity
    overlay += color.astype(np.float64) * opacity
    if np.issubdtype(rgb.dtype, np.integer):
        limits = np.iinfo(rgb.dtype)
        overlay = np.clip(overlay, limits.min, limits.max)
    rgb[:, pixels] = overlay.astype(rgb.dtype)


def _read_rgb(source: rasterio.io.DatasetReader) -> np.ndarray:
    if source.count == 1:
        band = source.read(1)
        return np.stack((band, band, band))
    if source.count == 2:
        first, second = source.read((1, 2))
        return np.stack((first, second, first))
    return source.read((1, 2, 3))


def _write_rasters(
    feature_collection: dict[str, Any],
    input_path: Path,
    export_dir: Path,
    options: ExportOptions,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    artifacts: list[dict[str, str]] = []
    label_values: dict[str, int] = {}
    if not options.include_mask_tiff and not options.include_annotated_tiff:
        for feature in feature_collection["features"]:
            label = _feature_label(feature)
            label_values.setdefault(label, len(label_values) + 1)
        return artifacts, label_values

    with rasterio.open(_inside_storage(input_path)) as source:
        shapes = []
        for feature in feature_collection["features"]:
            label = _feature_label(feature)
            value = label_values.setdefault(label, len(label_values) + 1)
            geometry = transform_geom(SOURCE_CRS, source.crs, feature["geometry"])
            shapes.append((geometry, value))

        mask_dtype = "uint8" if len(label_values) < 256 else "uint16"
        if shapes:
            mask = rasterize(
                shapes,
                out_shape=(source.height, source.width),
                transform=source.transform,
                fill=0,
                all_touched=True,
                dtype=mask_dtype,
            )
        else:
            mask = np.zeros((source.height, source.width), dtype=mask_dtype)

        if options.include_mask_tiff:
            mask_path = export_dir / "annotation_mask.tiff"
            mask_profile = source.profile.copy()
            mask_profile.update(
                count=1,
                dtype=mask.dtype,
                nodata=0,
                compress="deflate",
                photometric="minisblack",
            )
            with rasterio.open(mask_path, "w", **mask_profile) as target:
                target.write(mask, 1)
            artifacts.append(_artifact("mask_tiff", mask_path, export_dir))

        if options.include_annotated_tiff:
            rgb = _read_rgb(source)

            # The mask already holds one value per class, so each class can be
            # painted in its own colour - the frontend sends the colours the
            # legend shows. Classes without an entry, and single-class exports,
            # keep overlay_color.
            for label, value in label_values.items():
                pixels = mask == value
                if not pixels.any():
                    continue

                _blend_overlay(
                    rgb,
                    pixels,
                    options.label_colors.get(label, options.overlay_color),
                    options.overlay_opacity,
                )

            annotated_path = export_dir / "annotations_with_image.tiff"
            image_profile = source.profile.copy()
            image_profile.update(
                count=3,
                dtype=rgb.dtype,
                nodata=None,
                compress="deflate",
                photometric="RGB",
            )
            with rasterio.open(annotated_path, "w", **image_profile) as target:
                target.write(rgb)
            artifacts.append(
                _artifact("annotated_tiff", annotated_path, export_dir)
            )

    return artifacts, label_values


def _artifact(name: str, path: Path, export_dir: Path) -> dict[str, str]:
    return {
        "name": name,
        "path": path.relative_to(export_dir).as_posix(),
        "media_type": MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
    }


def _zip_paths(archive: Path, paths: Iterable[Path], base: Path) -> None:
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in paths:
            if path.is_file() and path.resolve() != archive.resolve():
                bundle.write(path, path.relative_to(base).as_posix())


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def export_annotations(
    query_id: UUID | str,
    annotations: Path | dict[str, Any],
    options: ExportOptions,
    prediction_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_id = str(query_id)
    query_dir = _inside_storage(
        settings.shared_storage_path / "queries" / query_id
    )
    input_path = query_dir / "input.tiff"
    if not input_path.is_file():
        raise FileNotFoundError(f"Source image not found for query {query_id}")

    source = _read_geojson(annotations)
    filtered = filter_features(source, options)
    export_id = uuid4()
    export_dir = query_dir / "exports" / str(export_id)
    export_dir.mkdir(parents=True, exist_ok=False)

    try:
        artifacts = _write_vector_formats(filtered, export_dir, options)
        raster_artifacts, label_values = _write_rasters(
            filtered,
            input_path,
            export_dir,
            options,
        )
        artifacts.extend(raster_artifacts)
        created_at = datetime.now(timezone.utc)
        metadata = {
            "export_id": str(export_id),
            "query_id": query_id,
            "created_at": created_at.isoformat(),
            "source_feature_count": len(source.get("features", [])),
            "exported_feature_count": len(filtered["features"]),
            "output_crs": options.output_crs,
            "options": options.model_dump(mode="json"),
            "label_values": label_values,
            "prediction": prediction_metadata or {},
            "artifacts": artifacts,
        }

        if options.include_metadata:
            metadata_path = export_dir / "metadata.json"
            _atomic_json(metadata_path, metadata)
            artifacts.append(_artifact("metadata", metadata_path, export_dir))

        if options.include_zip:
            bundle_path = export_dir / "export_bundle.zip"
            _zip_paths(bundle_path, export_dir.rglob("*"), export_dir)
            artifacts.append(_artifact("zip", bundle_path, export_dir))

        metadata["artifacts"] = artifacts
        _atomic_json(export_dir / "_manifest.json", metadata)
        if options.include_metadata:
            _atomic_json(export_dir / "metadata.json", metadata)
        return metadata
    except Exception:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise


def list_exports(query_id: UUID | str | None = None) -> list[dict[str, Any]]:
    query_root = settings.shared_storage_path / "queries"
    pattern = (
        f"{query_id}/exports/*/_manifest.json"
        if query_id is not None
        else "*/exports/*/_manifest.json"
    )
    manifests = []
    for path in query_root.glob(pattern):
        try:
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(manifests, key=lambda item: item["created_at"], reverse=True)


def get_export(export_id: UUID | str) -> tuple[dict[str, Any], Path] | None:
    query_root = settings.shared_storage_path / "queries"
    matches = list(query_root.glob(f"*/exports/{export_id}/_manifest.json"))
    if not matches:
        return None
    manifest_path = _inside_storage(matches[0])
    return json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path.parent


def get_export_artifact(
    export_id: UUID | str,
    artifact_name: str,
) -> tuple[dict[str, Any], Path] | None:
    export = get_export(export_id)
    if export is None:
        return None
    manifest, export_dir = export
    artifact = next(
        (item for item in manifest["artifacts"] if item["name"] == artifact_name),
        None,
    )
    if artifact is None:
        return None
    path = _inside_storage(export_dir / artifact["path"])
    if not path.is_file():
        return None
    return artifact, path
