"""Process-bounded execution for blocking embedding integrations."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import math
from threading import BoundedSemaphore, Lock
from typing import Any, Callable, Sequence


class EmbeddingRunner:
    """A timeout keeps its slot occupied until the underlying call finishes."""

    def __init__(self, *, max_workers: int = 2) -> None:
        if not 1 <= max_workers <= 16:
            raise ValueError("embedding workers must be between 1 and 16")
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="knowledge-embedding",
        )
        self._slots = BoundedSemaphore(max_workers)
        self._lock = Lock()
        self._in_flight = 0
        self._closed = False

    def embed(
        self, method: Callable, texts: Sequence[str], *, timeout: float,
    ) -> Any:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("embedding timeout must be positive and finite")
        if not self._slots.acquire(blocking=False):
            raise TimeoutError("embedding worker capacity exhausted")
        with self._lock:
            if self._closed:
                self._slots.release()
                raise RuntimeError("embedding runner is closed")
            self._in_flight += 1
            future = self._executor.submit(self._invoke, method, texts)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout as error:
            raise TimeoutError("knowledge embedding timed out") from error

    def _invoke(self, method: Callable, texts: Sequence[str]) -> Any:
        try:
            return method(texts)
        finally:
            with self._lock:
                self._in_flight -= 1
            self._slots.release()

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {"in_flight": self._in_flight}

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=True)


# Shared across tenants and Wiki instances, including calls that already timed out.
EMBEDDING_RUNNER = EmbeddingRunner()
