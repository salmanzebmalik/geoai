from pathlib import Path

from portalocker.utils import NamedBoundedSemaphore

from app.core.config import settings


PREDICTION_SEMAPHORE_NAME = "geoai-backend-predictions"


def get_prediction_lock_directory() -> Path:
    lock_directory = (
        settings.shared_storage_path
        / ".locks"
        / "predictions"
    )

    lock_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return lock_directory


def create_prediction_semaphore(
    *,
    maximum: int | None = None,
    directory: Path | None = None,
) -> NamedBoundedSemaphore:
    capacity = (
        settings.max_concurrent_predictions
        if maximum is None
        else maximum
    )

    if capacity < 1:
        raise ValueError(
            "Prediction capacity must be at least 1"
        )

    lock_directory = (
        get_prediction_lock_directory()
        if directory is None
        else directory
    )

    lock_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return NamedBoundedSemaphore(
        maximum=capacity,
        name=PREDICTION_SEMAPHORE_NAME,
        directory=str(lock_directory),
        timeout=0,
        fail_when_locked=True,
    )