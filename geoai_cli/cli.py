from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from geoai_cli import __version__
from geoai_cli.client import APIClient, APIError, DEFAULT_API_URL


ARTIFACT_SUFFIXES = {
    "geojson": ".geojson",
    "gpkg": ".gpkg",
    "flatgeobuf": ".fgb",
    "shapefile": ".zip",
    "mask_tiff": ".tiff",
    "annotated_tiff": ".tiff",
    "metadata": ".json",
    "zip": ".zip",
}

MODEL_TYPES = ("tree", "tree_satlas", "tree_unet", "tree_deepforest", "zeroshot")
SOURCE_TYPES = ("satellite", "ortho")
VECTOR_FORMATS = ("geojson", "gpkg", "flatgeobuf", "shapefile")
GEOMETRY_TYPES = ("Polygon", "MultiPolygon")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geoai",
        description="Command-line client for the GeoAI segmentation API.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("GEOAI_API_URL", DEFAULT_API_URL),
        help="segmentation API base URL (env: GEOAI_API_URL)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("GEOAI_TIMEOUT", "600")),
        help="request timeout in seconds (env: GEOAI_TIMEOUT; default: 600)",
    )
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    parser.add_argument("--version", action="version", version=__version__)

    commands = parser.add_subparsers(dest="command", required=True)
    _add_fetch_image_command(commands)
    _add_predict_command(commands)
    _add_predict_export_command(commands)
    _add_results_commands(commands)
    _add_exports_commands(commands)
    return parser


def _add_fetch_image_command(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "fetch-image",
        help="fetch the source image without running inference",
    )
    _add_bbox_arguments(parser)
    _add_source_argument(parser)
    parser.set_defaults(handler=_fetch_image)


def _add_predict_command(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser("predict", help="run a segmentation prediction")
    _add_prediction_arguments(parser)
    parser.set_defaults(handler=_predict)


def _add_predict_export_command(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "predict-export",
        help="run a prediction and export its artifacts",
    )
    _add_prediction_arguments(parser)
    _add_export_arguments(parser)
    parser.set_defaults(handler=_predict_export)


def _add_results_commands(commands: argparse._SubParsersAction) -> None:
    results = commands.add_parser("results", help="inspect prediction results")
    actions = results.add_subparsers(dest="results_command", required=True)

    list_parser = actions.add_parser("list", help="list completed predictions")
    list_parser.set_defaults(handler=_results_list)

    show = actions.add_parser("show", help="show one prediction")
    show.add_argument("query_id")
    show.set_defaults(handler=_results_show)

    download = actions.add_parser("download", help="download prediction GeoJSON")
    download.add_argument("query_id")
    download.add_argument("-o", "--output", type=Path)
    download.set_defaults(handler=_results_download)


def _add_exports_commands(commands: argparse._SubParsersAction) -> None:
    exports = commands.add_parser("exports", help="inspect and download exports")
    actions = exports.add_subparsers(dest="exports_command", required=True)

    create = actions.add_parser("create", help="export an existing prediction")
    create.add_argument("query_id")
    _add_export_arguments(create)
    create.set_defaults(handler=_exports_create)

    list_parser = actions.add_parser("list", help="list generated exports")
    list_parser.add_argument("--query-id")
    list_parser.set_defaults(handler=_exports_list)

    show = actions.add_parser("show", help="show one export manifest")
    show.add_argument("export_id")
    show.set_defaults(handler=_exports_show)

    download = actions.add_parser("download", help="download one export artifact")
    download.add_argument("export_id")
    download.add_argument("artifact_name")
    download.add_argument("-o", "--output", type=Path)
    download.set_defaults(handler=_exports_download)


def _add_bbox_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        required=True,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="bounding box in WGS84 coordinates",
    )


def _add_source_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-type",
        choices=SOURCE_TYPES,
        default="satellite",
        help="source imagery (default: satellite)",
    )


def _add_prediction_arguments(parser: argparse.ArgumentParser) -> None:
    _add_bbox_arguments(parser)
    _add_source_argument(parser)
    parser.add_argument(
        "--model-type",
        choices=MODEL_TYPES,
        default="tree",
        help="inference model (default: tree)",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        action="append",
        default=[],
        help="zero-shot search term; repeat for multiple terms",
    )


def _add_export_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--geojson",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include GeoJSON (default: enabled)",
    )
    parser.add_argument(
        "--annotated-tiff",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include annotated GeoTIFF (default: enabled)",
    )
    parser.add_argument(
        "--mask-tiff",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="include mask GeoTIFF (default: disabled)",
    )
    parser.add_argument(
        "--metadata",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include metadata JSON (default: enabled)",
    )
    parser.add_argument(
        "--zip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include ZIP bundle (default: enabled)",
    )
    parser.add_argument("--overlay-color", default="#ff0000")
    parser.add_argument("--overlay-opacity", type=float, default=0.45)
    parser.add_argument("--output-crs", default="EPSG:4326")
    parser.add_argument(
        "--vector-format",
        action="append",
        choices=VECTOR_FORMATS,
        help="vector format; repeat to request multiple formats",
    )
    parser.add_argument("--min-area-m2", type=float)
    parser.add_argument("--max-area-m2", type=float)
    parser.add_argument("--min-confidence", type=float)
    parser.add_argument(
        "--geometry-type",
        action="append",
        choices=GEOMETRY_TYPES,
        default=[],
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="feature label to retain; repeat for multiple labels",
    )


