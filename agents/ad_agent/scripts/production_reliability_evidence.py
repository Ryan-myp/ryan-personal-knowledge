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
import selectors
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.persistence.models import TaskRecord  # noqa: E402
from agents.ad_agent.persistence.mysql_store import MySQLStore  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402


FORMAT_VERSION = 2
MYSQL_ADMIN_URL_ENV = "AD_AGENT_RELIABILITY_ADMIN_URL"
MYSQL_DATABASE_URL_ENV = "AD_AGENT_RELIABILITY_DATABASE_URL"
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


def _open_store(database: str, database_url: str | None = None) -> Any:
    if database != "mysql":
        return AdAgentStore(database)
    configured_url = str(
        database_url or os.environ.get(MYSQL_DATABASE_URL_ENV) or ""
    ).strip()
    parsed = urlparse(configured_url.replace("mysql+pymysql://", "mysql://", 1))
    database_name = parsed.path.strip("/")
    if (
        parsed.scheme != "mysql"
        or not database_name.startswith("agent_reliability_")
    ):
        raise ValueError("isolated MySQL reliability database is not configured")
    return MySQLStore(configured_url, pool_size=3, max_overflow=2)


def _mysql_connection_options(database_url: str) -> tuple[Any, dict[str, Any]]:
    try:
        import pymysql
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("MySQL reliability evidence requires PyMySQL") from error

    parsed = urlparse(database_url.replace("mysql+pymysql://", "mysql://", 1))
    if parsed.scheme != "mysql" or not parsed.hostname:
        raise ValueError("MySQL admin URL must identify a MySQL server")
    query = parse_qs(parsed.query)
    unix_socket = query.get("unix_socket", [None])[0]
    host = str(parsed.hostname).lower()
    if host not in {"localhost", "127.0.0.1", "::1"} and not unix_socket:
        raise ValueError("ephemeral MySQL evidence is restricted to a local server")
    options: dict[str, Any] = {
        "host": parsed.hostname,
        "port": int(parsed.port or 3306),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.strip("/") or None,
        "charset": "utf8mb4",
        "autocommit": True,
        "connect_timeout": 5,
    }
    if unix_socket:
        options["unix_socket"] = unix_socket
    return pymysql, options


def _create_mysql_sandbox(admin_url: str) -> tuple[str, Any, str]:
    pymysql, options = _mysql_connection_options(admin_url)
    connection = pymysql.connect(**options)
    database_name = f"agent_reliability_{uuid.uuid4().hex}_test"
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    except Exception:
        connection.close()
        raise
    try:
        parsed = urlparse(admin_url)
        query = parse_qs(parsed.query)
        query.pop("unix_socket", None)
        # MySQLStore accepts the socket in the URL query. Keep all other
        # options, including the password, in-process and out of child args.
        if options.get("unix_socket"):
            query["unix_socket"] = [str(options["unix_socket"])]
        database_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            f"/{database_name}",
            parsed.params,
            urlencode(query, doseq=True),
            parsed.fragment,
        ))
    except Exception:
        _drop_mysql_sandbox(connection, database_name, admin_url=admin_url)
        raise
    return database_url, connection, database_name


def _drop_mysql_sandbox(
    connection: Any,
    database_name: str,
    *,
    admin_url: str | None = None,
) -> None:
    if not database_name.startswith("agent_reliability_"):
        raise ValueError("refusing to drop a non-evidence database")
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
    except Exception:
        try:
            if not admin_url:
                raise RuntimeError("temporary MySQL schema cleanup failed")
            pymysql, options = _mysql_connection_options(admin_url)
            replacement = pymysql.connect(**options)
            try:
                with replacement.cursor() as cursor:
                    cursor.execute(
                        f"DROP DATABASE IF EXISTS `{database_name}`"
                    )
            finally:
                replacement.close()
        except Exception as retry_error:
            raise RuntimeError(
                "temporary MySQL schema cleanup failed"
            ) from retry_error
        finally:
            connection.close()
        return
    else:
        connection.close()


def _child_claim_task(database: str, task_id: str, worker_id: str) -> int:
    store = _open_store(database)
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
    database: str, session_id: str, owner: str,
) -> int:
    store = _open_store(database)
    try:
        acquired = store.acquire_session_lease(
            session_id, owner, lease_seconds=30.0,
        )
        _json_line({"acquired": acquired})
        if acquired:
            sys.stdin.readline()
            store.release_session_lease(session_id, owner)
        return 0
    finally:
        store.close()


