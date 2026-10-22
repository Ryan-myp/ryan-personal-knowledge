"""Buffered cursors and transaction ownership for MySQL."""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Optional
from pymysql.err import IntegrityError, OperationalError
from .mysql_pool import _MySQLPool
from .mysql_sql import _translate_sql

class _MySQLRow(dict):
    """Dict row that also preserves SQLite-style integer indexing."""

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        super().__init__(zip(columns, values))
        self._columns = columns
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class _MySQLCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor
        self._columns: list[str] = []
        self._rows: list[tuple[Any, ...]] = []
        self._offset = 0

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def execute(self, statement: str, params: Any = None) -> "_MySQLCursor":
        try:
            self._cursor.execute(statement, params or ())
        except IntegrityError as error:
            raise sqlite3.IntegrityError(str(error)) from error
        self._columns = [str(item[0]) for item in (self._cursor.description or ())]
        if self._columns:
            self._rows = list(self._cursor.fetchall())
        return self

    def executemany(
        self, statement: str, rows: Any,
    ) -> "_MySQLCursor":
        try:
            self._cursor.executemany(statement, rows)
        except IntegrityError as error:
            raise sqlite3.IntegrityError(str(error)) from error
        self._columns = [
            str(item[0]) for item in (self._cursor.description or ())
        ]
        if self._columns:
            self._rows = list(self._cursor.fetchall())
        return self

    def fetchone(self) -> Optional[_MySQLRow]:
        row = self._rows[self._offset] if self._offset < len(self._rows) else None
        self._offset += 1
        return _MySQLRow(self._columns, row) if row is not None else None

    def fetchall(self) -> list[_MySQLRow]:
        rows = self._rows[self._offset:]
        self._offset = len(self._rows)
        return [_MySQLRow(self._columns, row) for row in rows]


