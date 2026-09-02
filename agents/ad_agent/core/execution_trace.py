"""Provider-neutral, safe execution events for Agent turn observers.

The trace is an operational view of a turn, not a model-thought stream.  It
contains only plan/tool metadata plus explicitly bounded, sanitized input and
output summaries so it can be sent to an interactive client without exposing
model thoughts, credentials or raw provider exceptions.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional


ExecutionEventCallback = Callable[[dict[str, Any]], None]

TRACE_STATUSES = frozenset(
    {
        "planned",
        "running",
        "succeeded",
        "failed",
        "awaiting_confirmation",
        "skipped",
        "unknown",
        "recovery_required",
    }
)

_SECRET_KEY = re.compile(
    r"(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|app[_-]?secret|"
    r"private[_-]?key|developer[_-]?token|bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc)",
    re.IGNORECASE,
)

# Execution plans contain a bounded list of node objects (and dependency
# lists).  A depth of three is enough for most metadata, but it truncates a
# perfectly safe plan at ``execution_plan -> nodes -> node``.  Keep the
# observer bounded without hiding the trace's own contract fields.
_MAX_METADATA_DEPTH = 6


def _safe_metadata(value: Any, *, depth: int = 0) -> Any:
    """Keep event metadata small and remove credential-shaped values."""

    if depth > _MAX_METADATA_DEPTH:
        return "[truncated]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _SECRET_KEY.search(key):
                continue
            result[key[:80]] = _safe_metadata(raw_value, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_metadata(item, depth=depth + 1) for item in list(value)[:12]]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if _SECRET_KEY.search(text):
        return "[redacted]"
    return text[:240]


class ExecutionTrace:
    """Emit a bounded, ordered trace for one Runtime turn.

    The callback is best-effort: tracing must never change business execution.
    A plan is the source of node identity. Features that discover a dependent
    Tool after the initial plan must explicitly register it before execution;
    consumers still never invent nodes from result rows.
    """

    def __init__(
        self,
        callback: Optional[ExecutionEventCallback] = None,
        *,
        trace_id: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> None:
        self.callback = callback
        self.trace_id = trace_id or str(uuid.uuid4())
        self.turn_id = turn_id or ""
        self._sequence = 0
        self._started_at: dict[str, float] = {}
        self._stage_started_at: dict[str, float] = {}
        self._node_occurrences: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._node_cursor: dict[tuple[str, str], int] = {}
        self._events: list[dict[str, Any]] = []
        self.plan: dict[str, Any] = {"schema_version": "1.0", "intent_type": "", "nodes": []}

    @property
    def enabled(self) -> bool:
        return callable(self.callback)

    def _emit(self, event_type: str, **payload: Any) -> None:
        self._sequence += 1
        event = {
            "type": event_type,
            "event_type": event_type,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "seq": self._sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for key, value in payload.items():
            if key == "safe_metadata":
                event[key] = _safe_metadata(value)
            elif key == "execution_plan":
                event[key] = _safe_metadata(value)
            else:
                event[key] = _safe_metadata(value)
        self._events.append(event)
        if len(self._events) > 256:
            self._events.pop(0)
        if not self.enabled:
            return
        try:
            self.callback(event)  # type: ignore[misc]
        except Exception:
            # Observers (including a disconnected SSE client) are never part
            # of the Runtime's execution correctness boundary.
            return

    @property
    def events(self) -> list[dict[str, Any]]:
        """Return the bounded, already-sanitized event history for persistence."""
        return [dict(event) for event in self._events]

    def snapshot(self) -> dict[str, Any]:
        """Return a durable, provider-neutral snapshot of this turn's trace."""
        status = "unknown"
        for event in reversed(self._events):
            if event.get("type") == "done":
                status = str(event.get("status") or status)
                break
        return {
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "status": status,
            "events": self.events,
        }

    def start(self) -> None:
        self._emit("start", status="running", safe_metadata={"input_received": True})

    def stage_status(
        self,
        stage_id: str,
        title: str,
        status: str,
        *,
        subtitle: str = "",
        platform: str = "",
        safe_metadata: Optional[Mapping[str, Any]] = None,
        safe_input: Any = None,
        safe_output: Any = None,
    ) -> None:
        """Emit a real Runtime lifecycle stage for the execution view.

        Stages are observational nodes, not executable plan nodes.  Runtime
        calls this at actual lifecycle boundaries (for example, around intent
        parsing or result analysis), so the client can render the path taken
        by this turn without pretending every request follows one workflow.
        """

        stage_key = str(stage_id or "").strip()
        if not stage_key:
            return
        if status not in TRACE_STATUSES:
            status = "unknown"
        if status == "running":
            self._stage_started_at[stage_key] = time.monotonic()
        metadata = dict(safe_metadata or {})
        started_at = self._stage_started_at.get(stage_key)
        if started_at is not None and status != "running":
            metadata.setdefault(
                "duration_ms", round((time.monotonic() - started_at) * 1000, 2)
            )
        node_id = f"stage:{stage_key}"
        self._emit(
            "stage_started" if status == "running" else "stage_status",
            node_id=node_id,
            stage_id=stage_key,
            kind="stage",
            title=str(title or stage_key),
            subtitle=str(subtitle or ""),
            platform=str(platform or ""),
            status=status,
            safe_metadata=metadata,
            safe_input=safe_input,
            safe_output=safe_output,
        )

    def bind_plan(self, execution_plan: Any) -> None:
        self.plan = execution_plan.to_dict()
        self._node_occurrences.clear()
        self._node_cursor.clear()
        for node in self.plan.get("nodes", []):
            key = (str(node.get("platform") or ""), str(node.get("tool") or ""))
            self._node_occurrences.setdefault(key, []).append(node)
        self._emit("plan", status="planned", execution_plan=self.plan)

    def register_dynamic_node(
        self,
        platform: str,
        tool_name: str,
        *,
        action: str = "",
        resource_type: str = "",
        parent_resource_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register a Tool materialized by a running Feature.

        Some read workflows discover a dependent report Tool only after a
        listing result is available.  This is an explicit observation of the
        Tool selected by the Feature, not a node inferred from a result row.
        """

        key = (str(platform or ""), str(tool_name or ""))
        existing_nodes = self._node_occurrences.get(key, [])
        if existing_nodes:
            return existing_nodes[-1]
        sequence = max(
            [int(node.get("sequence") or 0) for node in self.plan.get("nodes", [])]
            or [0]
        ) + 1
        previous_nodes = [
            item for item in self.plan.get("nodes", [])
            if str(item.get("platform") or "") == str(platform or "")
        ]
        node = {
            "node_id": f"node-{sequence:04d}",
            "sequence": sequence,
            "platform": str(platform or ""),
            "tool": str(tool_name or ""),
            "action": str(action or ""),
            "resource_type": str(resource_type or ""),
            "parent_resource_type": parent_resource_type,
            "depends_on": [previous_nodes[-1]["node_id"]] if previous_nodes else [],
        }
        self.plan.setdefault("nodes", []).append(node)
        self._node_occurrences.setdefault(key, []).append(node)
        self._emit(
            "node_discovered",
            node_id=node["node_id"],
            platform=node["platform"],
            tool=node["tool"],
            resource_type=node["resource_type"],
            action=node["action"],
            status="planned",
            safe_metadata={"source": "runtime_feature"},
        )
        return node

    def node_for(self, platform: str, tool_name: str) -> Optional[dict[str, Any]]:
        key = (str(platform or ""), str(tool_name or ""))
        nodes = self._node_occurrences.get(key, [])
        cursor = self._node_cursor.get(key, 0)
        if cursor >= len(nodes):
            return None
        self._node_cursor[key] = cursor + 1
        return nodes[cursor]

    def node_status(
        self,
        node: Optional[Mapping[str, Any]],
        status: str,
        *,
        safe_metadata: Optional[Mapping[str, Any]] = None,
        safe_input: Any = None,
        safe_output: Any = None,
    ) -> None:
        if status not in TRACE_STATUSES:
            status = "unknown"
        node_id = str((node or {}).get("node_id") or "")
        if status == "running" and node_id:
            self._started_at[node_id] = time.monotonic()
        duration_ms = None
        if node_id and status != "running" and node_id in self._started_at:
            duration_ms = round((time.monotonic() - self._started_at[node_id]) * 1000, 2)
        metadata = dict(safe_metadata or {})
        if duration_ms is not None:
            metadata["duration_ms"] = duration_ms
        self._emit(
            "node_started" if status == "running" else "node_status",
            node_id=node_id,
            parent_node_id=(node or {}).get("parent_node_id") or next(
                iter((node or {}).get("depends_on") or ()), None
            ),
            platform=(node or {}).get("platform"),
            tool=(node or {}).get("tool"),
            resource_type=(node or {}).get("resource_type"),
            action=(node or {}).get("action"),
            status=status,
            safe_metadata=metadata,
            safe_input=safe_input,
            safe_output=safe_output,
        )

    def all_nodes_status(self, status: str, *, reason: str) -> None:
        for node in self.plan.get("nodes", []):
            self.node_status(node, status, safe_metadata={"reason": reason})

    def confirmation(self, node: Optional[Mapping[str, Any]], *, reason: str) -> None:
        self.node_status(node, "awaiting_confirmation", safe_metadata={"reason": reason})
        self._emit(
            "confirmation",
            node_id=(node or {}).get("node_id"),
            status="awaiting_confirmation",
            safe_metadata={"reason": reason},
        )

    def reply(self, *, needs_confirmation: bool = False) -> None:
        self._emit(
            "reply",
            status="awaiting_confirmation" if needs_confirmation else "succeeded",
            safe_metadata={"available": True},
        )

    def error(self, *, reason: str = "runtime_error") -> None:
        self._emit("error", status="failed", safe_metadata={"reason": reason})

    def done(self, status: str = "succeeded", *, safe_metadata: Optional[Mapping[str, Any]] = None) -> None:
        if status not in TRACE_STATUSES:
            status = "unknown"
        self._emit("done", status=status, safe_metadata=safe_metadata or {})
