from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from geoai_cli.cli import build_parser
from geoai_cli.client import APIClient, APIError


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self.payload
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class RecordingClient:
    def __init__(self):
        self.calls = []

    def get(self, path, query=None):
        self.calls.append(("GET", path, query))
        return {"ok": True}

    def post(self, path, payload):
        self.calls.append(("POST", path, payload))
        return {"ok": True}


class CLICommandTests(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()
        self.client = RecordingClient()

    def invoke(self, arguments):
        args = self.parser.parse_args(arguments)
        return args.handler(self.client, args)

    def test_tree_prediction_payload(self):
        self.invoke(
            [
                "predict",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
                "--source-type",
                "satellite",
                "--model-type",
                "tree_satlas",
            ]
        )

        method, path, payload = self.client.calls[0]
        self.assertEqual((method, path), ("POST", "predict"))
        self.assertEqual(payload["model_type"], "tree_satlas")
        self.assertEqual(payload["source_type"], "satellite")
        self.assertEqual(payload["keywords"], [])
        self.assertEqual(payload["bbox"]["min_lon"], 7.61)

    def test_zeroshot_prediction_deduplicates_keywords(self):
        self.invoke(
            [
                "predict",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
                "--model-type",
                "zeroshot",
                "-k",
                "building",
                "-k",
                " building ",
                "-k",
                "car",
            ]
        )

        payload = self.client.calls[0][2]
        self.assertEqual(payload["keywords"], ["building", "car"])

    def test_zeroshot_requires_a_keyword(self):
        args = self.parser.parse_args(
            [
                "predict",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
                "--model-type",
                "zeroshot",
            ]
        )
        with self.assertRaisesRegex(ValueError, "--keyword is required"):
            args.handler(self.client, args)

    def test_predict_export_maps_all_export_options(self):
        self.invoke(
            [
                "predict-export",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
                "--mask-tiff",
                "--vector-format",
                "gpkg",
                "--output-crs",
                "EPSG:25832",
                "--min-area-m2",
                "5",
                "--min-confidence",
                "0.7",
                "--geometry-type",
                "Polygon",
                "--label",
                "tree",
            ]
        )

        method, path, payload = self.client.calls[0]
        self.assertEqual((method, path), ("POST", "export/predict"))
        options = payload["export"]
        self.assertTrue(options["include_mask_tiff"])
        self.assertEqual(options["vector_formats"], ["geojson", "gpkg"])
        self.assertEqual(options["output_crs"], "EPSG:25832")
        self.assertEqual(options["filters"]["min_area_m2"], 5.0)
        self.assertEqual(options["filters"]["min_confidence"], 0.7)
        self.assertEqual(options["filters"]["geometry_types"], ["Polygon"])
        self.assertEqual(options["filters"]["labels"], ["tree"])

    def test_export_list_filters_by_query(self):
        self.invoke(["exports", "list", "--query-id", "query-1"])
        self.assertEqual(
            self.client.calls[0],
            ("GET", "exports", {"query_id": "query-1"}),
        )

    def test_prediction_defaults_are_compatible(self):
        self.invoke(
            [
                "predict",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
            ]
        )

        payload = self.client.calls[0][2]

        self.assertEqual(payload["model_type"], "tree")
        self.assertEqual(payload["source_type"], "ortho")

    def test_rejects_incompatible_model_and_source(self):
        args = self.parser.parse_args(
            [
                "predict",
                "--bbox",
                "7.61",
                "51.95",
                "7.62",
                "51.96",
                "--source-type",
                "ortho",
                "--model-type",
                "tree_satlas",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not compatible",
        ):
            args.handler(self.client, args)

class APIClientTests(unittest.TestCase):
    def test_builds_relative_and_absolute_urls(self):
        client = APIClient("http://localhost:8013/api/segmentation")
        self.assertEqual(
            client._url("results", {"query_id": "a b"}),
            "http://localhost:8013/api/segmentation/results?query_id=a+b",
        )
        self.assertEqual(
            client._url("/api/segmentation/results/1/geojson"),
            "http://localhost:8013/api/segmentation/results/1/geojson",
        )

    @patch("geoai_cli.client.urlopen")
    def test_posts_json_and_decodes_response(self, urlopen):
        urlopen.return_value = FakeResponse(b'{"query_id": "abc"}')
        client = APIClient("http://localhost:8013/api/segmentation")

        response = client.post("predict", {"model_type": "tree"})

        self.assertEqual(response, {"query_id": "abc"})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            json.loads(request.data),
            {"model_type": "tree"},
        )

    @patch("geoai_cli.client.urlopen")
    def test_surfaces_api_error_detail(self, urlopen):
        urlopen.side_effect = HTTPError(
            "http://localhost/predict",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"detail": "invalid bbox"}'),
        )
        client = APIClient("http://localhost:8013/api/segmentation")

        with self.assertRaisesRegex(APIError, "invalid bbox"):
            client.get("results")

    @patch("geoai_cli.client.urlopen")
    def test_connection_failure_is_user_facing(self, urlopen):
        urlopen.side_effect = URLError("connection refused")
        client = APIClient("http://localhost:8013/api/segmentation")

        with self.assertRaisesRegex(APIError, "connection refused"):
            client.get("results")

    @patch("geoai_cli.client.urlopen")
    def test_download_is_written_atomically(self, urlopen):
        urlopen.return_value = FakeResponse(b"geojson-data")
        client = APIClient("http://localhost:8013/api/segmentation")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.geojson"
            path, size = client.download("results/1/geojson", destination)
            self.assertEqual(path.read_bytes(), b"geojson-data")
            self.assertEqual(size, 12)
            self.assertFalse((Path(directory) / ".result.geojson.part").exists())


if __name__ == "__main__":
    unittest.main()
