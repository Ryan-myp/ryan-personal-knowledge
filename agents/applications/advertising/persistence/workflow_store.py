"""Domain-owned workflow store operations behind the persistence facade."""

from __future__ import annotations
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, List
from .models import CampaignRecord
import logging
logger = logging.getLogger(__name__)
from .transitions import WORKFLOW_ITEM_TRANSITIONS, WORKFLOW_TRANSITIONS


class WorkflowRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn = connection_provider
        self._lock = lock

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

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned", metadata: dict = None,
        emit_outbox: bool = True,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            session_row = conn.execute(
                "SELECT tenant_id, metadata FROM sessions WHERE session_id = ?",
                (str(session_id),),
            ).fetchone()
            tenant_id = str(session_row["tenant_id"] or "default") if session_row else "default"
            conn.execute(
                """INSERT INTO workflows
                   (workflow_id, session_id, tenant_id, intent_type, execution_mode, status,
                    metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (workflow_id, session_id, tenant_id, intent_type, execution_mode, status,
                json.dumps(metadata or {}), now, now),
            )
            if emit_outbox:
                conn.execute(
                    """INSERT OR IGNORE INTO outbox_events
                       (event_id, run_id, event_type, payload, created_at)
                       VALUES (?, ?, 'workflow.created', ?, ?)""",
                    (
                        str(uuid.uuid4()), str(workflow_id),
                        json.dumps({
                            "workflow_id": str(workflow_id),
                            "status": str(status),
                            "metadata": metadata or {},
                        }, ensure_ascii=False, sort_keys=True, default=str),
                        now,
                    ),
                )
            conn.commit()

    def update_workflow(
        self, workflow_id: str, status: str, metadata: dict = None,
        emit_outbox: bool = True,
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
            merged_metadata = {}
            if metadata is None:
                existing = conn.execute(
                    "SELECT metadata FROM workflows WHERE workflow_id = ?",
                    (workflow_id,),
                ).fetchone()
                if existing and existing[0]:
                    try:
                        merged_metadata = json.loads(existing[0]) or {}
                    except (TypeError, ValueError):
                        merged_metadata = {}
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
            if cursor.rowcount > 0 and emit_outbox:
                conn.execute(
                    """INSERT INTO outbox_events
                       (event_id, run_id, event_type, payload, created_at)
                       VALUES (?, ?, 'workflow.updated', ?, ?)""",
                    (
                        str(uuid.uuid4()), str(workflow_id),
                        json.dumps({
                            "workflow_id": str(workflow_id),
                            "from_status": current_status,
                            "status": str(status),
                            "metadata": merged_metadata,
                        }, ensure_ascii=False, sort_keys=True, default=str),
                        datetime.now().isoformat(),
                    ),
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

    def get_workflow(
        self, workflow_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            query = (
                "SELECT w.* FROM workflows w JOIN sessions s "
                "ON s.session_id = w.session_id WHERE w.workflow_id = ?"
            )
            params: list[Any] = [workflow_id]
            if user_id is not None:
                query += " AND s.user_id = ?"
                params.append(str(user_id))
            if tenant_id is not None:
                query += " AND w.tenant_id = ?"
                params.append(str(tenant_id))
            row = conn.execute(query, params).fetchone()
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
        tenant_id: Optional[str] = None,
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
        if tenant_id is not None:
            query += " AND w.tenant_id = ?"
            params.append(str(tenant_id))
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
