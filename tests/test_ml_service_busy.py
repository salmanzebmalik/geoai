import unittest

from app.services.ml_service_client import (
    DEFAULT_BUSY_RETRY_AFTER_SECONDS,
    MLServiceBusyError,
    _parse_retry_after_seconds,
)


class MLServiceBusyTests(unittest.TestCase):
    def test_parses_retry_after_header(self):
        self.assertEqual(
            _parse_retry_after_seconds("45"),
            45,
        )

    def test_missing_header_uses_default(self):
        self.assertEqual(
            _parse_retry_after_seconds(None),
            DEFAULT_BUSY_RETRY_AFTER_SECONDS,
        )

    def test_invalid_header_uses_default(self):
        self.assertEqual(
            _parse_retry_after_seconds("invalid"),
            DEFAULT_BUSY_RETRY_AFTER_SECONDS,
        )

    def test_retry_after_is_at_least_one_second(self):
        self.assertEqual(
            _parse_retry_after_seconds("0"),
            1,
        )

    def test_busy_exception_preserves_retry_value(self):
        error = MLServiceBusyError(retry_after_seconds=25)

        self.assertEqual(error.retry_after_seconds, 25)
        self.assertIn("GPU inference capacity", str(error))


if __name__ == "__main__":
    unittest.main()