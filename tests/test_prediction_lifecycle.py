import unittest
from unittest.mock import MagicMock

from app.db.models import (
    PredictionStatus,
    SegmentationQuery,
)
from app.services.segmentation_service import (
    mark_prediction_failed,
    update_prediction_status,
)


def build_query() -> SegmentationQuery:
    return SegmentationQuery(
        min_lat=51.95,
        max_lat=51.951,
        min_lon=7.61,
        max_lon=7.611,
        status=PredictionStatus.PREPARING.value,
        progress_percent=10,
        status_message="Preparing imagery",
        prediction_result={},
    )


class PredictionLifecycleTests(unittest.TestCase):
    def test_updates_prediction_stage(self):
        query = build_query()
        session = MagicMock()

        update_prediction_status(
            query,
            session,
            status=PredictionStatus.INFERENCING,
            progress_percent=45,
            status_message="Running model inference",
        )

        self.assertEqual(
            query.status,
            PredictionStatus.INFERENCING.value,
        )
        self.assertEqual(query.progress_percent, 45)
        self.assertEqual(
            query.status_message,
            "Running model inference",
        )
        self.assertIsNotNone(query.started_at)
        self.assertIsNotNone(query.updated_at)

        session.add.assert_called_once_with(query)
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(query)

    def test_completed_status_sets_completion_time(self):
        query = build_query()
        session = MagicMock()

        update_prediction_status(
            query,
            session,
            status=PredictionStatus.COMPLETED,
            progress_percent=100,
            status_message="Prediction completed",
        )

        self.assertEqual(query.progress_percent, 100)
        self.assertIsNotNone(query.completed_at)

    def test_failure_records_error_information(self):
        query = build_query()
        session = MagicMock()

        mark_prediction_failed(
            query,
            session,
            RuntimeError("Test inference failure"),
        )

        self.assertEqual(
            query.status,
            PredictionStatus.FAILED.value,
        )
        self.assertEqual(
            query.error_code,
            "prediction_failed",
        )
        self.assertEqual(
            query.error_message,
            "Test inference failure",
        )
        self.assertIsNotNone(query.completed_at)

    def test_invalid_progress_is_rejected(self):
        query = build_query()
        session = MagicMock()

        with self.assertRaises(ValueError):
            update_prediction_status(
                query,
                session,
                status=PredictionStatus.INFERENCING,
                progress_percent=101,
                status_message="Invalid",
            )

        session.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()