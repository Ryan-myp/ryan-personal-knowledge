import sqlite3

import pytest

from scripts.advertising.restore_legacy_session_history import (
    migrate_legacy_sessions,
)


def create_legacy_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE conversation_messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
        CREATE TABLE dap_agent_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        );
        INSERT INTO sessions VALUES
            ('legacy-session', 'default', 'web_user', '2026-08-25', '2026-08-26'),
            ('current-session', 'default', 'ad-agent-service', '2026-10-19', '2026-10-19'),
            ('other-tenant-session', 'other-tenant', 'web_user', '2026-08-25', '2026-08-26'),
            ('test-operator-session', 'default', 'google-live-test-operator', '2026-09-08', '2026-09-08');
        INSERT INTO conversation_messages VALUES
            ('legacy-message', 'legacy-session', 'old conversation');
        INSERT INTO dap_agent_sessions VALUES
            ('foreign-session', 'dap-agent-user');
        """
    )
    connection.commit()
    connection.close()


def session_owner(connection, session_id):
    return connection.execute(
        "SELECT tenant_id, user_id FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()


def test_preview_is_read_only_and_limits_migration_to_requested_scope(tmp_path):
    database = tmp_path / "ad_agent.db"
    create_legacy_database(database)

    result = migrate_legacy_sessions(
        database,
        tenant_id="default",
        source_user_id="web_user",
        target_user_id="ad-agent-service",
    )

    assert result.session_count == 1
    assert result.applied is False
    assert result.backup_path is None
    connection = sqlite3.connect(database)
    assert session_owner(connection, "legacy-session") == ("default", "web_user")
    connection.close()
    assert not (tmp_path / "private" / "backups").exists()


def test_apply_backups_then_reassigns_only_legacy_sessions(tmp_path):
    database = tmp_path / "ad_agent.db"
    create_legacy_database(database)

    result = migrate_legacy_sessions(
        database,
        tenant_id="default",
        source_user_id="web_user",
        target_user_id="ad-agent-service",
        apply=True,
    )

    assert result.session_count == 1
    assert result.applied is True
    assert result.backup_path is not None
    assert result.backup_path.is_file()
    assert result.backup_path.stat().st_mode & 0o777 == 0o600

    connection = sqlite3.connect(database)
    assert session_owner(connection, "legacy-session") == (
        "default",
        "ad-agent-service",
    )
    assert session_owner(connection, "current-session") == (
        "default",
        "ad-agent-service",
    )
    assert session_owner(connection, "other-tenant-session") == (
        "other-tenant",
        "web_user",
    )
    assert session_owner(connection, "test-operator-session") == (
        "default",
        "google-live-test-operator",
    )
    assert connection.execute(
        "SELECT session_id, user_id FROM dap_agent_sessions"
    ).fetchall() == [("foreign-session", "dap-agent-user")]
    assert connection.execute(
        "SELECT content FROM conversation_messages WHERE session_id = ?",
        ("legacy-session",),
    ).fetchone() == ("old conversation",)
    connection.close()

    backup = sqlite3.connect(result.backup_path)
    assert session_owner(backup, "legacy-session") == ("default", "web_user")
    backup.close()


def test_migration_is_idempotent(tmp_path):
    database = tmp_path / "ad_agent.db"
    create_legacy_database(database)
    migrate_legacy_sessions(
        database,
        tenant_id="default",
        source_user_id="web_user",
        target_user_id="ad-agent-service",
        apply=True,
    )

    result = migrate_legacy_sessions(
        database,
        tenant_id="default",
        source_user_id="web_user",
        target_user_id="ad-agent-service",
        apply=True,
    )

    assert result.session_count == 0
    assert result.applied is False
    assert result.backup_path is None


@pytest.mark.parametrize(
    "source_user_id,target_user_id",
    [
        ("", "ad-agent-service"),
        ("web_user", ""),
        ("web_user", "web_user"),
    ],
)
def test_invalid_identity_scope_is_rejected(
    tmp_path,
    source_user_id,
    target_user_id,
):
    database = tmp_path / "ad_agent.db"
    create_legacy_database(database)

    with pytest.raises(ValueError):
        migrate_legacy_sessions(
            database,
            tenant_id="default",
            source_user_id=source_user_id,
            target_user_id=target_user_id,
        )


def test_missing_database_is_not_created(tmp_path):
    database = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        migrate_legacy_sessions(
            database,
            tenant_id="default",
            source_user_id="web_user",
            target_user_id="ad-agent-service",
        )

    assert not database.exists()
