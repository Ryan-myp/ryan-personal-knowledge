#!/usr/bin/env python3.13
"""Run process-level evidence for Runtime reliability boundaries.

The runner uses only a local shared persistence file and deterministic handlers.
It proves coordination and recovery semantics without calling a provider.  The
report therefore describes production-shaped reliability evidence, not a claim
that a production cluster has been deployed or live-tested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.persistence.models import TaskRecord  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402
from agents.ad_agent.runtime.task_executor import TaskExecutor  # noqa: E402


FORMAT_VERSION = 1
TERMINAL_TASK_STATUSES = frozenset({
    "succeeded",
    "failed",
    "partially_failed",
    "awaiting_input",
    "recovery_required",
    "cancelled",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any) -> str:
    """Return a stable identifier digest without exposing local IDs."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _task(
    task_id: str,
    *,
    kind: str = "agent.turn",
    status: str = "queued",
    updated_at: str | None = None,
) -> TaskRecord:
    timestamp = updated_at or _now()
    return TaskRecord(
        task_id=task_id,
        tenant_id="evidence-tenant",
        user_id="evidence-user",
        kind=kind,
        status=status,
        payload={"user_input": "controlled reliability probe"},
        metadata={"evidence": True},
        created_at=timestamp,
        updated_at=timestamp,
    )


def _json_line(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True), flush=True)


def _child_claim_task(database: str, task_id: str, worker_id: str) -> int:
    store = AdAgentStore(database)
    try:
        record = store.claim_task(task_id, worker_id, lease_seconds=10.0)
        _json_line({
            "claimed": record is not None,
            "status": record.status if record is not None else None,
        })
        return 0
    finally:
        store.close()


def _child_session_lease(
    database: str, session_id: str, owner: str, hold_seconds: float,
) -> int:
    store = AdAgentStore(database)
    try:
        acquired = store.acquire_session_lease(
            session_id, owner, lease_seconds=max(1.0, hold_seconds + 1.0),
        )
        if acquired:
            time.sleep(max(0.0, hold_seconds))
            store.release_session_lease(session_id, owner)
        _json_line({"acquired": acquired})
        return 0
    finally:
        store.close()


def _child_crash_after_claim(database: str, task_id: str) -> int:
    store = AdAgentStore(database)
    record = store.claim_task(task_id, "crashed-worker", lease_seconds=0.4)
    if record is None:
        store.close()
        return 2
    # Simulate a process crash after claiming but before a terminal update.
    os._exit(0)


def _child_run_worker(
    database: str, task_id: str, worker_label: str, timeout_seconds: float,
) -> int:
    store = AdAgentStore(database)
    executed = False
    executor = TaskExecutor(
        store,
        max_workers=1,
        max_queue=0,
        task_timeout_seconds=max(1.0, timeout_seconds),
        lease_seconds=2.0,
        queue_poll_interval=0.02,
    )

    def runtime_turn(context: Any) -> dict[str, Any]:
        nonlocal executed
        executed = True
        if context.is_cancelled():
            return {"task_status": "cancelled", "route": "agent.turn"}
        return {
            "task_status": "succeeded",
            "route": "agent.turn",
            "provider_direct": False,
            "worker": _safe_id(worker_label),
        }

    executor.register_handler("agent.turn", runtime_turn)
    try:
        executor.start()
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while time.monotonic() < deadline:
            record = store.get_task(task_id)
            if record is not None and record.status in TERMINAL_TASK_STATUSES:
                _json_line({
                    "status": record.status,
                    "route": (
                        record.result.get("route")
                        if isinstance(record.result, dict) else None
                    ),
                    "executed": executed,
                })
                return 0
            time.sleep(0.02)
        record = store.get_task(task_id)
        _json_line({
            "status": record.status if record is not None else None,
            "route": None,
            "executed": executed,
            "timeout": True,
        })
        return 1
    finally:
        executor.shutdown(wait=True)
        store.close()


