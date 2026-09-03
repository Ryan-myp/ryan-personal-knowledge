"""Backend-neutral persistence errors.

Domain services should depend on these errors rather than importing a
specific database driver's exception classes.  This keeps the current SQLite
backend replaceable by MySQL/PostgreSQL without changing business code.
"""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base error raised by a persistence backend."""


class PersistenceConflictError(PersistenceError):
    """A uniqueness or optimistic-concurrency constraint was violated."""