def _fetch_image(client: APIClient, args: argparse.Namespace) -> Any:
    return client.post(
        "fetch-image",
        {"bbox": _bbox_payload(args.bbox), "source_type": args.source_type},
    )


def _predict(client: APIClient, args: argparse.Namespace) -> Any:
    return client.post("predict", _prediction_payload(args))


def _predict_export(client: APIClient, args: argparse.Namespace) -> Any:
    payload = _prediction_payload(args)
    payload["export"] = _export_payload(args)
    return client.post("export/predict", payload)


def _results_list(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get("results")


def _results_show(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get(f"results/{args.query_id}")


def _results_download(client: APIClient, args: argparse.Namespace) -> None:
    output = args.output or Path(f"prediction-{args.query_id}.geojson")
    _download(client, f"results/{args.query_id}/geojson", output)


def _exports_list(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get("exports", query={"query_id": args.query_id})


def _exports_create(client: APIClient, args: argparse.Namespace) -> Any:
    return client.post(
        "exports",
        {"query_id": args.query_id, "options": _export_payload(args)},
    )


def _exports_show(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get(f"exports/{args.export_id}")


def _exports_download(client: APIClient, args: argparse.Namespace) -> None:
    suffix = ARTIFACT_SUFFIXES.get(args.artifact_name, "")
    output = args.output or Path(
        f"export-{args.export_id}-{args.artifact_name}{suffix}"
    )
    _download(
        client,
        f"exports/{args.export_id}/download/{args.artifact_name}",
        output,
    )


def _download(client: APIClient, path: str, output: Path) -> None:
    target, size = client.download(path, output)
    print(f"Saved {size} bytes to {target}")


def _bbox_payload(values: list[float]) -> dict[str, float]:
    min_lon, min_lat, max_lon, max_lat = values
    if max_lon <= min_lon:
        raise ValueError("MAX_LON must be greater than MIN_LON")
    if max_lat <= min_lat:
        raise ValueError("MAX_LAT must be greater than MIN_LAT")
    if not -180 <= min_lon <= 180 or not -180 <= max_lon <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if not -90 <= min_lat <= 90 or not -90 <= max_lat <= 90:
        raise ValueError("latitude must be between -90 and 90")
    return {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
    }


def _prediction_payload(args: argparse.Namespace) -> dict[str, Any]:
    keywords = list(dict.fromkeys(term.strip() for term in args.keyword if term.strip()))
    if args.model_type == "zeroshot" and not keywords:
        raise ValueError("--keyword is required for model type zeroshot")
    if args.model_type != "zeroshot" and keywords:
        raise ValueError("--keyword can only be used with model type zeroshot")
    return {
        "bbox": _bbox_payload(args.bbox),
        "model_type": args.model_type,
        "keywords": keywords,
        "source_type": args.source_type,
    }


def _export_payload(args: argparse.Namespace) -> dict[str, Any]:
    vector_formats = args.vector_format
    if vector_formats is None:
        vector_formats = ["geojson"] if args.geojson else []
    vector_formats = list(dict.fromkeys(vector_formats))
    if args.geojson and "geojson" not in vector_formats:
        vector_formats.insert(0, "geojson")
    if not args.geojson:
        vector_formats = [item for item in vector_formats if item != "geojson"]

    return {
        "include_geojson": args.geojson,
        "include_annotated_tiff": args.annotated_tiff,
        "include_mask_tiff": args.mask_tiff,
        "include_metadata": args.metadata,
        "include_zip": args.zip,
        "overlay_color": args.overlay_color,
        "overlay_opacity": args.overlay_opacity,
        "output_crs": args.output_crs,
        "vector_formats": vector_formats,
        "filters": {
            "min_area_m2": args.min_area_m2,
            "max_area_m2": args.max_area_m2,
            "min_confidence": args.min_confidence,
            "geometry_types": args.geometry_type,
            "labels": args.label,
        },
    }


def _print_json(value: Any, compact: bool) -> None:
    indent = None if compact else 2
    separators = (",", ":") if compact else None
    print(json.dumps(value, ensure_ascii=False, indent=indent, separators=separators))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = APIClient(args.api_url, timeout=args.timeout)
        result = args.handler(client, args)
        if result is not None:
            _print_json(result, args.compact)
        return 0
    except (APIError, ValueError) as error:
        print(f"geoai: error: {error}", file=sys.stderr)
        return 1
