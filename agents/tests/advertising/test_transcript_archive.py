import pytest

from agents.agent_harness import AgentMessage
from agents.applications.advertising.persistence.adapters import PersistenceTranscriptStore
from agents.applications.advertising.persistence.session_manager import SessionManager
from agents.applications.advertising.persistence.store import AdAgentStore


def test_archive_adapter_returns_only_bounded_user_text_from_owned_session():
    backend = AdAgentStore(":memory:")
    try:
        manager = SessionManager(backend)
        manager.create_session(
            "long", "owner", metadata={"tenant_id": "tenant-a"},
        )
        transcript = PersistenceTranscriptStore(backend)
        transcript.append(
            "long",
            [
                AgentMessage.user(
                    "旧请求" + "x" * 5000, turn_id="old",
                ),
                AgentMessage.tool(
                    "private tool result", tool_call_id="call", name="search",
                    turn_id="old",
                ),
                AgentMessage.user("新请求", turn_id="new"),
            ],
            tenant_id="tenant-a", user_id="owner",
        )
        rows = transcript.load_user_history(
            "long", tenant_id="tenant-a", user_id="owner", limit=2,
        )
        assert [row.role for row in rows] == ["user", "user"]
        assert [row.turn_id for row in rows] == ["old", "new"]
        assert len(rows[0].content) <= 1200
        assert rows[0].content.startswith("旧请求")
        assert "private tool result" not in str(rows)
        indexes = backend._get_conn().execute(
            "PRAGMA index_list(conversation_messages)"
        ).fetchall()
        assert "idx_conversation_user_history" in {
            row["name"] for row in indexes
        }
        plan = backend._get_conn().execute(
            """EXPLAIN QUERY PLAN SELECT message_id FROM conversation_messages
               WHERE session_id = ? AND role = 'user'
               ORDER BY created_at DESC LIMIT ?""",
            ("long", 2),
        ).fetchall()
        assert any(
            "idx_conversation_user_history" in row["detail"] for row in plan
        )
        with pytest.raises(PermissionError):
            transcript.load_user_history(
                "long", tenant_id="tenant-b", user_id="owner", limit=2,
            )
    finally:
        backend.close()


def test_archive_index_is_recreated_when_upgrading_a_version_26_database(tmp_path):
    path = str(tmp_path / "old.db")
    backend = AdAgentStore(path)
    connection = backend._get_conn()
    connection.execute("DROP INDEX idx_conversation_user_history")
    connection.execute("DELETE FROM schema_migrations WHERE version = 27")
    connection.commit()
    backend.close()

    upgraded = AdAgentStore(path)
    try:
        indexes = upgraded._get_conn().execute(
            "PRAGMA index_list(conversation_messages)"
        ).fetchall()
        assert "idx_conversation_user_history" in {
            row["name"] for row in indexes
        }
    finally:
        upgraded.close()


def test_mysql_archive_query_is_parameterized_and_bounded():
    from agents.applications.advertising.persistence.mysql_store import MySQLStore

    class Connection:
        def __init__(self):
            self.query = ""
            self.params = ()

        def execute(self, query, params):
            self.query = query
            self.params = params
            return self

        def fetchall(self):
            return [{"message_id": "old", "turn_id": "one", "content": "goal"}]

    connection = Connection()
    backend = MySQLStore.__new__(MySQLStore)
    backend._get_conn = lambda: connection
    assert backend.list_recent_user_messages("session-id", limit=10000) == [
        {"message_id": "old", "turn_id": "one", "content": "goal"},
    ]
    assert connection.params == ("session-id", 128)
    assert "role = 'user'" in connection.query
    assert "SUBSTR(content, 1, 1200)" in connection.query