class _MySQLConnection:
    def __init__(self, pool: _MySQLPool):
        self._pool = pool
        self._local = threading.local()

    def _transaction_connection(self) -> Any:
        return getattr(self._local, "connection", None)

    def execute(self, statement: str, params: Any = None) -> _MySQLCursor:
        return self._run_statement("execute", statement, params=params)

    def executemany(self, statement: str, rows: Any) -> _MySQLCursor:
        return self._run_statement("executemany", statement, rows=rows)

    def _run_statement(
        self,
        method: str,
        statement: str,
        *,
        params: Any = None,
        rows: Any = None,
    ) -> _MySQLCursor:
        import pymysql

        active = self._transaction_connection()
        connection = active or self._pool.acquire()
        borrowed = active is None
        discarded = False
        cursor = None
        operation_error: Optional[BaseException] = None
        try:
            cursor = connection.cursor(pymysql.cursors.Cursor)
            mysql_cursor = _MySQLCursor(cursor)
            if method == "execute":
                result = mysql_cursor.execute(_translate_sql(statement), params)
            else:
                result = mysql_cursor.executemany(_translate_sql(statement), rows)
            if borrowed:
                try:
                    connection.commit()
                except BaseException as exc:
                    self._discard_after_error(connection, exc)
                    discarded = True
                    raise
            return result
        except BaseException as exc:
            operation_error = exc
            if borrowed:
                discarded = self._recover_borrowed_connection(
                    connection, exc, pymysql, discarded,
                )
            raise
        finally:
            discarded = self._close_cursor(
                cursor, connection, borrowed, discarded, operation_error,
            )
            if borrowed and not discarded:
                self._pool.release(connection)

    def _recover_borrowed_connection(
        self,
        connection: Any,
        operation_error: BaseException,
        pymysql: Any,
        discarded: bool,
    ) -> bool:
        if discarded:
            return True
        try:
            connection.rollback()
        except BaseException as rollback_error:
            self._add_cleanup_note(
                operation_error,
                "MySQL rollback failed "
                f"({type(rollback_error).__name__}); connection discarded",
            )
            self._discard_after_error(connection, operation_error)
            return True
        if not isinstance(operation_error, Exception) or isinstance(
            operation_error, getattr(pymysql.err, "OperationalError", ()),
        ):
            self._discard_after_error(connection, operation_error)
            return True
        return False

    def _close_cursor(
        self,
        cursor: Any,
        connection: Any,
        borrowed: bool,
        discarded: bool,
        operation_error: Optional[BaseException],
    ) -> bool:
        if cursor is None:
            return discarded
        try:
            cursor.close()
        except BaseException as close_error:
            primary_error = operation_error or close_error
            if operation_error is not None:
                self._add_cleanup_note(
                    operation_error,
                    "MySQL cursor close failed "
                    f"({type(close_error).__name__})",
                )
            if borrowed and not discarded:
                self._discard_after_error(connection, primary_error)
                discarded = True
            if operation_error is None:
                raise
        return discarded

    def _discard_after_error(
        self, connection: Any, operation_error: BaseException,
    ) -> None:
        try:
            self._pool.discard(connection)
        except BaseException as discard_error:
            self._add_cleanup_note(
                operation_error,
                "MySQL connection discard failed "
                f"({type(discard_error).__name__})",
            )

    @staticmethod
    def _add_cleanup_note(error: BaseException, note: str) -> None:
        add_note = getattr(error, "add_note", None)
        if callable(add_note):
            add_note(note)

    def executescript(self, script: str) -> None:
        # The checked-in schema contains no semicolons inside string literals.
        for statement in script.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            try:
                self.execute(statement)
            except OperationalError as error:
                # MySQL DDL bootstrap may encounter an existing index/table.
                if not error.args or error.args[0] not in {1050, 1061}:
                    raise

    def begin(self) -> None:
        if self._transaction_connection() is not None:
            raise RuntimeError("nested MySQL transactions are not supported")
        connection = self._pool.acquire()
        try:
            connection.begin()
        except BaseException:
            self._pool.discard(connection)
            raise
        self._local.connection = connection

    def commit(self) -> None:
        connection = self._transaction_connection()
        if connection is None:
            return
        try:
            connection.commit()
        except BaseException:
            self._pool.discard(connection)
            raise
        finally:
            self._local.connection = None
        self._pool.release(connection)

    def rollback(self) -> None:
        connection = self._transaction_connection()
        if connection is None:
            return
        try:
            connection.rollback()
        except BaseException:
            self._pool.discard(connection)
            raise
        finally:
            self._local.connection = None
        self._pool.release(connection)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(self):
        """Always roll back on cancellation while preserving the primary error."""
        self.begin()
        try:
            yield self
        except BaseException as error:
            try:
                self.rollback()
            except BaseException as cleanup_error:
                self._add_cleanup_note(
                    error, f"MySQL rollback failed ({type(cleanup_error).__name__})",
                )
            raise
        else:
            self.commit()


def _is_retryable_transaction_error(error: BaseException) -> bool:
    """Return whether MySQL aborted a transaction that is safe to retry."""
    code = None
    args = getattr(error, "args", ())
    if args:
        try:
            code = int(args[0])
        except (TypeError, ValueError):
            code = None
    # ER_LOCK_DEADLOCK and ER_LOCK_WAIT_TIMEOUT. Connection failures are not
    # retried here: the pool discards those connections and the caller can
    # apply its own request-level retry policy without duplicating mutations.
    return code in {1205, 1213}


def _retry_transaction(operation: Any, *, attempts: int = 3) -> Any:
    """Retry a complete claim transaction, never an individual SQL statement."""
    for attempt in range(max(1, int(attempts))):
        try:
            return operation()
        except Exception as exc:
            if attempt + 1 >= max(1, int(attempts)) or not _is_retryable_transaction_error(exc):
                raise
            time.sleep(min(0.25, 0.05 * (2 ** attempt)))
    raise AssertionError("unreachable")
