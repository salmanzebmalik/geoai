from collections.abc import Iterator

from fastapi import HTTPException
from portalocker import AlreadyLocked

from app.core.config import settings
from app.services.prediction_admission import (
    create_prediction_semaphore,
)


def acquire_prediction_slot() -> Iterator[None]:
    semaphore = create_prediction_semaphore()

    try:
        semaphore.acquire()

    except AlreadyLocked as error:
        retry_after = (
            settings.prediction_busy_retry_after_seconds
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "Another prediction is already running. "
                f"Please try again in about "
                f"{retry_after} seconds."
            ),
            headers={
                "Retry-After": str(retry_after),
            },
        ) from error

    try:
        yield

    finally:
        semaphore.release()