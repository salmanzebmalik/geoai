import tempfile
import unittest
from pathlib import Path

from portalocker import AlreadyLocked

from app.services.prediction_admission import (
    create_prediction_semaphore,
)


class PredictionAdmissionTests(unittest.TestCase):
    def test_rejects_second_process_when_capacity_is_one(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_directory = Path(directory)

            first = create_prediction_semaphore(
                maximum=1,
                directory=lock_directory,
            )

            second = create_prediction_semaphore(
                maximum=1,
                directory=lock_directory,
            )

            first.acquire()

            try:
                with self.assertRaises(AlreadyLocked):
                    second.acquire()
            finally:
                first.release()

    def test_slot_is_available_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_directory = Path(directory)

            first = create_prediction_semaphore(
                maximum=1,
                directory=lock_directory,
            )

            second = create_prediction_semaphore(
                maximum=1,
                directory=lock_directory,
            )

            first.acquire()
            first.release()

            second.acquire()
            second.release()

    def test_capacity_greater_than_one(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_directory = Path(directory)

            first = create_prediction_semaphore(
                maximum=2,
                directory=lock_directory,
            )

            second = create_prediction_semaphore(
                maximum=2,
                directory=lock_directory,
            )

            third = create_prediction_semaphore(
                maximum=2,
                directory=lock_directory,
            )

            first.acquire()
            second.acquire()

            try:
                with self.assertRaises(AlreadyLocked):
                    third.acquire()
            finally:
                first.release()
                second.release()

    def test_invalid_capacity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                create_prediction_semaphore(
                    maximum=0,
                    directory=Path(directory),
                )


if __name__ == "__main__":
    unittest.main()