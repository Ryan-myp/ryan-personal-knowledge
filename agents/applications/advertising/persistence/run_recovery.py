"""Bounded recovery projections and lease-fenced local maintenance."""

from datetime import datetime, timedelta, timezone
import json
import math

from agents.agent_harness.redaction import redact_for_persistence


class RunRecoveryRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn, self._lock = connection_provider, lock

    def recover_stale(self, stale_after_seconds=300):
        seconds = float(stale_after_seconds)
        if not math.isfinite(seconds) or seconds <= 0:
            return 0
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=seconds)).isoformat()
        timestamp = now.isoformat()
        with self._lock:
            conn = self._get_conn()
            with conn:
                rows = conn.execute(
                    """SELECT r.run_id, r.metadata FROM execution_runs r
                       WHERE r.status = 'running' AND r.updated_at <= ?
                       AND NOT EXISTS (SELECT 1 FROM sessions s WHERE s.session_id = r.session_id
                           AND s.lease_owner IS NOT NULL AND s.lease_expires_at > ?)
                       AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.task_id = r.task_id
                           AND t.lease_owner IS NOT NULL AND t.lease_expires_at > ?)
                       ORDER BY r.updated_at, r.run_id LIMIT 100""",
                    (cutoff, timestamp, timestamp),
                ).fetchall()
                for row in rows:
                    self._mark_unknown(conn, row, timestamp)
                self._release_expired_sessions(conn, timestamp)
            return len(rows)

    @staticmethod
    def _mark_unknown(conn, row, now):
        # Malformed durable metadata is a storage error, not proof of success.
        metadata = json.loads(row["metadata"] or "{}")
        if not isinstance(metadata, dict):
            raise ValueError("invalid execution run metadata")
        metadata = redact_for_persistence({**metadata,
            "recovery_reason": "stale_execution_run", "effect_state": "unknown",
            "recovery_detected_at": now, "automatic_replay_allowed": False,
        })
        conn.execute(
            """UPDATE execution_runs SET status = 'recovery_required', metadata = ?,
               updated_at = ?, finished_at = COALESCE(finished_at, ?)
               WHERE run_id = ? AND status = 'running'""",
            (json.dumps(metadata, ensure_ascii=False), now, now, row["run_id"]),
        )
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM execution_run_events WHERE run_id = ?",
            (row["run_id"],),
        ).fetchone()[0]
        event = {"type": "recovery_required", "event_type": "recovery_required", "seq": seq,
                 "status": "recovery_required", "timestamp": now, "safe_metadata": metadata}
        conn.execute(
            """INSERT INTO execution_run_events (run_id, seq, event_type, payload, created_at)
               VALUES (?, ?, 'recovery_required', ?, ?)""",
            (row["run_id"], seq, json.dumps(event, ensure_ascii=False), now),
        )

    @staticmethod
    def _release_expired_sessions(conn, now):
        rows = conn.execute(
            """SELECT session_id FROM sessions s WHERE lease_owner IS NOT NULL
               AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
               AND NOT EXISTS (SELECT 1 FROM execution_runs r
                   WHERE r.session_id = s.session_id AND r.status = 'running')
               ORDER BY lease_expires_at LIMIT 100""", (now,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE sessions SET lease_owner = NULL, lease_expires_at = NULL "
                "WHERE session_id = ?",
                (row["session_id"],),
            )

    def inbox(self, *, tenant_id=None, user_id=None, limit=30):
        limit = min(100, max(1, int(limit)))
        values = [tenant_id, tenant_id, user_id, user_id] * 2
        query = """SELECT run_id AS id, 'run' AS kind, updated_at, metadata FROM execution_runs
                   WHERE status = 'recovery_required'
                   AND (? IS NULL OR tenant_id = ?) AND (? IS NULL OR user_id = ?)
                   UNION ALL
                   SELECT task_id AS id, 'task' AS kind, updated_at, metadata FROM tasks
                   WHERE status = 'recovery_required'
                   AND (? IS NULL OR tenant_id = ?) AND (? IS NULL OR user_id = ?)
                   ORDER BY updated_at, kind, id LIMIT ?"""
        count_query = """SELECT
            (SELECT COUNT(*) FROM execution_runs WHERE status = 'recovery_required'
             AND (? IS NULL OR tenant_id = ?) AND (? IS NULL OR user_id = ?)) +
            (SELECT COUNT(*) FROM tasks WHERE status = 'recovery_required'
             AND (? IS NULL OR tenant_id = ?) AND (? IS NULL OR user_id = ?))"""
        with self._lock:
            conn = self._get_conn()
            total = conn.execute(count_query, values).fetchone()[0]
            rows = conn.execute(query, [*values, limit]).fetchall()
        items = [self._project(row) for row in rows]
        return {"items": items, "total": total, "has_more": total > limit,
                "scope": "runs_and_tasks"}

    @staticmethod
    def _project(row):
        try:
            metadata = json.loads(row["metadata"] or "{}")
        except (TypeError, ValueError):
            metadata = {"recovery_reason": "unreadable_evidence"}
        metadata = metadata if isinstance(metadata, dict) else {}
        reasons = {
            "stale_execution_run": "执行中断且租约已失效，需核验已有操作结果。",
            "unreadable_evidence": "执行记录格式异常，需人工检查原始审计。",
        }
        code = metadata.get("recovery_reason")
        code = code if isinstance(code, str) and code in reasons else "effect_unverified"
        return {
            "id": row["id"], "kind": row["kind"], "updated_at": row["updated_at"],
            "next_action": (
                "inspect_run_evidence" if row["kind"] == "run" else "verify_effect_before_requeue"
            ),
            "automatic_replay_allowed": False, "reason_code": code,
            "reason": reasons.get(code, "执行结果尚未确认，需核验已有操作和回读证据。"),
        }
