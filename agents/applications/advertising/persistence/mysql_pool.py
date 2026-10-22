"""Bounded connection pooling for the MySQL persistence adapter."""

import queue
import threading
import logging
import time
from typing import Any

class _MySQLPool:
    """Small bounded PyMySQL pool with ping-before-borrow semantics."""

    def __init__(self, connect: Any, *, pool_size: int, max_overflow: int):
        self._connect = connect
        self._capacity = max(1, int(pool_size)) + max(0, int(max_overflow))
        self._available: queue.Queue[Any] = queue.Queue(maxsize=self._capacity)
        self._created = 0
        self._condition = threading.Condition(threading.RLock())
        self._all: dict[int, Any] = {}
        self._checked_out: dict[int, Any] = {}
        self._closed = False
        self._close_failures = 0

    def acquire(self) -> Any:
        with self._condition:
            deadline = time.monotonic() + 30.0
            while not self._closed:
                connection = self._try_borrow_locked()
                if connection is not None:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("MySQL connection pool is exhausted")
                self._condition.wait(timeout=remaining)
            else:
                raise RuntimeError("MySQL connection pool is closed")
            self._checked_out[id(connection)] = connection
        try:
            connection.ping(reconnect=True)
            return connection
        except BaseException as error:
            try:
                self.discard(connection)
            except BaseException as cleanup_error:
                error.add_note(f"MySQL discard failed ({type(cleanup_error).__name__})")
            raise

    def _try_borrow_locked(self) -> Any:
        try:
            return self._available.get_nowait()
        except queue.Empty:
            if self._created >= self._capacity:
                return None
        connection = self._connect()
        self._created += 1
        self._all[id(connection)] = connection
        return connection

    def release(self, connection: Any) -> None:
        connection_id = id(connection)
        with self._condition:
            self._checked_out.pop(connection_id, None)
            if self._closed:
                try:
                    connection.close()
                finally:
                    self._all.pop(connection_id, None)
                    self._created = max(0, self._created - 1)
                    self._condition.notify()
                return
            try:
                self._available.put_nowait(connection)
            except queue.Full:
                connection.close()
                self._all.pop(connection_id, None)
                self._created = max(0, self._created - 1)
            self._condition.notify()

    def discard(self, connection: Any) -> None:
        connection_id = id(connection)
        with self._condition:
            self._checked_out.pop(connection_id, None)
            tracked = connection_id in self._all
            try:
                connection.close()
            finally:
                if tracked:
                    self._all.pop(connection_id, None)
                    self._created = max(0, self._created - 1)
                self._condition.notify()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            connections = list(self._all.values())
            self._all.clear()
            self._checked_out.clear()
            self._available = queue.Queue(maxsize=self._capacity)
            self._created = 0
            self._condition.notify_all()
        for connection in connections:
            try:
                connection.close()
            except Exception as error:
                with self._condition:
                    self._close_failures += 1
                logging.getLogger(__name__).warning(
                    "MySQL pooled connection close failed (%s)", type(error).__name__,
                )

    def metrics(self) -> dict[str, Any]:
        with self._condition:
            return {
                "capacity": self._capacity,
                "created": self._created,
                "idle": self._available.qsize(),
                "in_use": len(self._checked_out),
                "closed": self._closed,
                "close_failures": self._close_failures,
            }