def _child_crash_after_claim(database: str, task_id: str) -> int:
    store = _open_store(database)
    record = store.claim_task(task_id, "crashed-worker", lease_seconds=0.4)
    if record is None:
        store.close()
        return 2
    # Simulate a process crash after claiming but before a terminal update.
    os._exit(0)


def _child_run_worker(
    database: str,
    task_id: str,
    timeout_seconds: float,
    hold_before_run_seconds: float = 0.0,
) -> int:
    from agents.ad_agent.runtime.ad_application import AdvertisingComposition

    store = _open_store(database)
    runtime_entry_calls = 0
    original_run = AdvertisingComposition.run

    def observed_run(
        runtime_instance: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal runtime_entry_calls
        runtime_entry_calls += 1
        if hold_before_run_seconds > 0:
            time.sleep(hold_before_run_seconds)
        return original_run(runtime_instance, *args, **kwargs)

    AdvertisingComposition.run = observed_run
    runtime = None
    try:
        runtime = AdvertisingComposition(
            require_llm=False,
            persistence_store=store,
            features=[],
            enforce_account_scope=False,
            max_task_workers=1,
            max_task_queue=0,
            task_timeout_seconds=max(1.0, timeout_seconds),
            task_lease_seconds=2.0,
            task_queue_poll_interval=0.02,
        )
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while time.monotonic() < deadline:
            record = store.get_task(task_id)
            if record is not None and record.status in TERMINAL_TASK_STATUSES:
                result = record.result if isinstance(record.result, dict) else {}
                run_id = str(result.get("run_id") or "")
                run = store.get_execution_run(run_id) if run_id else None
                _json_line({
                    "status": record.status,
                    "runtime_entry_called": runtime_entry_calls > 0,
                    "turn_id_present": bool(result.get("turn_id")),
                    "run_store_status": getattr(run, "status", None),
                    "tool_result_count": len(result.get("results") or []),
                    "worker_id": runtime.task_executor.metrics().get("worker_id"),
                })
                return 0
            time.sleep(0.02)
        record = store.get_task(task_id)
        _json_line({
            "status": record.status if record is not None else None,
            "runtime_entry_called": runtime_entry_calls > 0,
            "worker_id": runtime.task_executor.metrics().get("worker_id"),
            "timeout": True,
        })
        return 1
    finally:
        try:
            if runtime is not None:
                runtime.close(wait=True)
            else:
                store.close()
        finally:
            AdvertisingComposition.run = original_run


def _child_command(arguments: list[str]) -> int:
    command = arguments[0] if arguments else ""
    if command == "claim-task" and len(arguments) == 4:
        return _child_claim_task(arguments[1], arguments[2], arguments[3])
    if command == "session-lease" and len(arguments) == 4:
        return _child_session_lease(
            arguments[1], arguments[2], arguments[3],
        )
    if command == "crash-after-claim" and len(arguments) == 3:
        return _child_crash_after_claim(arguments[1], arguments[2])
    if command == "run-worker" and len(arguments) in {4, 5}:
        return _child_run_worker(
            arguments[1],
            arguments[2],
            float(arguments[3]),
            float(arguments[4]) if len(arguments) == 5 else 0.0,
        )
    raise ValueError("unsupported reliability evidence child command")


def _child_process(
    arguments: list[str],
    environment_overrides: Mapping[str, str] | None = None,
) -> subprocess.Popen[str]:
    environment = dict(os.environ)
    current_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(ROOT) + os.pathsep + current_pythonpath
        if current_pythonpath else str(ROOT)
    )
    environment.update(dict(environment_overrides or {}))
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        cwd=str(ROOT),
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _read_process(
    process: subprocess.Popen[str], timeout_seconds: float,
) -> tuple[int, dict[str, Any] | None, str]:
    try:
        stdout, stderr = process.communicate(
            timeout=max(0.01, timeout_seconds),
        )
    except subprocess.TimeoutExpired:
        stdout, stderr = _terminate_process(process)
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
    error = "child process wrote to stderr" if stderr.strip() else ""
    if process.returncode != 0 and not error:
        error = f"child exited with code {process.returncode}"
    return int(process.returncode or 0), payload, error


def _terminate_process(
    process: subprocess.Popen[str],
) -> tuple[str, str]:
    if process.poll() is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            return process.communicate(timeout=0.25)
        except subprocess.TimeoutExpired:
            process.kill()
    return process.communicate()


