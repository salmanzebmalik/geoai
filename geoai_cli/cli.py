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
    _add_results_commands(commands)
    _add_exports_commands(commands)
    return parser


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


def _results_list(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get("results")


def _results_show(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get(f"results/{args.query_id}")


def _results_download(client: APIClient, args: argparse.Namespace) -> None:
    output = args.output or Path(f"prediction-{args.query_id}.geojson")
    _download(client, f"results/{args.query_id}/geojson", output)


def _exports_list(client: APIClient, args: argparse.Namespace) -> Any:
    return client.get("exports", query={"query_id": args.query_id})


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
