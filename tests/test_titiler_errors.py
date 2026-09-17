import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4
from tempfile import TemporaryDirectory
import requests
from fastapi import HTTPException

from app.api.endpoints.segmentation import (
    build_titiler_http_exception,
    predict_segmentation,
)

from app.schemas.segmentation import (
    BoundingBox,
    PredictionRequest,
)
from app.services.satellite_image_service import (
    TiTilerResponseError,
    TiTilerTimeoutError,
    TiTilerUnavailableError,
    fetch_satellite_image_from_titiler,
)


class TiTilerErrorTests(unittest.TestCase):
    def test_timeout_maps_to_504(self):
        exception = build_titiler_http_exception(
            TiTilerTimeoutError()
        )

        self.assertEqual(exception.status_code, 504)
        self.assertNotIn(
            "127.0.0.1",
            str(exception.detail),
        )

    def test_unavailable_maps_to_503(self):
        exception = build_titiler_http_exception(
            TiTilerUnavailableError()
        )

        self.assertEqual(exception.status_code, 503)

    def test_upstream_response_maps_to_502(self):
        exception = build_titiler_http_exception(
            TiTilerResponseError(status_code=500)
        )

        self.assertEqual(exception.status_code, 502)

    def test_timeout_removes_partial_download(self):
        response = MagicMock(spec=requests.Response)
        response.status_code = 200
        response.headers = {
            "content-type": "image/tiff",
        }
        response.url = "http://titiler.test/crop.tif"
        response.raise_for_status.return_value = None

        def timed_out_chunks(*args, **kwargs):
            yield b"partial-image-data"
            raise requests.exceptions.ReadTimeout(
                "Simulated streaming timeout"
            )

        response.iter_content.side_effect = timed_out_chunks

        http_session = MagicMock()
        http_session.get.return_value = response

        bbox = BoundingBox(
            min_lon=7.61,
            min_lat=51.95,
            max_lon=7.611,
            max_lat=51.951,
        )

        with TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)

            with (
                patch(
                    "app.services.satellite_image_service."
                    "get_shared_storage_dir",
                    return_value=storage_root,
                ),
                patch(
                    "app.services.satellite_image_service."
                    "get_http_session",
                    return_value=http_session,
                ),
            ):
                with self.assertRaises(TiTilerTimeoutError):
                    fetch_satellite_image_from_titiler(
                        query_id="timeout-test",
                        bbox=bbox,
                        source_type="ortho",
                    )

            query_directory = (
                storage_root / "queries" / "timeout-test"
            )

            remaining_parts = [
                path
                for path in query_directory.iterdir()
                if path.name.endswith(".part")
            ]

            self.assertEqual(remaining_parts, [])
            self.assertFalse(
                (query_directory / "input.tiff").exists()
            )

        response.close.assert_called_once()

    @patch(
        "app.api.endpoints.segmentation."
        "create_prediction"
    )
    def test_generic_prediction_error_is_hidden(
        self,
        create_prediction_mock: MagicMock,
    ):
        create_prediction_mock.side_effect = RuntimeError(
            "secret internal path /private/data"
        )

        request = PredictionRequest(
            bbox=BoundingBox(
                min_lon=7.62,
                min_lat=51.95,
                max_lon=7.621,
                max_lat=51.951,
            ),
            source_type="ortho",
            model_type="tree",
        )

        with self.assertRaises(HTTPException) as context:
            predict_segmentation(
                request=request,
                _prediction_slot=None,
                session=MagicMock(),
            )

        self.assertEqual(
            context.exception.status_code,
            500,
        )
        self.assertNotIn(
            "secret internal path",
            str(context.exception.detail),
        )


if __name__ == "__main__":
    unittest.main()