def _read_json_line(
    stream: Any,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    if stream is None:
        return None
    deadline = time.monotonic() + max(0.01, timeout_seconds)
    output = bytearray()
    selector = selectors.DefaultSelector()
    try:
        selector.register(stream, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(timeout=remaining):
                return None
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                break
            output.extend(chunk)
            if b"\n" in output:
                break
    finally:
        selector.close()
    try:
        line = bytes(output).split(b"\n", 1)[0].decode("utf-8")
        payload = json.loads(line)
    except (UnicodeDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_processes(
    processes: Iterable[subprocess.Popen[str]], timeout_seconds: float,
) -> list[tuple[int, dict[str, Any] | None, str]]:
    deadline = time.monotonic() + max(0.01, timeout_seconds)
    results = []
    for process in processes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process(process)
            results.append((-9, None, "child process timed out"))
            continue
        results.append(_read_process(process, remaining))
    return results


def _spawn_child_processes(
    commands: Iterable[list[str]],
    environment_overrides: Mapping[str, str],
) -> list[subprocess.Popen[str]]:
    processes: list[subprocess.Popen[str]] = []
    try:
        for command in commands:
            processes.append(_child_process(command, environment_overrides))
    except Exception:
        for process in processes:
            _terminate_process(process)
        raise
    return processes


def _remaining_seconds(deadline: float, maximum: float) -> float:
    remaining = min(float(maximum), deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("reliability evidence time budget exhausted")
    return remaining


def _session_lease_evidence(
    database: str,
    store: Any,
    child_environment: Mapping[str, str],
    deadline: float,
) -> dict[str, Any]:
    session_id = f"evidence-session-{uuid.uuid4().hex}"
    holder = f"holder-{uuid.uuid4().hex}"
    store.create_session(
        session_id,
        "evidence-user",
        metadata={"tenant_id": "evidence-tenant"},
    )
    process = _child_process(
        ["session-lease", database, session_id, holder],
        child_environment,
    )
    holder_payload = None
    contender_payload = None
    contender_code = -1
    contender_error = ""
    try:
        holder_payload = _read_json_line(
            process.stdout,
            timeout_seconds=_remaining_seconds(deadline, 15.0),
        )
        if bool((holder_payload or {}).get("acquired")):
            contender_timeout = _remaining_seconds(deadline, 5.0)
            contender = _child_process(
                ["session-lease", database, session_id, "contender"],
                child_environment,
            )
            contender_code, contender_payload, contender_error = _read_process(
                contender,
                contender_timeout,
            )
    finally:
        if process.stdin is not None:
            try:
                process.stdin.write("release\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
    holder_code, _remaining_payload, holder_error = _read_process(
        process,
        min(1.0, max(0.01, deadline - time.monotonic() + 0.5)),
    )
    acquired = bool((holder_payload or {}).get("acquired"))
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
            and contender_code == 0
        ),
        "instance_count": 2,
        "lease_owner_digest": _safe_id(holder),
        "busy_count": busy_count,
        "holder_exit_code": holder_code,
        "contender_acquired": bool((contender_payload or {}).get("acquired")),
        "error_type": (
            "ChildProcessError"
            if holder_error or contender_error or contender_code not in {0, -1}
            else None
        ),
    }


def _task_claim_evidence(
    database: str,
    store: Any,
    child_environment: Mapping[str, str],
    deadline: float,
) -> dict[str, Any]:
    task_id = f"evidence-claim-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    wait_timeout = _remaining_seconds(deadline, 5.0)
    processes = _spawn_child_processes(
        (
            ["claim-task", database, task_id, f"worker-{index}"]
            for index in range(2)
        ),
        child_environment,
    )
    results = _read_processes(
        processes,
        wait_timeout,
    )
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


def _worker_route_evidence(
    database: str,
    store: Any,
    child_environment: Mapping[str, str],
    deadline: float,
) -> dict[str, Any]:
    task_id = f"evidence-worker-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    wait_timeout = _remaining_seconds(deadline, 8.0)
    processes = _spawn_child_processes(
        (
            ["run-worker", database, task_id, "8"]
            for _index in range(2)
        ),
        child_environment,
    )
    results = _read_processes(
        processes,
        wait_timeout,
    )
    record = store.get_task(task_id)
    terminal_status = record.status if record is not None else None
    run_id = (
        str(record.result.get("run_id") or "")
        if record is not None and isinstance(record.result, dict) else ""
    )
    run = store.get_execution_run(run_id) if run_id else None
    run_store_status = getattr(run, "status", None)
    return {
        "scenario": "worker_runtime_route",
        "passed": bool(
            terminal_status == "succeeded"
            and run_id
            and run_store_status == "succeeded"
            and bool(
                record.result.get("turn_id")
                if record is not None and isinstance(record.result, dict)
                else False
            )
            and all(code == 0 for code, _payload, _error in results)
            and sum(
                1 for _code, payload, _error in results
                if bool((payload or {}).get("runtime_entry_called"))
            ) == 1
        ),
        "instance_count": 2,
        "terminal_status": terminal_status,
        "runtime_entry": "AdvertisingComposition.run",
        "run_store_status": run_store_status,
        "run_id_digest": _safe_id(run_id) if run_id else None,
        "turn_id_present": bool(
            record.result.get("turn_id")
            if record is not None and isinstance(record.result, dict) else False
        ),
        "tool_result_count": len(
            record.result.get("results") or []
            if record is not None and isinstance(record.result, dict) else []
        ),
        "successful_worker_count": sum(
            1 for _code, payload, _error in results
            if bool((payload or {}).get("runtime_entry_called"))
        ),
        "task_id_digest": _safe_id(task_id),
    }


def _worker_liveness_evidence(
    database: str,
    store: Any,
    child_environment: Mapping[str, str],
    deadline: float,
) -> dict[str, Any]:
    task_id = f"evidence-worker-liveness-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    worker_timeout = _remaining_seconds(deadline, 9.0)
    process = _child_process(
        ["run-worker", database, task_id, "8", "5.0"],
        child_environment,
    )
    worker_id = ""
    first_heartbeat = ""
    heartbeat_advanced_while_running = False
    registered_while_running = False
    record = None
    process_code = -1
    payload = None
    process_error = ""
    try:
        observation_deadline = min(
            deadline,
            time.monotonic() + worker_timeout,
        )
        while time.monotonic() < observation_deadline:
            record = store.get_task(task_id)
            task_running = record is not None and record.status == "running"
            workers = store.list_workers(statuses=["running"], limit=200)
            current = workers[0] if workers else None
            if current is not None:
                worker_id = str(current.get("worker_id") or "")
                heartbeat = str(current.get("last_heartbeat_at") or "")
                registered_while_running = registered_while_running or task_running
                if first_heartbeat and heartbeat != first_heartbeat and task_running:
                    heartbeat_advanced_while_running = True
                if not first_heartbeat:
                    first_heartbeat = heartbeat
            if (
                record is not None
                and record.status in TERMINAL_TASK_STATUSES
                and heartbeat_advanced_while_running
            ):
                break
            time.sleep(0.05)
        process_code, payload, process_error = _read_process(
            process,
            min(2.0, max(0.01, deadline - time.monotonic() + 0.5)),
        )
    finally:
        if process.poll() is None:
            _terminate_process(process)

    if not worker_id:
        worker_id = str((payload or {}).get("worker_id") or "")
    record = store.get_task(task_id)
    worker_record = next(
        (
            item for item in store.list_workers(limit=200)
            if str(item.get("worker_id") or "") == worker_id
        ),
        None,
    ) if worker_id else None
    return {
        "scenario": "worker_liveness_multi_instance",
        "passed": bool(
            process_code == 0
            and not process_error
            and record is not None
            and record.status == "succeeded"
            and registered_while_running
            and heartbeat_advanced_while_running
            and bool((payload or {}).get("runtime_entry_called"))
            and worker_record is not None
            and worker_record.get("status") == "stopped"
            and worker_record.get("lease_expires_at") is None
        ),
        "instance_count": 2,
        "registered_while_running": registered_while_running,
        "heartbeat_advanced_while_running": heartbeat_advanced_while_running,
        "shutdown_status": (
            worker_record.get("status") if worker_record is not None else None
        ),
        "lease_cleared": bool(
            worker_record is not None
            and worker_record.get("lease_expires_at") is None
        ),
        "runtime_entry_called": bool(
            (payload or {}).get("runtime_entry_called")
        ),
        "error_type": "ChildProcessError" if process_error else None,
        "worker_id_digest": _safe_id(worker_id) if worker_id else None,
        "task_id_digest": _safe_id(task_id),
    }


def _worker_recovery_evidence(
    database: str,
    store: Any,
    child_environment: Mapping[str, str],
    deadline: float,
) -> dict[str, Any]:
    task_id = f"evidence-recovery-{uuid.uuid4().hex}"
    store.create_task(_task(task_id))
    crash_timeout = _remaining_seconds(deadline, 5.0)
    crashed = _child_process(
        ["crash-after-claim", database, task_id], child_environment,
    )
    crash_code, _payload, crash_error = _read_process(
        crashed,
        crash_timeout,
    )
    time.sleep(min(0.65, _remaining_seconds(deadline, 1.0)))
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
    restart_timeout = _remaining_seconds(deadline, 8.0)
    restarted = _child_process(
        ["run-worker", database, task_id, "8"], child_environment,
    )
    restart_code, restart_payload, restart_error = _read_process(
        restarted,
        restart_timeout,
    )
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
            and bool((restart_payload or {}).get("runtime_entry_called"))
            and (restart_payload or {}).get("run_store_status") == "succeeded"
            and final_status == "succeeded"
        ),
        "instance_count": 2,
        "crash_exit_code": crash_code,
        "recovered_count": recovered_count,
        "recovered_status": recovered_status,
        "empty_reference_rejected": empty_reference_rejected,
        "final_status": final_status,
        "restart_runtime_entry": "AdvertisingComposition.run",
        "restart_run_id_present": bool(
            (restart_payload or {}).get("runtime_entry_called")
        ),
        "restart_run_store_status": (restart_payload or {}).get("run_store_status"),
        "error_type": (
            "ChildProcessError"
            if crash_error or restart_error else None
        ),
        "task_id_digest": _safe_id(task_id),
    }


def run_reliability_evidence(
    *,
    timeout_seconds: float = 30.0,
    backend: str = "sqlite",
    admin_database_url: str | None = None,
) -> dict[str, Any]:
    """Run process-level reliability evidence against an isolated SQL database."""
    started = time.monotonic()
    selected_backend = str(backend or "sqlite").strip().lower()
    if selected_backend not in {"sqlite", "mysql"}:
        raise ValueError("reliability evidence backend must be sqlite or mysql")
    mysql_connection = None
    mysql_database_name = None
    mysql_database_url = None
    child_environment: dict[str, str] = {}
    if selected_backend == "mysql":
        configured_admin_url = str(
            admin_database_url
            or os.environ.get(MYSQL_ADMIN_URL_ENV)
            or ""
        ).strip()
        if not configured_admin_url:
            raise ValueError(
                f"{MYSQL_ADMIN_URL_ENV} is required for MySQL evidence"
            )
        mysql_database_url, mysql_connection, mysql_database_name = (
            _create_mysql_sandbox(configured_admin_url)
        )
        database = "mysql"
        child_environment[MYSQL_DATABASE_URL_ENV] = mysql_database_url
    else:
        database = ""
    try:
        with tempfile.TemporaryDirectory(prefix="ad-agent-reliability-") as directory:
            if selected_backend == "sqlite":
                database = str(Path(directory) / "shared-evidence.db")
            store = _open_store(database, mysql_database_url)
            try:
                scenario_functions = (
                    _session_lease_evidence,
                    _task_claim_evidence,
                    _worker_route_evidence,
                    _worker_liveness_evidence,
                    _worker_recovery_evidence,
                )
                scenarios: list[dict[str, Any]] = []
                deadline = started + max(1.0, timeout_seconds)
                for function in scenario_functions:
                    try:
                        scenarios.append(function(
                            database, store, child_environment, deadline,
                        ))
                    except Exception as error:
                        scenarios.append({
                            "scenario": function.__name__,
                            "passed": False,
                            "error_type": type(error).__name__,
                        })
                    if time.monotonic() >= deadline:
                        scenarios.append({
                            "scenario": "runner_timeout",
                            "passed": False,
                            "error": "reliability evidence runner exceeded its time budget",
                        })
                        break
            finally:
                store.close()
    finally:
        if mysql_connection is not None and mysql_database_name is not None:
            _drop_mysql_sandbox(
                mysql_connection,
                mysql_database_name,
                admin_url=configured_admin_url,
            )
    return {
        "format_version": FORMAT_VERSION,
        "generated_at": _now(),
        "evidence_scope": (
            "local_mysql_shared_persistence_processes"
            if selected_backend == "mysql"
            else "local_sqlite_shared_persistence_processes"
        ),
        "persistence_backend": selected_backend,
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
    parser.add_argument(
        "--backend",
        choices=("sqlite", "mysql"),
        default="sqlite",
        help="mysql uses a temporary local database created from "
        f"{MYSQL_ADMIN_URL_ENV}; the schema is dropped after the run.",
    )
    parser.add_argument("child", nargs="*")
    args = parser.parse_args(argv)
    if args.child:
        return _child_command(args.child)
    try:
        report = run_reliability_evidence(
            timeout_seconds=max(1.0, float(args.timeout_seconds)),
            backend=args.backend,
        )
    except Exception as error:
        report = {
            "format_version": FORMAT_VERSION,
            "generated_at": _now(),
            "evidence_scope": f"local_{args.backend}_shared_persistence_processes",
            "persistence_backend": args.backend,
            "production_deployment_attested": False,
            "provider_calls": 0,
            "scenario_count": 0,
            "passed_scenarios": 0,
            "failed_scenarios": 1,
            "passed": False,
            "error_type": type(error).__name__,
            "scenarios": [],
        }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