def _child_command(arguments: list[str]) -> int:
    command = arguments[0] if arguments else ""
    if command == "claim-task" and len(arguments) == 4:
        return _child_claim_task(arguments[1], arguments[2], arguments[3])
    if command == "session-lease" and len(arguments) == 5:
        return _child_session_lease(
            arguments[1], arguments[2], arguments[3], float(arguments[4]),
        )
    if command == "crash-after-claim" and len(arguments) == 3:
        return _child_crash_after_claim(arguments[1], arguments[2])
    if command == "run-worker" and len(arguments) == 5:
        return _child_run_worker(
            arguments[1], arguments[2], arguments[3], float(arguments[4]),
        )
    raise ValueError("unsupported reliability evidence child command")


def _child_process(arguments: list[str]) -> subprocess.Popen[str]:
    environment = dict(os.environ)
    current_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(ROOT) + os.pathsep + current_pythonpath
        if current_pythonpath else str(ROOT)
    )
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        cwd=str(ROOT),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _read_process(
    process: subprocess.Popen[str], timeout_seconds: float,
) -> tuple[int, dict[str, Any] | None, str]:
    try:
        stdout, stderr = process.communicate(timeout=max(1.0, timeout_seconds))
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return -9, None, "child process timed out"
    payload = None
    for line in reversed(stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    error = stderr.strip()[-500:] if stderr.strip() else ""
    if process.returncode != 0 and not error:
        error = f"child exited with code {process.returncode}"
    return int(process.returncode or 0), payload, error


def _read_processes(
    processes: Iterable[subprocess.Popen[str]], timeout_seconds: float,
) -> list[tuple[int, dict[str, Any] | None, str]]:
    return [
        _read_process(process, timeout_seconds)
        for process in processes
    ]


def _session_lease_evidence(database: str, store: AdAgentStore) -> dict[str, Any]:
    session_id = f"evidence-session-{uuid.uuid4().hex}"
    holder = f"holder-{uuid.uuid4().hex}"
    store.create_session(
        session_id,
        "evidence-user",
        metadata={"tenant_id": "evidence-tenant"},
    )
    process = _child_process([
        "session-lease", database, session_id, holder, "0.8",
    ])
    deadline = time.monotonic() + 2.0
    acquired = False
    while time.monotonic() < deadline:
        session = store.get_session(session_id)
        if session and session.get("lease_owner") == holder:
            acquired = True
            break
        time.sleep(0.02)
    contender = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "session-lease", database, session_id, "contender", "0"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    contender_payload = None
    for line in reversed(contender.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(candidate, dict):
            contender_payload = candidate
            break
    holder_code, holder_payload, holder_error = _read_process(process, 5)
    busy_count = int(acquired and not bool(
        (contender_payload or {}).get("acquired")
    ))
    return {
        "scenario": "session_lease_multi_instance",
        "passed": bool(
            acquired
            and busy_count == 1
            and holder_code == 0
            and bool((holder_payload or {}).get("acquired"))
            and contender.returncode == 0
        ),
        "instance_count": 2,
        "lease_owner_digest": _safe_id(holder),
        "busy_count": busy_count,
        "holder_exit_code": holder_code,
        "contender_acquired": bool((contender_payload or {}).get("acquired")),
        "error": holder_error or contender.stderr.strip()[-500:],
    }


def _task_claim_evidence(database: str, store: AdAgentStore) -> dict[str, Any]:
    task_id = f"evidence-claim-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    processes = [
        _child_process(["claim-task", database, task_id, f"worker-{index}"])
        for index in range(2)
    ]
    results = _read_processes(processes, 5)
    winner_count = sum(
        1 for _code, payload, _error in results
        if bool((payload or {}).get("claimed"))
    )
    store.update_task(task_id, "succeeded", expected_statuses=["running"])
    return {
        "scenario": "durable_task_claim_multi_instance",
        "passed": bool(
            winner_count == 1
            and all(code == 0 for code, _payload, _error in results)
        ),
        "instance_count": 2,
        "winner_count": winner_count,
        "task_id_digest": _safe_id(task_id),
        "child_exit_codes": [code for code, _payload, _error in results],
    }


def _worker_route_evidence(database: str, store: AdAgentStore) -> dict[str, Any]:
    task_id = f"evidence-worker-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    processes = [
        _child_process([
            "run-worker", database, task_id, f"worker-{index}", "5",
        ])
        for index in range(2)
    ]
    results = _read_processes(processes, 8)
    record = store.get_task(task_id)
    terminal_status = record.status if record is not None else None
    route = (
        record.result.get("route")
        if record is not None and isinstance(record.result, dict) else None
    )
    direct_provider = (
        record.result.get("provider_direct")
        if record is not None and isinstance(record.result, dict) else None
    )
    return {
        "scenario": "worker_runtime_route",
        "passed": bool(
            terminal_status == "succeeded"
            and route == "agent.turn"
            and direct_provider is False
            and sum(
                1 for _code, payload, _error in results
                if bool((payload or {}).get("executed"))
            ) == 1
        ),
        "instance_count": 2,
        "terminal_status": terminal_status,
        "route": route,
        "provider_direct": direct_provider,
        "successful_worker_count": sum(
            1 for _code, payload, _error in results
            if bool((payload or {}).get("executed"))
        ),
        "task_id_digest": _safe_id(task_id),
    }


