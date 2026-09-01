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
import time
from datetime import datetime, timedelta
from typing import Any, Optional, List

from .models import CampaignRecord, ToolCallRecord

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
    "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown", "skipped"},
    "running": {"running", "awaiting_confirmation", "succeeded", "failed", "unknown", "skipped"},
    "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
    "failed": {"failed", "succeeded", "unknown"},
    "unknown": {"unknown", "succeeded", "failed"},
    "succeeded": {"succeeded"},
    "unsupported": {"unsupported"},
    "skipped": {"skipped"},
}


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
        lease_owner TEXT,
        lease_expires_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS workflow_items (
        item_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        platform TEXT NOT NULL,
        account_id TEXT,
        tool_name TEXT NOT NULL,
        status TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        error TEXT,
        compensation_required INTEGER NOT NULL DEFAULT 0,
        resource_type TEXT,
        parent_resource_type TEXT,
        parent_sequence INTEGER,
        parent_resource_id TEXT,
        provider_resource_id TEXT,
        logical_resource_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_workflow_items_workflow ON workflow_items(workflow_id, sequence);

    CREATE TABLE IF NOT EXISTS skill_versions (
        version_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        files TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        published_at TEXT,
        evaluation_status TEXT NOT NULL DEFAULT 'not_run',
        evaluation_run_id TEXT,
        evaluation_report TEXT DEFAULT '{}',
        UNIQUE (tenant_id, skill_name, version)
    );

    CREATE TABLE IF NOT EXISTS skill_releases (
        tenant_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        version_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, skill_name),
        FOREIGN KEY (version_id) REFERENCES skill_versions(version_id)
    );
    CREATE INDEX IF NOT EXISTS idx_skill_versions_name
        ON skill_versions(tenant_id, skill_name, created_at DESC);

    CREATE TABLE IF NOT EXISTS skill_evaluation_runs (
        run_id TEXT PRIMARY KEY,
        version_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        report TEXT DEFAULT '{}',
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (version_id) REFERENCES skill_versions(version_id)
    );
    CREATE INDEX IF NOT EXISTS idx_skill_evaluation_runs_tenant
        ON skill_evaluation_runs(tenant_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS plugin_packages (
        package_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        plugin_id TEXT NOT NULL,
        version TEXT NOT NULL,
        manifest TEXT NOT NULL,
        files TEXT NOT NULL,
        package_digest TEXT NOT NULL,
        signature_verified INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'validated',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        activated_at TEXT,
        last_error TEXT,
        UNIQUE (tenant_id, plugin_id, version)
    );

    CREATE TABLE IF NOT EXISTS plugin_releases (
        tenant_id TEXT NOT NULL,
        plugin_id TEXT NOT NULL,
        package_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, plugin_id),
        FOREIGN KEY (package_id) REFERENCES plugin_packages(package_id)
    );
    CREATE INDEX IF NOT EXISTS idx_plugin_packages_tenant
        ON plugin_packages(tenant_id, plugin_id, created_at DESC);

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
            workflow_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(workflows)")
            }
            if "lease_owner" not in workflow_columns:
                conn.execute("ALTER TABLE workflows ADD COLUMN lease_owner TEXT")
            if "lease_expires_at" not in workflow_columns:
                conn.execute("ALTER TABLE workflows ADD COLUMN lease_expires_at TEXT")
            item_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(workflow_items)")
            }
            for column, definition in {
                "account_id": "TEXT",
                "resource_type": "TEXT",
                "parent_resource_type": "TEXT",
                "parent_sequence": "INTEGER",
                "parent_resource_id": "TEXT",
                "provider_resource_id": "TEXT",
                "logical_resource_id": "TEXT",
            }.items():
                if column not in item_columns:
                    conn.execute(
                        f"ALTER TABLE workflow_items ADD COLUMN {column} {definition}"
                    )
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

    # -- Managed Agent Skills -------------------------------------------

    @staticmethod
    def _skill_row(row: Any) -> Optional[dict]:
        if not row:
            return None
        value = dict(row)
        for key in ("files", "evaluation_report", "report"):
            raw = value.get(key)
            if isinstance(raw, str):
                try:
                    value[key] = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    value[key] = {}
        return value

    def create_skill_version(
        self, version_id: str, tenant_id: str, skill_name: str,
        version: str, files: dict[str, dict[str, Any]], sha256: str,
        created_by: str, status: str = "draft",
    ) -> dict:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO skill_versions
                   (version_id, tenant_id, skill_name, version, status, files,
                    sha256, created_by, created_at, evaluation_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_run')""",
                (
                    str(version_id), str(tenant_id), str(skill_name), str(version),
                    str(status), json.dumps(files, ensure_ascii=False, sort_keys=True),
                    str(sha256), str(created_by), now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(version_id),),
            ).fetchone()
            return self._skill_row(row) or {}

    def get_skill_version(
        self, tenant_id: str, skill_name: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            if version:
                row = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "AND skill_name = ? AND version = ?",
                    (str(tenant_id), str(skill_name), str(version)),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT v.* FROM skill_versions v
                       JOIN skill_releases r ON r.version_id = v.version_id
                       WHERE r.tenant_id = ? AND r.skill_name = ?""",
                    (str(tenant_id), str(skill_name)),
                ).fetchone()
            return self._skill_row(row)

    def list_skill_versions(
        self, tenant_id: str, skill_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            conn = self._get_conn()
            if skill_name:
                rows = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "AND skill_name = ? ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), str(skill_name), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), limit),
                ).fetchall()
            return [self._skill_row(row) for row in rows]

    def publish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE tenant_id = ? "
                "AND skill_name = ? AND version = ?",
                (str(tenant_id), str(skill_name), str(version)),
            ).fetchone()
            # Archived versions remain immutable and can be selected as an
            # explicit rollback target.  The release pointer is the source of
            # truth for what is currently active; version status alone must
            # not make rollback impossible.
            if not row:
                return None
            conn.execute(
                "UPDATE skill_versions SET status = 'archived' WHERE tenant_id = ? "
                "AND skill_name = ? AND status = 'published'",
                (str(tenant_id), str(skill_name)),
            )
            conn.execute(
                "UPDATE skill_versions SET status = 'published', published_at = ? "
                "WHERE version_id = ?",
                (now, str(row["version_id"])),
            )
            conn.execute(
                "INSERT INTO skill_releases (tenant_id, skill_name, version_id, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(tenant_id, skill_name) DO UPDATE SET "
                "version_id = excluded.version_id, updated_at = excluded.updated_at",
                (str(tenant_id), str(skill_name), str(row["version_id"]), now),
            )
            conn.commit()
            published = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(row["version_id"]),),
            ).fetchone()
            return self._skill_row(published)

    def unpublish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        """Remove the active release pointer and archive that version.

        The version remains available for audit or an explicit later rollback;
        only the tenant/Skill release pointer is removed.  The join and
        version check make this operation safe when an older API request tries
        to unpublish a release that has already been replaced.
        """
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT v.* FROM skill_versions v
                   JOIN skill_releases r ON r.version_id = v.version_id
                   WHERE r.tenant_id = ? AND r.skill_name = ?
                     AND v.version = ?""",
                (str(tenant_id), str(skill_name), str(version)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM skill_releases WHERE tenant_id = ? AND skill_name = ?",
                (str(tenant_id), str(skill_name)),
            )
            conn.execute(
                "UPDATE skill_versions SET status = 'archived' "
                "WHERE version_id = ? AND tenant_id = ?",
                (str(row["version_id"]), str(tenant_id)),
            )
            conn.commit()
            unpublished = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(row["version_id"]),),
            ).fetchone()
            return self._skill_row(unpublished)

    def set_skill_evaluation(
        self, version_id: str, tenant_id: str, status: str, run_id: Optional[str] = None,
        report: Optional[dict] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            sql = (
                "UPDATE skill_versions SET evaluation_status = ?, "
                "evaluation_run_id = ?, evaluation_report = ? "
                "WHERE version_id = ? AND tenant_id = ?"
            )
            params = [
                str(status), str(run_id) if run_id else None,
                json.dumps(report or {}, ensure_ascii=False, sort_keys=True),
                str(version_id), str(tenant_id),
            ]
            # A worker from an older retry must not overwrite the current
            # evaluation attached to this immutable version.
            if run_id:
                sql += " AND evaluation_run_id = ?"
                params.append(str(run_id))
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def create_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
        status: str = "queued",
    ) -> dict:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO skill_evaluation_runs
                   (run_id, version_id, tenant_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(run_id), str(version_id), str(tenant_id), str(status), now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(row) or {}

    def claim_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
    ) -> Optional[dict]:
        """Atomically claim one version for a queued evaluation.

        The version row is the durable single-flight lock.  Keeping the
        claim and run creation in one transaction prevents two API workers
        from evaluating the same immutable version concurrently, and gives a
        future MySQL/PostgreSQL backend a precise transaction contract to
        preserve.
        """
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT version_id, evaluation_status FROM skill_versions "
                "WHERE version_id = ? AND tenant_id = ?",
                (str(version_id), str(tenant_id)),
            ).fetchone()
            if not row or str(row["evaluation_status"]) in {"queued", "running"}:
                return None
            conn.execute(
                "INSERT INTO skill_evaluation_runs "
                "(run_id, version_id, tenant_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?)",
                (str(run_id), str(version_id), str(tenant_id), now, now),
            )
            cursor = conn.execute(
                "UPDATE skill_versions SET evaluation_status = 'queued', "
                "evaluation_run_id = ?, evaluation_report = '{}' "
                "WHERE version_id = ? AND tenant_id = ? "
                "AND evaluation_status NOT IN ('queued', 'running')",
                (str(run_id), str(version_id), str(tenant_id)),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return None
            conn.commit()
            claimed = conn.execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(claimed)

    def get_skill_evaluation(self, run_id: str, tenant_id: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(row)

    def update_skill_evaluation_run(
        self, run_id: str, tenant_id: str, status: str, report: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE skill_evaluation_runs SET status = ?, report = ?, error = ?, "
                "updated_at = ? WHERE run_id = ? AND tenant_id = ?",
                (
                    str(status),
                    json.dumps(report or {}, ensure_ascii=False, sort_keys=True),
                    str(error) if error else None,
                    datetime.now().isoformat(),
                    str(run_id), str(tenant_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def recover_stale_skill_evaluations(
        self, stale_after_seconds: float = 900.0,
    ) -> int:
        """Mark evaluations interrupted by a process failure as retryable.

        Evaluation workers are process-local, so a queued/running row cannot
        be resumed after the process that owned it disappears.  The update is
        guarded by both ``run_id`` and the version's current run ID, which
        keeps a late worker from overwriting a newer retry.  A future
        multi-process backend should preserve this atomic lease-recovery
        contract, even if it implements it with row locks or a lease table.
        """
        try:
            age = max(0.0, float(stale_after_seconds))
        except (TypeError, ValueError):
            raise ValueError("stale_after_seconds must be a non-negative number")
        cutoff = (datetime.now() - timedelta(seconds=age)).isoformat()
        recovered = 0
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT run_id, version_id FROM skill_evaluation_runs "
                "WHERE status IN ('queued', 'running') AND updated_at <= ?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                run_id = str(row["run_id"])
                version_id = str(row["version_id"])
                now = datetime.now().isoformat()
                report = {
                    "recovered": True,
                    "reason": "evaluation worker interrupted before completion",
                    "recovered_at": now,
                }
                conn.execute("SAVEPOINT recover_skill_evaluation")
                version_cursor = conn.execute(
                    "UPDATE skill_versions SET evaluation_status = 'error', "
                    "evaluation_run_id = ?, evaluation_report = ? "
                    "WHERE version_id = ? AND evaluation_run_id = ? "
                    "AND evaluation_status IN ('queued', 'running')",
                    (
                        run_id,
                        json.dumps(report, ensure_ascii=False, sort_keys=True),
                        version_id,
                        run_id,
                    ),
                )
                if version_cursor.rowcount != 1:
                    conn.execute("ROLLBACK TO recover_skill_evaluation")
                    conn.execute("RELEASE recover_skill_evaluation")
                    continue
                run_cursor = conn.execute(
                    "UPDATE skill_evaluation_runs SET status = 'error', "
                    "report = ?, error = ?, updated_at = ? "
                    "WHERE run_id = ? AND status IN ('queued', 'running')",
                    (
                        json.dumps(report, ensure_ascii=False, sort_keys=True),
                        "skill-up evaluation interrupted; retry is allowed",
                        now,
                        run_id,
                    ),
                )
                if run_cursor.rowcount == 1 and version_cursor.rowcount == 1:
                    conn.execute("RELEASE recover_skill_evaluation")
                    recovered += 1
                else:
                    conn.execute("ROLLBACK TO recover_skill_evaluation")
                    conn.execute("RELEASE recover_skill_evaluation")
            conn.commit()
        return recovered

    # -- Generic Plugin package control plane ---------------------------

    @staticmethod
    def _plugin_row(row: Any) -> Optional[dict]:
        if not row:
            return None
        value = dict(row)
        for key in ("manifest", "files"):
            raw = value.get(key)
            if isinstance(raw, str):
                try:
                    value[key] = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    value[key] = {}
        value["signature_verified"] = bool(value.get("signature_verified"))
        return value

    def create_plugin_package(
        self, package_id: str, tenant_id: str, plugin_id: str, version: str,
        manifest: dict, files: dict[str, dict[str, Any]], package_digest: str,
        signature_verified: bool, created_by: str, status: str = "validated",
    ) -> dict:
        """Persist one immutable, tenant-owned Plugin package snapshot."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO plugin_packages
                   (package_id, tenant_id, plugin_id, version, manifest, files,
                    package_digest, signature_verified, status, created_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(package_id), str(tenant_id), str(plugin_id), str(version),
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    json.dumps(files, ensure_ascii=False, sort_keys=True),
                    str(package_digest), int(bool(signature_verified)), str(status),
                    str(created_by), now, now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(package_id),),
            ).fetchone()
            return self._plugin_row(row) or {}

    def get_plugin_package(
        self, tenant_id: str, plugin_id: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            if version:
                row = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "AND plugin_id = ? AND version = ?",
                    (str(tenant_id), str(plugin_id), str(version)),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT p.* FROM plugin_packages p
                       JOIN plugin_releases r ON r.package_id = p.package_id
                       WHERE r.tenant_id = ? AND r.plugin_id = ?""",
                    (str(tenant_id), str(plugin_id)),
                ).fetchone()
            return self._plugin_row(row)

    def list_plugin_packages(
        self, tenant_id: str, plugin_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            conn = self._get_conn()
            if plugin_id:
                rows = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "AND plugin_id = ? ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), str(plugin_id), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), limit),
                ).fetchall()
            return [self._plugin_row(row) for row in rows]

    def activate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                "AND plugin_id = ? AND version = ?",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row or str(row["status"]) == "uninstalled":
                return None
            conn.execute(
                "UPDATE plugin_packages SET status = 'inactive', updated_at = ? "
                "WHERE tenant_id = ? AND plugin_id = ? AND status = 'active'",
                (now, str(tenant_id), str(plugin_id)),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'active', activated_at = ?, "
                "updated_at = ?, last_error = NULL WHERE package_id = ?",
                (now, now, str(row["package_id"])),
            )
            conn.execute(
                """INSERT INTO plugin_releases
                   (tenant_id, plugin_id, package_id, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tenant_id, plugin_id) DO UPDATE SET
                   package_id = excluded.package_id, updated_at = excluded.updated_at""",
                (str(tenant_id), str(plugin_id), str(row["package_id"]), now),
            )
            conn.commit()
            active = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(active)

    def deactivate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT p.* FROM plugin_packages p
                   JOIN plugin_releases r ON r.package_id = p.package_id
                   WHERE r.tenant_id = ? AND r.plugin_id = ?
                     AND p.version = ?""",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM plugin_releases WHERE tenant_id = ? AND plugin_id = ?",
                (str(tenant_id), str(plugin_id)),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'inactive', updated_at = ? "
                "WHERE package_id = ?",
                (now, str(row["package_id"])),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(updated)

    def uninstall_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        """Remove a package from the active release without deleting audit data."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                "AND plugin_id = ? AND version = ?",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row or str(row["status"]) == "uninstalled":
                return None
            conn.execute(
                "DELETE FROM plugin_releases WHERE tenant_id = ? AND plugin_id = ? "
                "AND package_id = ?",
                (str(tenant_id), str(plugin_id), str(row["package_id"])),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'uninstalled', updated_at = ? "
                "WHERE package_id = ?",
                (now, str(row["package_id"])),
            )
            conn.commit()
            removed = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(removed)
    
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
            # Only an actively running workflow owns an execution lease.
            # Awaiting confirmation and recovery-required are waiting states;
            # a recovery worker must acquire a fresh lease through the atomic
            # claim method instead of inheriting the old Runtime lease.
            lease_sql = ", lease_owner = NULL, lease_expires_at = NULL" if status != "running" else ""
            if metadata is None:
                cursor = conn.execute(
                    f"UPDATE workflows SET status = ?, updated_at = ?{lease_sql} WHERE workflow_id = ?",
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
                    f"""UPDATE workflows SET status = ?, metadata = ?, updated_at = ?{lease_sql}
                       WHERE workflow_id = ?""",
                    (status, json.dumps(merged_metadata), datetime.now().isoformat(), workflow_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def heartbeat_workflow(
        self, workflow_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Refresh an active workflow lease without changing its state."""
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows
                   SET updated_at = ?, lease_owner = ?, lease_expires_at = ?
                   WHERE workflow_id = ? AND status = 'running'
                     AND (lease_owner IS NULL OR lease_owner = ?)""",
                (now_iso, str(lease_owner), expires_iso, workflow_id, str(lease_owner)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def recover_stale_workflow(
        self, workflow_id: str, stale_after_seconds: float = 300.0,
        metadata: dict = None,
    ) -> bool:
        """Atomically move an expired running workflow into recovery."""
        if float(stale_after_seconds) <= 0:
            return False
        now = datetime.now()
        cutoff_iso = (now - timedelta(seconds=float(stale_after_seconds))).isoformat()
        now_iso = now.isoformat()
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("recovery_reason", "stale_running_workflow")
        merged_metadata.setdefault("recovery_detected_at", now_iso)
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT metadata FROM workflows WHERE workflow_id = ? AND status = 'running' "
                "AND updated_at <= ?",
                (workflow_id, cutoff_iso),
            ).fetchone()
            if not current:
                return False
            try:
                existing = json.loads(current[0] or "{}") or {}
            except (TypeError, ValueError):
                existing = {}
            existing.update(merged_metadata)
            cursor = conn.execute(
                """UPDATE workflows SET status = 'recovery_required', metadata = ?,
                   updated_at = ?, lease_owner = NULL, lease_expires_at = NULL
                   WHERE workflow_id = ? AND status = 'running' AND updated_at <= ?""",
                (json.dumps(existing), now_iso, workflow_id, cutoff_iso),
            )
            conn.commit()
            return cursor.rowcount > 0

    def claim_workflow_recovery(
        self, workflow_id: str, lease_owner: str,
        stale_after_seconds: float = 300.0, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically claim a stale/runnable workflow for one recovery worker."""
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        cutoff_iso = (now - timedelta(seconds=float(stale_after_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows SET status = 'recovery_required',
                   updated_at = ?, lease_owner = ?, lease_expires_at = ?
                   WHERE workflow_id = ?
                     AND ((status = 'running' AND updated_at <= ?)
                       OR status IN ('failed', 'partially_failed', 'blocked', 'recovery_required'))
                     AND (lease_owner IS NULL OR lease_owner = ?
                       OR lease_expires_at IS NULL OR lease_expires_at <= ?)""",
                (
                    now_iso, str(lease_owner), expires_iso, workflow_id,
                    cutoff_iso, str(lease_owner), now_iso,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def release_workflow_lease(self, workflow_id: str, lease_owner: str) -> bool:
        """Release only the lease owned by the calling recovery worker."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE workflow_id = ? AND lease_owner = ?""",
                (workflow_id, str(lease_owner)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: dict = None, error: str = None,
        compensation_required: bool = False,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO workflow_items
                   (item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                   input_data, output_data, error, compensation_required,
                   resource_type, parent_resource_type, parent_sequence, parent_resource_id,
                   provider_resource_id, logical_resource_id,
                   created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                    json.dumps(input_data or {}),
                    json.dumps(output_data) if output_data is not None else None,
                    error, int(compensation_required), resource_type, parent_resource_type,
                    parent_sequence, parent_resource_id, provider_resource_id,
                    logical_resource_id, now, now,
                ),
            )
            conn.commit()

    def upsert_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: dict = None, error: str = None,
        compensation_required: bool = False,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> None:
        """Create or advance an item checkpoint without duplicating rows.

        Workflow items are registered before execution and advanced after the
        handler returns.  ``INSERT OR REPLACE`` would reset creation metadata
        and could overwrite a newer state, so the update path validates the
        state transition and only changes the mutable checkpoint fields.
        """
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflow_items WHERE workflow_id = ? AND sequence = ?",
                (workflow_id, int(sequence)),
            ).fetchone()
            if not current:
                now = datetime.now().isoformat()
                conn.execute(
                    """INSERT INTO workflow_items
                       (item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                       input_data, output_data, error, compensation_required,
                       resource_type, parent_resource_type, parent_sequence, parent_resource_id,
                       provider_resource_id, logical_resource_id,
                       created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id, workflow_id, int(sequence), platform, account_id,
                        tool_name, status, json.dumps(input_data or {}),
                        json.dumps(output_data) if output_data is not None else None,
                        error, int(compensation_required), resource_type, parent_resource_type,
                        parent_sequence, parent_resource_id, provider_resource_id,
                        logical_resource_id, now, now,
                    ),
                )
            else:
                current_status = str(current[0])
                if status not in WORKFLOW_ITEM_TRANSITIONS.get(current_status, set()):
                    raise ValueError(
                        f"cannot advance workflow item {sequence} from "
                        f"{current_status} to {status}"
                    )
                assignments = [
                    "status = ?", "input_data = ?", "output_data = ?",
                    "error = ?", "compensation_required = ?",
                    "account_id = ?", "resource_type = ?",
                    "parent_resource_type = ?", "parent_sequence = ?",
                    "parent_resource_id = ?", "provider_resource_id = ?",
                    "logical_resource_id = ?", "updated_at = ?",
                ]
                conn.execute(
                    f"UPDATE workflow_items SET {', '.join(assignments)} "
                    "WHERE workflow_id = ? AND sequence = ?",
                    (
                        status, json.dumps(input_data or {}),
                        json.dumps(output_data) if output_data is not None else None,
                        error, int(compensation_required), account_id, resource_type,
                        parent_resource_type,
                        parent_sequence, parent_resource_id, provider_resource_id,
                        logical_resource_id, datetime.now().isoformat(),
                        workflow_id, int(sequence),
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
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
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
        for column, value in (
            ("account_id", account_id),
            ("resource_type", resource_type),
            ("parent_resource_type", parent_resource_type),
            ("parent_sequence", parent_sequence),
            ("parent_resource_id", parent_resource_id),
            ("provider_resource_id", provider_resource_id),
            ("logical_resource_id", logical_resource_id),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
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
        self, user_id: Optional[str] = None, limit: int = 50,
        include_stale_running: bool = False, stale_after_seconds: float = 300.0,
    ) -> list[dict]:
        """List non-terminal workflows for an operator/recovery worker."""
        statuses = ["failed", "partially_failed", "recovery_required", "blocked"]
        if include_stale_running:
            statuses.append("running")
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
                if item.get("status") == "running" and include_stale_running:
                    try:
                        age = time.time() - datetime.fromisoformat(
                            str(item.get("updated_at"))
                        ).timestamp()
                    except (TypeError, ValueError, OverflowError):
                        age = 0
                    if age < float(stale_after_seconds):
                        continue
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
