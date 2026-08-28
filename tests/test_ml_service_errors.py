import unittest
from unittest.mock import MagicMock, patch

import requests

from app.api.endpoints.segmentation import (
    build_ml_service_http_exception,
)
from app.services.ml_service_client import (
    MLServiceBusyError,
    MLServiceResponseError,
    MLServiceTimeoutError,
    MLServiceUnavailableError,
    call_ml_service,
)


class MLServiceErrorTests(unittest.TestCase):
    def call_with_session(
        self,
        http_session: MagicMock,
    ):
        with (
            patch(
                "app.services.ml_service_client."
                "get_shared_storage_relative_path",
                return_value="queries/test-query/input.tiff",
            ),
            patch(
                "app.services.ml_service_client."
                "get_http_session",
                return_value=http_session,
            ),
        ):
            return call_ml_service(
                query_id="test-query",
                input_image_path="/unused/input.tiff",
                model_type="tree",
            )

    def build_response(
        self,
        status_code: int = 200,
    ) -> MagicMock:
        response = MagicMock(spec=requests.Response)
        response.status_code = status_code
        response.headers = {}
        response.text = '{"result": "ok"}'
        response.json.return_value = {"result": "ok"}

        return response

    def test_timeout_is_classified(self):
        http_session = MagicMock()
        http_session.post.side_effect = (
            requests.exceptions.ReadTimeout(
                "internal ML timeout"
            )
        )

        with self.assertRaises(MLServiceTimeoutError):
            self.call_with_session(http_session)

    def test_connection_failure_is_classified(self):
        http_session = MagicMock()
        http_session.post.side_effect = (
            requests.exceptions.ConnectionError(
                "internal ML address"
            )
        )

        with self.assertRaises(
            MLServiceUnavailableError
        ):
            self.call_with_session(http_session)

    def test_http_failure_is_classified_safely(self):
        response = self.build_response(status_code=503)
        response.text = (
            "secret model traceback /private/model"
        )
        response.raise_for_status.side_effect = (
            requests.exceptions.HTTPError(
                "ML HTTP failure",
                response=response,
            )
        )

        http_session = MagicMock()
        http_session.post.return_value = response

        with self.assertRaises(
            MLServiceResponseError
        ) as caught:
            self.call_with_session(http_session)

        self.assertNotIn(
            "/private/model",
            str(caught.exception),
        )

    def test_invalid_json_is_classified(self):
        response = self.build_response()
        response.json.side_effect = ValueError(
            "Invalid JSON"
        )

        http_session = MagicMock()
        http_session.post.return_value = response

        with self.assertRaises(
            MLServiceResponseError
        ):
            self.call_with_session(http_session)

    def test_busy_response_preserves_retry_after(self):
        response = self.build_response(
            status_code=429
        )
        response.headers = {
            "Retry-After": "45",
        }

        http_session = MagicMock()
        http_session.post.return_value = response

        with self.assertRaises(
            MLServiceBusyError
        ) as caught:
            self.call_with_session(http_session)

        self.assertEqual(
            caught.exception.retry_after_seconds,
            45,
        )

    def test_http_status_mappings(self):
        cases = (
            (MLServiceTimeoutError(), 504),
            (MLServiceUnavailableError(), 503),
            (MLServiceResponseError(503), 502),
        )

        for error, expected_status in cases:
            with self.subTest(error=type(error).__name__):
                http_error = (
                    build_ml_service_http_exception(
                        error
                    )
                )

                self.assertEqual(
                    http_error.status_code,
                    expected_status,
                )


if __name__ == "__main__":
    unittest.main()