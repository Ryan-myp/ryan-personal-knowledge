"""
persistence/store.py - SQLite 持久化存储

Tables:
- sessions: session metadata
- tool_calls: tool invocation history (with input/output/status)
- campaign_state: campaign resource state (shared across sessions)
"""

import json
import sqlite3
import logging
import hashlib
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional, List

logger = logging.getLogger(__name__)


WORKFLOW_TRANSITIONS = {
    "planned": {"planned", "running", "awaiting_confirmation", "blocked", "failed", "cancelled"},
    "running": {"running", "planned", "awaiting_confirmation", "blocked", "failed", "succeeded", "partially_failed", "recovery_required", "cancelled"},
    "awaiting_confirmation": {"awaiting_confirmation", "running", "blocked", "failed", "cancelled"},
    "partially_failed": {"partially_failed", "recovery_required", "succeeded", "failed", "cancelled"},
    "recovery_required": {"recovery_required", "running", "succeeded", "failed", "cancelled"},
    "blocked": {"blocked", "running", "failed", "recovery_required", "succeeded", "cancelled"},
    "failed": {"failed", "running", "recovery_required", "succeeded", "cancelled"},
    "succeeded": {"succeeded"},
    "cancelled": {"cancelled"},
}

WORKFLOW_ITEM_TRANSITIONS = {
    "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown"},
    "running": {"running", "succeeded", "failed", "unknown"},
    "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
    "failed": {"failed", "succeeded", "unknown"},
    "unknown": {"unknown", "succeeded", "failed"},
    "succeeded": {"succeeded"},
    "unsupported": {"unsupported"},
    "skipped": {"skipped"},
}


@dataclass
class CampaignRecord:
    """Campaign resource record"""
    id: str
    platform: str                    # meta/google/tiktok/dv360
    campaign_id: str                 # platform-side ID
    name: str
    status: str                      # ACTIVE/PAUSED/DRAFT
    objective: Optional[str] = None
    budget_daily: Optional[float] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)
    # Account/advertiser/customer scope is part of the identity.  Campaign IDs
    # are not safe to treat as globally unique across customers.
    account_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['metadata'] = json.dumps(d['metadata']) if d['metadata'] else '{}'
        return d
    
    @classmethod
    def from_row(cls, row) -> "CampaignRecord":
        # Handle both tuple (from DB cursor) and dict inputs
        if isinstance(row, dict):
            d = row
        else:
            columns = ['id', 'platform', 'campaign_id', 'name', 'status',
                       'objective', 'budget_daily', 'created_at', 'updated_at',
                       'metadata', 'account_id']
            d = dict(zip(columns, row))
        if d.get('metadata'):
            try:
                d['metadata'] = json.loads(d['metadata'])
            except:
                d['metadata'] = {}
        return cls(**d)


@dataclass
class ToolCallRecord:
    """Tool invocation record"""
    id: str
    session_id: str
    turn_id: str
    tool_name: str
    platform: str
    input_data: dict
    output_data: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None
    started_at: str = ""
    ended_at: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['input_data'] = json.dumps(d['input_data']) if d['input_data'] else '{}'
        d['output_data'] = json.dumps(d['output_data']) if d['output_data'] else None
        return d
    
    @classmethod
    def from_row(cls, row) -> "ToolCallRecord":
        # Handle both tuple (from DB cursor) and dict inputs
        if isinstance(row, dict):
            d = row
        else:
            columns = ['id', 'session_id', 'turn_id', 'tool_name', 'platform',
                       'input_data', 'output_data', 'success', 'error', 'started_at', 'ended_at']
            d = dict(zip(columns, row))
        for key in ['input_data', 'output_data']:
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except:
                    d[key] = {}
        return cls(**d)


