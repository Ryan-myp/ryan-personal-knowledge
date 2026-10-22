"""Domain-owned extension store operations behind the persistence facade."""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from .errors import PersistenceConflictError


class ExtensionRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn = connection_provider
        self._lock = lock

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

    @staticmethod
    def _mcp_decode(row: Any) -> Optional[dict]:
        if not row:
            return None
        value = dict(row)
        for key in (
            "validation_report", "input_schema", "annotations", "intent_types",
            "intent_aliases", "skill_refs", "required_permissions", "traits",
        ):
            if isinstance(value.get(key), str):
                try:
                    value[key] = json.loads(value[key] or "{}")
                except (TypeError, ValueError):
                    value[key] = {} if key in {"validation_report", "input_schema", "annotations"} else []
        for key in ("enabled",):
            value[key] = bool(value.get(key))
        return value

    def create_mcp_server(self, data: dict[str, Any]) -> dict:
        """Persist a tenant-scoped external MCP Server declaration."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO mcp_servers
                       (server_id, tenant_id, name, description, endpoint, transport,
                        auth_type, credential_ref, auth_header, timeout_seconds, status,
                        enabled, validation_status, validation_report, created_by,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, 'not_run', '{}', ?, ?, ?)""",
                    (
                        str(data["server_id"]), str(data["tenant_id"]), str(data["name"]),
                        str(data.get("description") or ""), str(data["endpoint"]),
                        str(data.get("transport") or "streamable_http"),
                        str(data.get("auth_type") or "none"), data.get("credential_ref"),
                        str(data.get("auth_header") or "Authorization"),
                        float(data.get("timeout_seconds") or 500.0), str(data["created_by"]),
                        now, now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "MCP server violates a persistence uniqueness constraint"
                ) from exc
            conn.commit()
            return self._mcp_decode(conn.execute(
                "SELECT * FROM mcp_servers WHERE server_id = ?",
                (str(data["server_id"]),),
            ).fetchone()) or {}

    def get_mcp_server(self, tenant_id: str, server_id: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM mcp_servers WHERE tenant_id = ? AND server_id = ?",
                (str(tenant_id), str(server_id)),
            ).fetchone()
            return self._mcp_decode(row)

    def list_mcp_servers(self, tenant_id: str, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM mcp_servers WHERE tenant_id = ? "
                "ORDER BY updated_at DESC LIMIT ?", (str(tenant_id), limit),
            ).fetchall()
            return [self._mcp_decode(row) for row in rows]

    def update_mcp_server(self, server_id: str, tenant_id: str, data: dict[str, Any]) -> Optional[dict]:
        allowed = {
            "name", "description", "endpoint", "transport", "auth_type", "credential_ref",
            "auth_header", "timeout_seconds", "status", "enabled", "validation_status",
            "validation_report", "protocol_version", "last_checked_at", "last_error",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        if not updates:
            return self.get_mcp_server(tenant_id, server_id)
        if "validation_report" in updates:
            updates["validation_report"] = json.dumps(
                updates["validation_report"] or {}, ensure_ascii=False, sort_keys=True
            )
        if "enabled" in updates:
            updates["enabled"] = int(bool(updates["enabled"]))
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [str(tenant_id), str(server_id)]
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    f"UPDATE mcp_servers SET {assignments} WHERE tenant_id = ? AND server_id = ?",
                    values,
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "MCP server violates a persistence uniqueness constraint"
                ) from exc
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return self._mcp_decode(conn.execute(
                "SELECT * FROM mcp_servers WHERE tenant_id = ? AND server_id = ?",
                (str(tenant_id), str(server_id)),
            ).fetchone())

    def _mcp_tool_decode(self, row: Any) -> Optional[dict]:
        return self._mcp_decode(row)

    def upsert_mcp_tool(self, data: dict[str, Any]) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            existing = conn.execute(
                "SELECT tool_id FROM mcp_tools WHERE server_id = ? AND remote_name = ?",
                (str(data["server_id"]), str(data["remote_name"])),
            ).fetchone()
            encoded_schema = json.dumps(data.get("input_schema") or {}, ensure_ascii=False, sort_keys=True)
            encoded_annotations = json.dumps(data.get("annotations") or {}, ensure_ascii=False, sort_keys=True)
            if existing:
                conn.execute(
                    """UPDATE mcp_tools SET tool_id = ?, tenant_id = ?, title = ?,
                       description = ?, input_schema = ?, annotations = ?,
                       validation_status = ?, updated_at = ?
                       WHERE server_id = ? AND remote_name = ?""",
                    (
                        str(data["tool_id"]), str(data["tenant_id"]), str(data.get("title") or ""),
                        str(data.get("description") or ""), encoded_schema, encoded_annotations,
                        str(data.get("validation_status") or "pending"), now,
                        str(data["server_id"]), str(data["remote_name"]),
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO mcp_tools
                    (tool_id, server_id, tenant_id, remote_name, title, description,
                        input_schema, annotations, intent_types, intent_aliases,
                        skill_refs, action, resource_type, resource_id_field,
                        readback_tool, idempotency_key_field, required_permissions,
                        traits, status, enabled, validation_status,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                               'discovered', 0, ?, ?, ?)""",
                    (
                        str(data["tool_id"]), str(data["server_id"]), str(data["tenant_id"]),
                        str(data["remote_name"]), str(data.get("title") or ""),
                        str(data.get("description") or ""), encoded_schema, encoded_annotations,
                        json.dumps(data.get("intent_types") or [], ensure_ascii=False),
                        json.dumps(data.get("intent_aliases") or [], ensure_ascii=False),
                        json.dumps(data.get("skill_refs") or [], ensure_ascii=False),
                        str(data.get("action") or "invoke"),
                        str(data.get("resource_type") or "mcp_invocation"),
                        data.get("resource_id_field"), data.get("readback_tool"),
                        data.get("idempotency_key_field"),
                        json.dumps(data.get("required_permissions") or [], ensure_ascii=False),
                        json.dumps(data.get("traits") or ["external", "mcp"], ensure_ascii=False),
                        str(data.get("validation_status") or "pending"), now, now,
                    ),
                )
            conn.commit()
            return self._mcp_tool_decode(conn.execute(
                "SELECT * FROM mcp_tools WHERE server_id = ? AND remote_name = ?",
                (str(data["server_id"]), str(data["remote_name"])),
            ).fetchone()) or {}

    def list_mcp_tools(self, server_id: str, tenant_id: Optional[str] = None) -> list[dict]:
        with self._lock:
            if tenant_id is None:
                rows = self._get_conn().execute(
                    "SELECT * FROM mcp_tools WHERE server_id = ? ORDER BY remote_name",
                    (str(server_id),),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    "SELECT * FROM mcp_tools WHERE server_id = ? AND tenant_id = ? ORDER BY remote_name",
                    (str(server_id), str(tenant_id)),
                ).fetchall()
            return [self._mcp_tool_decode(row) for row in rows]

    def get_mcp_tool(self, tool_id: str, tenant_id: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM mcp_tools WHERE tool_id = ? AND tenant_id = ?",
                (str(tool_id), str(tenant_id)),
            ).fetchone()
            return self._mcp_tool_decode(row)

    def update_mcp_tool(self, tool_id: str, tenant_id: str, data: dict[str, Any]) -> Optional[dict]:
        allowed = {
            "status", "enabled", "validation_status", "last_error",
            "intent_types", "intent_aliases", "skill_refs", "action",
            "resource_type", "resource_id_field", "readback_tool",
            "idempotency_key_field", "required_permissions", "traits",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        if not updates:
            return self.get_mcp_tool(tool_id, tenant_id)
        if "enabled" in updates:
            updates["enabled"] = int(bool(updates["enabled"]))
        for key in (
            "intent_types", "intent_aliases", "skill_refs",
            "required_permissions", "traits",
        ):
            if key in updates:
                updates[key] = json.dumps(
                    updates[key] or [], ensure_ascii=False, sort_keys=True
                )
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [str(tenant_id), str(tool_id)]
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                f"UPDATE mcp_tools SET {assignments} WHERE tenant_id = ? AND tool_id = ?",
                values,
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return self._mcp_tool_decode(conn.execute(
                "SELECT * FROM mcp_tools WHERE tenant_id = ? AND tool_id = ?",
                (str(tenant_id), str(tool_id)),
            ).fetchone())
