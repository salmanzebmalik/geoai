from threading import BoundedSemaphore, Lock


class InferenceGate:
    """Process-local admission control for expensive GPU inference."""

    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("Inference capacity must be at least 1")

        self.capacity = capacity
        self._semaphore = BoundedSemaphore(capacity)
        self._state_lock = Lock()
        self._active = 0

    def try_acquire(self) -> bool:
        acquired = self._semaphore.acquire(blocking=False)

        if not acquired:
            return False

        with self._state_lock:
            self._active += 1

        return True

    def release(self) -> None:
        with self._state_lock:
            if self._active <= 0:
                raise RuntimeError(
                    "Inference gate released without an active acquisition"
                )

            self._active -= 1

        self._semaphore.release()

    def snapshot(self) -> dict[str, int]:
        with self._state_lock:
            active = self._active

        return {
            "capacity": self.capacity,
            "active": active,
            "available": self.capacity - active,
        }