class AdAgentStore:
    """
    Unified persistence layer (SQLite).
    
    Thread-safe: each connection is independent, read/write operations are locked.
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        account_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    );
    
    CREATE TABLE IF NOT EXISTS tool_calls (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        platform TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        success INTEGER NOT NULL DEFAULT 1,
        error TEXT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS campaign_state (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        objective TEXT,
        budget_daily REAL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        account_id TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
    CREATE INDEX IF NOT EXISTS idx_tool_calls_turn ON tool_calls(session_id, turn_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_platform ON campaign_state(platform, campaign_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaign_state(name);

    CREATE TABLE IF NOT EXISTS workflows (
        workflow_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        intent_type TEXT NOT NULL,
        execution_mode TEXT NOT NULL,
        status TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS workflow_items (
        item_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        platform TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        status TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        error TEXT,
        compensation_required INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_workflow_items_workflow ON workflow_items(workflow_id, sequence);

    CREATE TABLE IF NOT EXISTS write_reservations (
        idempotency_key TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS approvals (
        plan_fingerprint TEXT PRIMARY KEY,
        token_hash TEXT NOT NULL,
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        consumed_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_approvals_session ON approvals(session_id, status);
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-safe database connection (single connection mode)"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn
    
    def _init_db(self):
        """Initialize table structure"""
        with self._lock:
            conn = self._get_conn()
            conn.executescript(self.SCHEMA)
            # Backward-compatible migration for databases created before
            # account scoping was added.  This only changes local schema; it
            # never reads, rewrites, or derives values from credentials.
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(campaign_state)")
            }
            if "account_id" not in columns:
                conn.execute("ALTER TABLE campaign_state ADD COLUMN account_id TEXT")
            conn.commit()
    
    def close(self):
        """Close database connection"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    # -- Write idempotency -------------------------------------------------

    def reserve_write(self, idempotency_key: str, ttl_seconds: int = 300) -> bool:
        """Atomically reserve a write key across Runtime processes.

        Both pending and executed reservations block a duplicate within the
        TTL.  A stale pending reservation is replaceable so a crashed worker
        does not permanently prevent a later explicit retry.
        """
        with self._lock:
            conn = self._get_conn()
            now = datetime.now()
            row = conn.execute(
                "SELECT status, updated_at FROM write_reservations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                try:
                    age = (now - datetime.fromisoformat(row["updated_at"])).total_seconds()
                except (TypeError, ValueError):
                    age = 0
                if age < ttl_seconds:
                    return False
            timestamp = now.isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO write_reservations "
                "(idempotency_key, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (idempotency_key, "pending", timestamp, timestamp),
            )
            conn.commit()
            return True

    def mark_write_executed(self, idempotency_key: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE write_reservations SET status = ?, updated_at = ? WHERE idempotency_key = ?",
                ("executed", datetime.now().isoformat(), idempotency_key),
            )
            conn.commit()

    def release_write(self, idempotency_key: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM write_reservations WHERE idempotency_key = ? AND status = ?",
                (idempotency_key, "pending"),
            )
            conn.commit()

    # -- Approval records --------------------------------------------------

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def create_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str, expires_at: str,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO approvals
                   (plan_fingerprint, token_hash, session_id, user_id, account_id,
                    tool_name, expires_at, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    plan_fingerprint, self._token_hash(token), str(session_id),
                    str(user_id), str(account_id or ""), str(tool_name),
                    str(expires_at), now,
                ),
            )
            conn.commit()

    def get_approval(self, plan_fingerprint: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM approvals WHERE plan_fingerprint = ?",
                (plan_fingerprint,),
            ).fetchone()
            return dict(row) if row else None

    def validate_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str,
    ) -> tuple[bool, str]:
        row = self.get_approval(plan_fingerprint)
        if not row:
            return False, "approval record not found"
        if row.get("status") != "pending":
            return False, "approval has already been consumed"
        if row.get("token_hash") != self._token_hash(token):
            return False, "approval token mismatch"
        if str(row.get("session_id")) != str(session_id):
            return False, "approval session mismatch"
        if str(row.get("user_id")) != str(user_id):
            return False, "approval user mismatch"
        if str(row.get("account_id")) != str(account_id or ""):
            return False, "approval account mismatch"
        if str(row.get("tool_name")) != str(tool_name):
            return False, "approval tool mismatch"
        try:
            if datetime.fromisoformat(str(row.get("expires_at"))) <= datetime.now():
                return False, "approval expired"
        except (TypeError, ValueError):
            return False, "approval expiry is invalid"
        return True, ""

    def consume_approval(self, plan_fingerprint: str, token: str) -> bool:
        with self._lock:
            now = datetime.now().isoformat()
            cursor = self._get_conn().execute(
                """UPDATE approvals SET status = 'consumed', consumed_at = ?
                   WHERE plan_fingerprint = ? AND token_hash = ? AND status = 'pending'""",
                (now, plan_fingerprint, self._token_hash(token)),
            )
            self._get_conn().commit()
            return cursor.rowcount > 0
    
    # -- Session --
    
    def create_session(self, session_id: str, user_id: str, account_id: str = None, 
                       metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            sql = "INSERT OR REPLACE INTO sessions (session_id, user_id, account_id, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?)"
            conn.execute(sql, (session_id, user_id, account_id, now, now, json.dumps(metadata or {})))
            conn.commit()
    
    def update_session(self, session_id: str, metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            sql = "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?"
            conn.execute(sql, (datetime.now().isoformat(), json.dumps(metadata or {}), session_id))
            conn.commit()
    
    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if row:
                return dict(row)
            return None
    
    def list_sessions(self, user_id: str = None, limit: int = 50) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
    
    # -- Tool Calls --
    
    def record_tool_call(self, record: ToolCallRecord) -> None:
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO tool_calls 
                     (id, session_id, turn_id, tool_name, platform, input_data, output_data, 
                      success, error, started_at, ended_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            conn.execute(sql, (
                d['id'], d['session_id'], d['turn_id'], d['tool_name'], d['platform'],
                d['input_data'], d['output_data'], int(d['success']), d['error'],
                d['started_at'], d['ended_at']
            ))
            conn.commit()
    
    def list_tool_calls(self, session_id: str, turn_id: str = None, limit: int = 100) -> List[ToolCallRecord]:
        with self._lock:
            conn = self._get_conn()
            if turn_id:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? AND turn_id = ? ORDER BY started_at ASC LIMIT ?",
                    (session_id, turn_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY started_at DESC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            return [ToolCallRecord.from_row(dict(r)) for r in rows]
    
    # -- Campaign State --
    
    def save_campaign(self, record: CampaignRecord) -> None:
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO campaign_state 
                     (id, platform, campaign_id, name, status, objective, budget_daily,
                      created_at, updated_at, metadata, account_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT(id) DO UPDATE SET
                       name = excluded.name,
                       status = excluded.status,
                       objective = excluded.objective,
                       budget_daily = excluded.budget_daily,
                       updated_at = excluded.updated_at,
                       metadata = excluded.metadata,
                       account_id = excluded.account_id"""
            conn.execute(sql, (
                d['id'], d['platform'], d['campaign_id'], d['name'], d['status'],
                d['objective'], d['budget_daily'], d['created_at'], d['updated_at'],
                d['metadata'], d['account_id']
            ))
            conn.commit()
    
    def get_campaign(
        self, platform: str, campaign_id: str, account_id: str = None
    ) -> Optional[CampaignRecord]:
        with self._lock:
            # Campaign IDs are only unique inside a provider account.  A
            # caller that omits account scope must not receive the newest
            # record from an arbitrary account.
            if account_id is None or account_id == "":
                return None
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                "AND account_id = ?",
                (platform, campaign_id, account_id),
            ).fetchone()
            return CampaignRecord.from_row(dict(row)) if row else None
    
    def list_campaigns(
        self, platform: str = None, status: str = None, limit: int = 100,
        account_id: str = None,
    ) -> List[CampaignRecord]:
        with self._lock:
            conn = self._get_conn()
            clauses = []
            params: list[Any] = []
            if platform:
                clauses.append("platform = ?")
                params.append(platform)
            if status:
                clauses.append("status = ?")
                params.append(status)
            if account_id:
                clauses.append("account_id = ?")
                params.append(account_id)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM campaign_state{where} ORDER BY updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [CampaignRecord.from_row(dict(r)) for r in rows]
    
    def update_campaign_status(
        self, platform: str, campaign_id: str, status: str,
        account_id: str = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            if account_id is None:
                cursor = conn.execute(
                    "UPDATE campaign_state SET status = ?, updated_at = ? "
                    "WHERE platform = ? AND campaign_id = ? AND account_id IS NULL",
                    (status, datetime.now().isoformat(), platform, campaign_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE campaign_state SET status = ?, updated_at = ? "
                    "WHERE platform = ? AND campaign_id = ? AND account_id = ?",
                    (status, datetime.now().isoformat(), platform, campaign_id, account_id),
                )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_campaign(
        self, platform: str, campaign_id: str, account_id: str = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            if account_id is None:
                cursor = conn.execute(
                    "DELETE FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                    "AND account_id IS NULL",
                    (platform, campaign_id),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                    "AND account_id = ?",
                    (platform, campaign_id, account_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    # -- Workflow audit / compensation ---------------------------------

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned", metadata: dict = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO workflows
                   (workflow_id, session_id, intent_type, execution_mode, status,
                    metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (workflow_id, session_id, intent_type, execution_mode, status,
                 json.dumps(metadata or {}), now, now),
            )
            conn.commit()

    def update_workflow(
        self, workflow_id: str, status: str, metadata: dict = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflows WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            if not current:
                return False
            current_status = str(current[0])
            if status not in WORKFLOW_TRANSITIONS.get(current_status, set()):
                logger.warning(
                    "Rejected invalid workflow transition %s -> %s for %s",
                    current_status, status, workflow_id,
                )
                return False
            if metadata is None:
                cursor = conn.execute(
                    "UPDATE workflows SET status = ?, updated_at = ? WHERE workflow_id = ?",
                    (status, datetime.now().isoformat(), workflow_id),
                )
            else:
                existing = conn.execute(
                    "SELECT metadata FROM workflows WHERE workflow_id = ?",
                    (workflow_id,),
                ).fetchone()
                merged_metadata = {}
                if existing and existing[0]:
                    try:
                        merged_metadata = json.loads(existing[0]) or {}
                    except (TypeError, ValueError):
                        merged_metadata = {}
                merged_metadata.update(metadata)
                cursor = conn.execute(
                    """UPDATE workflows SET status = ?, metadata = ?, updated_at = ?
                       WHERE workflow_id = ?""",
                    (status, json.dumps(merged_metadata), datetime.now().isoformat(), workflow_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def add_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: dict = None, error: str = None,
        compensation_required: bool = False,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO workflow_items
                   (item_id, workflow_id, sequence, platform, tool_name, status,
                    input_data, output_data, error, compensation_required,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id, workflow_id, sequence, platform, tool_name, status,
                    json.dumps(input_data or {}),
                    json.dumps(output_data) if output_data is not None else None,
                    error, int(compensation_required), now, now,
                ),
            )
            conn.commit()

    def get_workflow(self, workflow_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            try:
                result["metadata"] = json.loads(result.get("metadata") or "{}")
            except (TypeError, ValueError):
                result["metadata"] = {}
            result["items"] = self.list_workflow_items(workflow_id)
            return result

    def list_workflow_items(self, workflow_id: str) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM workflow_items WHERE workflow_id = ? ORDER BY sequence ASC",
                (workflow_id,),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                for key in ("input_data", "output_data"):
                    if item.get(key):
                        try:
                            item[key] = json.loads(item[key])
                        except (TypeError, ValueError):
                            item[key] = {}
                item["compensation_required"] = bool(item.get("compensation_required"))
                items.append(item)
        return items

    def update_workflow_item(
        self,
        workflow_id: str,
        sequence: int,
        status: str,
        output_data: Optional[dict] = None,
        error: Optional[str] = None,
        compensation_required: Optional[bool] = None,
    ) -> bool:
        """Update one item during an explicitly verified reconciliation."""
        assignments = ["status = ?", "error = ?", "updated_at = ?"]
        values: list[Any] = [status, error, datetime.now().isoformat()]
        if output_data is not None:
            assignments.append("output_data = ?")
            values.append(json.dumps(output_data))
        if compensation_required is not None:
            assignments.append("compensation_required = ?")
            values.append(int(compensation_required))
        values.extend([workflow_id, int(sequence)])
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflow_items WHERE workflow_id = ? AND sequence = ?",
                (workflow_id, int(sequence)),
            ).fetchone()
            if not current:
                return False
            current_status = str(current[0])
            if status not in WORKFLOW_ITEM_TRANSITIONS.get(current_status, set()):
                logger.warning(
                    "Rejected invalid workflow item transition %s -> %s for %s/%s",
                    current_status, status, workflow_id, sequence,
                )
                return False
            cursor = conn.execute(
                f"UPDATE workflow_items SET {', '.join(assignments)} "
                "WHERE workflow_id = ? AND sequence = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """List non-terminal workflows for an operator/recovery worker."""
        statuses = ("failed", "partially_failed", "recovery_required", "blocked")
        placeholders = ",".join("?" for _ in statuses)
        params: list[Any] = list(statuses)
        query = (
            "SELECT w.* FROM workflows w JOIN sessions s "
            f"ON s.session_id = w.session_id WHERE w.status IN ({placeholders})"
        )
        if user_id is not None:
            query += " AND s.user_id = ?"
            params.append(str(user_id))
        query += " ORDER BY w.updated_at ASC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata"] = json.loads(item.get("metadata") or "{}")
                except (TypeError, ValueError):
                    item["metadata"] = {}
                result.append(item)
            return result

    def mark_workflow_items_for_compensation(
        self, workflow_id: str, sequences: list[int]
    ) -> None:
        if not sequences:
            return
        placeholders = ",".join("?" for _ in sequences)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                f"""UPDATE workflow_items SET compensation_required = 1,
                       updated_at = ? WHERE workflow_id = ?
                       AND sequence IN ({placeholders})""",
                (datetime.now().isoformat(), workflow_id, *sequences),
            )
            conn.commit()