def _worker_recovery_evidence(database: str, store: AdAgentStore) -> dict[str, Any]:
    task_id = f"evidence-recovery-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    crashed = _child_process(["crash-after-claim", database, task_id])
    crash_code, _payload, crash_error = _read_process(crashed, 5)
    time.sleep(0.65)
    recovered_count = store.recover_stale_tasks(stale_after_seconds=0.1)
    recovered = store.get_task(task_id)
    recovered_status = recovered.status if recovered is not None else None
    empty_reference_rejected = False
    try:
        store.requeue_recovery_task(task_id, recovery_reference="")
    except ValueError:
        empty_reference_rejected = True
    requeued = store.requeue_recovery_task(
        task_id, recovery_reference="controlled-readback",
    )
    restarted = _child_process([
        "run-worker", database, task_id, "restarted-worker", "5",
    ])
    restart_code, restart_payload, restart_error = _read_process(restarted, 8)
    final = store.get_task(task_id)
    final_status = final.status if final is not None else None
    return {
        "scenario": "worker_crash_recovery",
        "passed": bool(
            crash_code == 0
            and recovered_count == 1
            and recovered_status == "recovery_required"
            and empty_reference_rejected
            and requeued is not None
            and requeued.status in {"queued", "running", "succeeded"}
            and restart_code == 0
            and final_status == "succeeded"
        ),
        "instance_count": 2,
        "crash_exit_code": crash_code,
        "recovered_count": recovered_count,
        "recovered_status": recovered_status,
        "empty_reference_rejected": empty_reference_rejected,
        "final_status": final_status,
        "restart_route": (restart_payload or {}).get("route"),
        "error": crash_error or restart_error,
        "task_id_digest": _safe_id(task_id),
    }


def run_reliability_evidence(*, timeout_seconds: float = 15.0) -> dict[str, Any]:
    """Run deterministic process-level reliability scenarios."""
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ad-agent-reliability-") as directory:
        database = str(Path(directory) / "shared-evidence.db")
        store = AdAgentStore(database)
        try:
            scenario_functions = (
                _session_lease_evidence,
                _task_claim_evidence,
                _worker_route_evidence,
                _worker_recovery_evidence,
            )
            scenarios: list[dict[str, Any]] = []
            for function in scenario_functions:
                try:
                    scenarios.append(function(database, store))
                except Exception as error:
                    scenarios.append({
                        "scenario": function.__name__,
                        "passed": False,
                        "error": f"{type(error).__name__}: {error}",
                    })
                if time.monotonic() - started > max(1.0, timeout_seconds):
                    scenarios.append({
                        "scenario": "runner_timeout",
                        "passed": False,
                        "error": "reliability evidence runner exceeded its time budget",
                    })
                    break
        finally:
            store.close()
    return {
        "format_version": FORMAT_VERSION,
        "generated_at": _now(),
        "evidence_scope": "local_shared_persistence_processes",
        "production_deployment_attested": False,
        "provider_calls": 0,
        "scenario_count": len(scenarios),
        "passed_scenarios": sum(1 for item in scenarios if item.get("passed")),
        "failed_scenarios": sum(1 for item in scenarios if not item.get("passed")),
        "passed": bool(scenarios) and all(item.get("passed") for item in scenarios),
        "scenarios": scenarios,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("child", nargs="*")
    args = parser.parse_args(argv)
    if args.child:
        return _child_command(args.child)
    report = run_reliability_evidence(
        timeout_seconds=max(1.0, float(args.timeout_seconds)),
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
