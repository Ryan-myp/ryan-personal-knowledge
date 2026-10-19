#!/usr/bin/env python3
"""Expose legacy single-user web conversations to the current service identity."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_TENANT_ID = "default"
LEGACY_USER_ID = "web_user"
SERVICE_USER_ID = "ad-agent-service"


@dataclass(frozen=True)
class MigrationResult:
    session_count: int
    applied: bool
    backup_path: Path | None = None


def _validate_scope(tenant_id: str, source_user_id: str, target_user_id: str) -> None:
    values = (tenant_id, source_user_id, target_user_id)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("tenant and user identities must be non-empty text")
    if source_user_id == target_user_id:
        raise ValueError("source and target users must be different")


def _open_read_only(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=30,
    )
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def _legacy_session_count(
    connection: sqlite3.Connection,
    *,
    tenant_id: str,
    source_user_id: str,
) -> int:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sessions'"
    ).fetchone()
    if not exists:
        raise ValueError("database does not contain the sessions table")
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(sessions)")
    }
    if not {"session_id", "tenant_id", "user_id"} <= columns:
        raise ValueError("sessions table is missing required identity columns")
    return int(connection.execute(
        "SELECT COUNT(*) FROM sessions WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, source_user_id),
    ).fetchone()[0])


def _create_backup(database_path: Path) -> Path:
    backup_directory = database_path.parent / "private" / "backups"
    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"history-{timestamp}-",
        suffix=".db",
        dir=backup_directory,
    )
    os.close(descriptor)
    backup_path = Path(temporary_name)
    try:
        with _open_read_only(database_path) as source:
            with sqlite3.connect(backup_path, timeout=30) as destination:
                source.backup(destination)
                integrity = destination.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise RuntimeError("database backup failed integrity verification")
        os.chmod(backup_path, 0o600)
        return backup_path
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise


def migrate_legacy_sessions(
    database_path: Path | str,
    *,
    tenant_id: str,
    source_user_id: str,
    target_user_id: str,
    apply: bool = False,
) -> MigrationResult:
    """Preview or migrate only sessions in the exact legacy tenant/user scope."""
    _validate_scope(tenant_id, source_user_id, target_user_id)
    path = Path(database_path).expanduser().resolve()
    with _open_read_only(path) as connection:
        session_count = _legacy_session_count(
            connection,
            tenant_id=tenant_id,
            source_user_id=source_user_id,
        )
    if not apply or session_count == 0:
        return MigrationResult(session_count=session_count, applied=False)

    backup_path = _create_backup(path)
    connection = sqlite3.connect(path, timeout=30)
    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE sessions
            SET user_id = ?
            WHERE tenant_id = ? AND user_id = ?
            """,
            (target_user_id, tenant_id, source_user_id),
        )
        updated_count = int(cursor.rowcount)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return MigrationResult(
        session_count=updated_count,
        applied=updated_count > 0,
        backup_path=backup_path,
    )


def _default_database_path() -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    return repository_root / "agents" / "ad_agent" / "ad_agent.db"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=_default_database_path(),
        help="SQLite database used by the local advertising service",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create a private backup and reassign the identified legacy sessions",
    )
    arguments = parser.parse_args(argv)

    try:
        result = migrate_legacy_sessions(
            arguments.database,
            tenant_id=DEFAULT_TENANT_ID,
            source_user_id=LEGACY_USER_ID,
            target_user_id=SERVICE_USER_ID,
            apply=arguments.apply,
        )
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
        parser.exit(1, f"migration failed: {type(error).__name__}: {error}\n")

    print(json.dumps({
        "database": str(arguments.database.expanduser().resolve()),
        "tenant_id": DEFAULT_TENANT_ID,
        "source_user_id": LEGACY_USER_ID,
        "target_user_id": SERVICE_USER_ID,
        "session_count": result.session_count,
        "applied": result.applied,
        "backup_path": str(result.backup_path) if result.backup_path else None,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
