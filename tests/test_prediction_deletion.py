import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.db.database import get_session
from app.main import app
from app.services.segmentation_service import (
    PredictionDeletionError,
    PredictionNotDeletableError,
    delete_prediction,
)


def build_query(
    query_id: UUID,
    *,
    status: str = "completed",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=query_id,
        status=status,
    )


class DeletePredictionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query_id = uuid4()
        self.session = MagicMock()

    def test_returns_false_when_prediction_does_not_exist(self):
        self.session.get.return_value = None

        deleted = delete_prediction(
            query_id=self.query_id,
            session=self.session,
        )

        self.assertFalse(deleted)
        self.session.delete.assert_not_called()
        self.session.commit.assert_not_called()

    def test_rejects_active_prediction(self):
        self.session.get.return_value = build_query(
            self.query_id,
            status="inferencing",
        )

        with tempfile.TemporaryDirectory() as temp_directory:
            storage_root = Path(temp_directory)

            with patch(
                "app.services.segmentation_service.settings",
                SimpleNamespace(
                    shared_storage_path=storage_root,
                ),
            ):
                with self.assertRaises(
                    PredictionNotDeletableError
                ):
                    delete_prediction(
                        query_id=self.query_id,
                        session=self.session,
                    )

        self.session.delete.assert_not_called()
        self.session.commit.assert_not_called()

    def test_deletes_database_row_and_prediction_files(self):
        query = build_query(self.query_id)
        self.session.get.return_value = query

        with tempfile.TemporaryDirectory() as temp_directory:
            storage_root = Path(temp_directory)
            query_directory = (
                storage_root
                / "queries"
                / str(self.query_id)
            )

            export_directory = query_directory / "exports"
            export_directory.mkdir(parents=True)

            (query_directory / "input.tiff").write_bytes(
                b"test-raster"
            )
            (query_directory / "prediction.geojson").write_text(
                '{"type": "FeatureCollection", "features": []}',
                encoding="utf-8",
            )
            (export_directory / "result.zip").write_bytes(
                b"test-export"
            )

            with patch(
                "app.services.segmentation_service.settings",
                SimpleNamespace(
                    shared_storage_path=storage_root,
                ),
            ):
                deleted = delete_prediction(
                    query_id=self.query_id,
                    session=self.session,
                )

            self.assertTrue(deleted)
            self.assertFalse(query_directory.exists())

            trash_directory = storage_root / "queries" / ".trash"
            self.assertTrue(trash_directory.exists())
            self.assertEqual(
                list(trash_directory.iterdir()),
                [],
            )

        self.session.delete.assert_called_once_with(query)
        self.session.commit.assert_called_once()
        self.session.rollback.assert_not_called()

    def test_deletes_row_when_storage_is_already_missing(self):
        query = build_query(self.query_id)
        self.session.get.return_value = query

        with tempfile.TemporaryDirectory() as temp_directory:
            storage_root = Path(temp_directory)

            with patch(
                "app.services.segmentation_service.settings",
                SimpleNamespace(
                    shared_storage_path=storage_root,
                ),
            ):
                deleted = delete_prediction(
                    query_id=self.query_id,
                    session=self.session,
                )

        self.assertTrue(deleted)
        self.session.delete.assert_called_once_with(query)
        self.session.commit.assert_called_once()

    def test_restores_files_when_database_deletion_fails(self):
        query = build_query(self.query_id)
        self.session.get.return_value = query
        self.session.commit.side_effect = RuntimeError(
            "Database unavailable"
        )

        with tempfile.TemporaryDirectory() as temp_directory:
            storage_root = Path(temp_directory)
            query_directory = (
                storage_root
                / "queries"
                / str(self.query_id)
            )
            query_directory.mkdir(parents=True)

            result_file = query_directory / "prediction.geojson"
            result_file.write_text(
                '{"type": "FeatureCollection"}',
                encoding="utf-8",
            )

            with patch(
                "app.services.segmentation_service.settings",
                SimpleNamespace(
                    shared_storage_path=storage_root,
                ),
            ):
                with self.assertRaises(
                    PredictionDeletionError
                ):
                    delete_prediction(
                        query_id=self.query_id,
                        session=self.session,
                    )

            self.assertTrue(query_directory.exists())
            self.assertTrue(result_file.exists())

            trash_directory = storage_root / "queries" / ".trash"
            self.assertEqual(
                list(trash_directory.iterdir()),
                [],
            )

        self.session.rollback.assert_called_once()

    def test_rejects_symbolic_link_storage_path(self):
        query = build_query(self.query_id)
        self.session.get.return_value = query

        with tempfile.TemporaryDirectory() as temp_directory:
            storage_root = Path(temp_directory)
            queries_root = storage_root / "queries"
            queries_root.mkdir(parents=True)

            outside_directory = storage_root / "outside"
            outside_directory.mkdir()

            query_path = queries_root / str(self.query_id)
            query_path.symlink_to(
                outside_directory,
                target_is_directory=True,
            )

            with patch(
                "app.services.segmentation_service.settings",
                SimpleNamespace(
                    shared_storage_path=storage_root,
                ),
            ):
                with self.assertRaises(
                    PredictionDeletionError
                ):
                    delete_prediction(
                        query_id=self.query_id,
                        session=self.session,
                    )

            self.assertTrue(outside_directory.exists())

        self.session.delete.assert_not_called()
        self.session.commit.assert_not_called()


class DeletePredictionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query_id = uuid4()
        self.session = MagicMock()
        self.previous_overrides = (
            app.dependency_overrides.copy()
        )

        def override_get_session():
            yield self.session

        app.dependency_overrides[get_session] = (
            override_get_session
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(
            self.previous_overrides
        )

    @patch(
        "app.api.endpoints.segmentation.delete_prediction"
    )
    def test_endpoint_returns_204_after_deletion(
        self,
        delete_mock: MagicMock,
    ):
        delete_mock.return_value = True

        response = self.client.delete(
            f"/api/segmentation/results/{self.query_id}"
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

        delete_mock.assert_called_once_with(
            query_id=self.query_id,
            session=self.session,
        )

    @patch(
        "app.api.endpoints.segmentation.delete_prediction"
    )
    def test_endpoint_returns_404_when_not_found(
        self,
        delete_mock: MagicMock,
    ):
        delete_mock.return_value = False

        response = self.client.delete(
            f"/api/segmentation/results/{self.query_id}"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "Prediction not found.",
        )

    @patch(
        "app.api.endpoints.segmentation.delete_prediction"
    )
    def test_endpoint_returns_409_for_active_prediction(
        self,
        delete_mock: MagicMock,
    ):
        delete_mock.side_effect = (
            PredictionNotDeletableError(
                "This prediction is still being processed "
                "and cannot be deleted."
            )
        )

        response = self.client.delete(
            f"/api/segmentation/results/{self.query_id}"
        )

        self.assertEqual(response.status_code, 409)

    @patch(
        "app.api.endpoints.segmentation.delete_prediction"
    )
    def test_endpoint_hides_internal_deletion_errors(
        self,
        delete_mock: MagicMock,
    ):
        delete_mock.side_effect = PredictionDeletionError(
            "Sensitive internal failure information"
        )

        response = self.client.delete(
            f"/api/segmentation/results/{self.query_id}"
        )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(
            "Sensitive internal failure information",
            response.text,
        )
        self.assertEqual(
            response.json()["detail"],
            (
                "The prediction could not be deleted safely. "
                "Please try again."
            ),
        )


if __name__ == "__main__":
    unittest.main()