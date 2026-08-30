"""Managed Agent Skill packages and version publication.

User-authored Skills are standard Agent Skills directories: ``SKILL.md`` is
the entry point, while ``scripts/``, ``references/``, ``assets/`` and other
package files are preserved as part of the version snapshot.  The important
security boundary is that this package is *context*, not a new executable
provider integration.  The Runtime never imports files from a managed
package; advertising side effects remain behind the existing Capability/Tool
registry and its policy gates.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

import yaml

from .runtime.skill import SkillContract


class SkillPackageError(ValueError):
    """Raised when a submitted Skill directory is not safe or valid."""


_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_MAX_FILES = 512
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_PACKAGE_BYTES = 16 * 1024 * 1024
_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".csv"}
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?im)(?P<field>access[_-]?token|refresh[_-]?token|developer[_-]?token|"
    r"client[_-]?secret|private[_-]?key|app[_-]?secret|api[_-]?key|"
    r"bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|"
    r"manager[_-]?customer[_-]?id)\s*[:=]"
)

# Skill evaluation is an expensive external process/API operation. Keep a
# process-level bounded queue because the HTTP layer creates a short-lived
# manager facade per request; a manager-local executor would not actually
# bound concurrent evaluations across requests.
_EVAL_MAX_WORKERS = max(
    1, min(int(os.environ.get("AD_AGENT_SKILL_EVAL_WORKERS", "2")), 8)
)
_EVAL_MAX_QUEUE = max(
    0, min(int(os.environ.get("AD_AGENT_SKILL_EVAL_QUEUE", "8")), 64)
)
_EVAL_EXECUTOR = ThreadPoolExecutor(
    max_workers=_EVAL_MAX_WORKERS,
    thread_name_prefix="ad-agent-skill-eval",
)
_EVAL_CAPACITY = threading.BoundedSemaphore(_EVAL_MAX_WORKERS + _EVAL_MAX_QUEUE)


def _safe_component(value: str, field: str) -> str:
    value = str(value or "").strip().lower()
    if not _NAME_RE.fullmatch(value):
        raise SkillPackageError(
            f"{field} must match {_NAME_RE.pattern}"
        )
    return value


def _safe_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillPackageError("Skill file path must be a non-empty string")
    raw = value.replace("\\", "/")
    if "\x00" in raw:
        raise SkillPackageError("Skill file path contains NUL")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise SkillPackageError(f"unsafe Skill file path: {value}")
    normalized = str(path)
    if normalized in {".", ""} or normalized.startswith(".git/") or "/.git/" in normalized:
        raise SkillPackageError(f"reserved Skill file path: {value}")
    if any(part == "__pycache__" for part in path.parts):
        raise SkillPackageError(f"generated Skill file is not allowed: {value}")
    if len(normalized) > 240:
        raise SkillPackageError("Skill file path is too long")
    return normalized


def _decode_file(value: Any, path: str) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if not isinstance(value, Mapping):
        raise SkillPackageError(f"Skill file {path} must be UTF-8 text or an encoded object")
    content = value.get("content")
    encoding = str(value.get("encoding", "utf-8")).lower()
    if not isinstance(content, str):
        raise SkillPackageError(f"Skill file {path}.content must be a string")
    if encoding in {"utf-8", "text"}:
        return content.encode("utf-8")
    if encoding in {"base64", "base64url"}:
        try:
            return base64.b64decode(content, validate=True)
        except (ValueError, TypeError) as exc:
            raise SkillPackageError(f"Skill file {path} has invalid base64") from exc
    raise SkillPackageError(f"unsupported encoding for Skill file {path}: {encoding}")


def normalize_skill_files(raw_files: Mapping[str, Any]) -> dict[str, bytes]:
    """Normalize a complete standard Skill directory snapshot.

    The API accepts text directly and ``{encoding: base64, content: ...}``
    for binary assets.  Arbitrary files are retained, but no file is imported
    by the service process.
    """
    if not isinstance(raw_files, Mapping):
        raise SkillPackageError("files must be an object keyed by relative path")
    if len(raw_files) == 0 or len(raw_files) > _MAX_FILES:
        raise SkillPackageError(f"Skill package must contain 1..{_MAX_FILES} files")
    result: dict[str, bytes] = {}
    total = 0
    for raw_path, raw_value in raw_files.items():
        path = _safe_path(raw_path)
        if path in result:
            raise SkillPackageError(f"duplicate Skill file: {path}")
        data = _decode_file(raw_value, path)
        if len(data) > _MAX_FILE_BYTES:
            raise SkillPackageError(f"Skill file {path} exceeds {_MAX_FILE_BYTES} bytes")
        total += len(data)
        if total > _MAX_PACKAGE_BYTES:
            raise SkillPackageError(f"Skill package exceeds {_MAX_PACKAGE_BYTES} bytes")
        result[path] = data
    if "SKILL.md" not in result:
        raise SkillPackageError("standard Skill package requires SKILL.md")
    try:
        result["SKILL.md"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillPackageError("SKILL.md must be UTF-8 text") from exc
    return dict(sorted(result.items()))


def encode_skill_files(files: Mapping[str, bytes]) -> dict[str, dict[str, str]]:
    """Encode bytes for persistence without losing binary assets."""
    return {
        str(path): {
            "encoding": "base64",
            "content": base64.b64encode(bytes(data)).decode("ascii"),
        }
        for path, data in sorted(files.items())
    }


def decode_skill_files(value: Mapping[str, Any]) -> dict[str, bytes]:
    return normalize_skill_files(value)


def _validate_no_credential_assignments(files: Mapping[str, bytes]) -> None:
    """Keep credentials out of Skill context and persisted Skill snapshots.

    Natural-language guidance may explain that credentials are Runtime-owned,
    but a Skill package must not contain credential-shaped assignments. Eval
    case fixtures are excluded because they deliberately test this boundary
    and are never loaded as model context.
    """
    for raw_path, data in files.items():
        path = str(raw_path)
        if path.lower().startswith("evals/") or Path(path).suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            continue
        match = _CREDENTIAL_ASSIGNMENT_RE.search(text)
        if match:
            raise SkillPackageError(
                f"Skill file {path} contains forbidden credential field assignment: "
                f"{match.group('field')}"
            )


def skill_package_digest(files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(files.items()):
        encoded_path = path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


class ManagedSkillManager:
    """CRUD, validation and materialization for versioned Skill packages."""

    def __init__(self, store: Any, root: Optional[str] = None):
        self.store = store
        configured = root or os.environ.get("AD_AGENT_MANAGED_SKILLS_ROOT")
        if configured:
            self.root = Path(configured).expanduser().resolve()
        else:
            db_path = getattr(store, "_db_path", ":memory:")
            if db_path == ":memory:":
                base = Path(tempfile.gettempdir()) / "ad-agent-managed-skills"
            else:
                base = Path(str(db_path)).expanduser().resolve().parent / "managed-skills"
            self.root = base
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_skill_document(skill_name: str, files: Mapping[str, bytes]) -> None:
        """Validate SKILL.md with the production parser without importing code."""
        with tempfile.TemporaryDirectory(prefix="ad-agent-skill-validate-") as temp:
            directory = Path(temp) / skill_name
            directory.mkdir()
            for path, data in files.items():
                target = directory / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            try:
                contract = SkillContract(str(directory)).load()
            except Exception as exc:
                raise SkillPackageError(f"invalid SKILL.md package: {exc}") from exc
            if contract.context_only:
                raise SkillPackageError("business context files are not standalone managed Skills")
            if contract.name != skill_name:
                raise SkillPackageError(
                    f"SKILL.md name '{contract.name}' does not match package name '{skill_name}'"
                )

    def validate(
        self, skill_name: str, version: str, raw_files: Mapping[str, Any]
    ) -> tuple[dict[str, bytes], str]:
        skill_name = _safe_component(skill_name, "skill_name")
        version = str(version or "").strip()
        if not _SEMVER_RE.fullmatch(version):
            raise SkillPackageError("version must be semantic versioning, for example 1.0.0")
        files = normalize_skill_files(raw_files)
        _validate_no_credential_assignments(files)
        self._validate_skill_document(skill_name, files)
        return files, skill_package_digest(files)

    @staticmethod
    def _public(version: Mapping[str, Any], include_files: bool = False) -> dict[str, Any]:
        result = {
            key: version.get(key)
            for key in (
                "version_id", "tenant_id", "skill_name", "version", "status",
                "sha256", "created_by", "created_at", "published_at",
                "evaluation_status", "evaluation_run_id", "evaluation_report",
            )
        }
        files = version.get("files") or {}
        result["files"] = files if include_files else sorted(files)
        return result

    def create_version(
        self, tenant_id: str, skill_name: str, version: str,
        raw_files: Mapping[str, Any], created_by: str,
    ) -> dict[str, Any]:
        files, digest = self.validate(skill_name, version, raw_files)
        version_id = uuid.uuid4().hex
        try:
            record = self.store.create_skill_version(
                version_id=version_id,
                tenant_id=str(tenant_id or "default"),
                skill_name=skill_name,
                version=version,
                files=encode_skill_files(files),
                sha256=digest,
                created_by=str(created_by),
            )
        except Exception as exc:
            # Keep backend details out of the HTTP response while preserving
            # the conflict semantics expected by an editor UI.
            if "UNIQUE" in str(exc).upper() or "unique" in str(exc):
                raise SkillPackageError(
                    f"Skill version already exists: {skill_name}@{version}"
                ) from exc
            raise
        return self._public(record)

    def create_version_archive(
        self, tenant_id: str, skill_name: str, version: str,
        archive: bytes, created_by: str,
    ) -> dict[str, Any]:
        """Create a version from a standard Skill ZIP directory."""
        if not isinstance(archive, (bytes, bytearray)) or len(archive) > _MAX_PACKAGE_BYTES:
            raise SkillPackageError(f"Skill archive exceeds {_MAX_PACKAGE_BYTES} bytes")
        try:
            zfile = zipfile.ZipFile(io.BytesIO(bytes(archive)))
        except (zipfile.BadZipFile, TypeError) as exc:
            raise SkillPackageError("request body must be a valid Skill ZIP archive") from exc
        entries: dict[str, bytes] = {}
        total = 0
        with zfile:
            infos = [info for info in zfile.infolist() if not info.is_dir()]
            if not infos or len(infos) > _MAX_FILES:
                raise SkillPackageError(f"Skill archive must contain 1..{_MAX_FILES} files")
            for info in infos:
                path = _safe_path(info.filename.rstrip("/"))
                mode = (info.external_attr >> 16) & 0o170000
                if stat.S_ISLNK(mode):
                    raise SkillPackageError(f"symbolic links are not allowed in Skill archives: {path}")
                if info.file_size > _MAX_FILE_BYTES:
                    raise SkillPackageError(f"Skill file {path} exceeds {_MAX_FILE_BYTES} bytes")
                if path in entries:
                    raise SkillPackageError(f"duplicate Skill file: {path}")
                data = zfile.read(info)
                total += len(data)
                if total > _MAX_PACKAGE_BYTES:
                    raise SkillPackageError(f"Skill archive exceeds {_MAX_PACKAGE_BYTES} bytes uncompressed")
                entries[path] = data
        # ZIP tools commonly include one directory wrapper. Strip it only when
        # it is unambiguous; never silently guess among multiple roots.
        if "SKILL.md" not in entries:
            prefixes = {path.split("/", 1)[0] for path in entries if "/" in path}
            if len(prefixes) == 1:
                prefix = next(iter(prefixes)) + "/"
                candidate = {
                    path[len(prefix):]: data
                    for path, data in entries.items()
                    if path.startswith(prefix) and path[len(prefix):]
                }
                if "SKILL.md" in candidate:
                    entries = candidate
        return self.create_version(tenant_id, skill_name, version, entries, created_by)

    def get_version(
        self, tenant_id: str, skill_name: str, version: Optional[str] = None,
        include_files: bool = False,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_skill_version(tenant_id, skill_name, version)
        return self._public(record, include_files=include_files) if record else None

    def list_versions(
        self, tenant_id: str, skill_name: Optional[str] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        return [
            self._public(record)
            for record in self.store.list_skill_versions(tenant_id, skill_name, limit)
        ]

    def _materialize(self, record: Mapping[str, Any]) -> Path:
        tenant_key = hashlib.sha256(str(record["tenant_id"]).encode()).hexdigest()[:20]
        skill_name = _safe_component(str(record["skill_name"]), "skill_name")
        version = re.sub(r"[^a-zA-Z0-9_-]", "_", str(record["version"]))
        if not version:
            raise SkillPackageError("invalid Skill version path")
        target = self.root / tenant_key / skill_name / version
        if target.exists():
            return target
        staging_root = self.root / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="skill-", dir=str(staging_root)))
        try:
            files = decode_skill_files(record.get("files") or {})
            for path, data in files.items():
                output = staging / path
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(staging), str(target))
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target

    def publish(
        self, tenant_id: str, skill_name: str, version: str, runtime: Any = None,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_skill_version(tenant_id, skill_name, version)
        if not record:
            return None
        # Re-validate the immutable snapshot at publication time.  This keeps
        # a future backend migration or manual DB edit from bypassing checks.
        files, digest = self.validate(skill_name, version, record.get("files") or {})
        if digest != record.get("sha256"):
            raise SkillPackageError("Skill package digest mismatch")
        # A package that declares an evaluation suite has an explicit release
        # gate.  Keep evaluation optional for simple context-only Skills, but
        # never publish a version while its declared acceptance suite is
        # missing, queued, running, failed, or errored.
        if "evals/eval.yaml" in files and record.get("evaluation_status") != "passed":
            raise SkillPackageError(
                "Skill version with evals/eval.yaml must pass skill-up before publication"
            )
        materialized = self._materialize(record)
        published = self.store.publish_skill_version(tenant_id, skill_name, version)
        if not published:
            return None
        if runtime is not None:
            runtime.load_managed_skill(str(materialized), tenant_id=str(tenant_id))
        return self._public(published)

    def activate_published(self, tenant_id: str, runtime: Any) -> int:
        records = self.store.list_skill_versions(tenant_id, None, 200)
        active = [record for record in records if record.get("status") == "published"]
        loaded = 0
        for record in active:
            materialized = self._materialize(record)
            runtime.load_managed_skill(str(materialized), tenant_id=str(tenant_id))
            loaded += 1
        return loaded

    @staticmethod
    def _validate_eval_config(record: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
        """Validate the user Skill's data-only skill-up configuration.

        The service deliberately does not execute user-provided custom engine
        commands or judge scripts. Built-in engines and declarative/agent
        judges run in the isolated evaluation workspace and use only the
        platform's configured credentials.
        """
        files = decode_skill_files(record.get("files") or {})
        eval_path = Path("evals/eval.yaml")
        if str(eval_path) not in files:
            raise SkillPackageError("Skill evaluation requires evals/eval.yaml")
        try:
            config = yaml.safe_load(files[str(eval_path)].decode("utf-8")) or {}
        except (UnicodeDecodeError, yaml.YAMLError) as exc:
            raise SkillPackageError(f"invalid evals/eval.yaml: {exc}") from exc
        if not isinstance(config, dict):
            raise SkillPackageError("evals/eval.yaml must be an object")
        engine = config.get("engine") or {}
        if not isinstance(engine, dict):
            raise SkillPackageError("skill-up engine must be an object")
        if engine.get("custom") is not None:
            raise SkillPackageError("managed Skill evaluation cannot use a Custom Engine")
        if str(engine.get("name", "")).strip() not in {
            "codex", "claude_code", "claude_sdk", "qodercli", "qwen_code", "ad-agent-runtime",
        }:
            raise SkillPackageError(
                "managed Skill evaluation must use a built-in skill-up Agent Engine"
            )
        engine_kwargs = engine.get("kwargs") or {}
        if not isinstance(engine_kwargs, Mapping):
            raise SkillPackageError("managed Skill evaluation engine.kwargs must be an object")
        if str(engine.get("name", "")).strip() == "claude_sdk":
            allowed_kwargs = {
                "max_tokens", "file_paths", "max_skill_context_chars",
                "max_tool_context_chars", "max_file_context_chars",
            }
            for key in engine_kwargs:
                key_text = str(key)
                if key_text not in allowed_kwargs:
                    raise SkillPackageError(
                        f"managed Skill evaluation does not support engine.kwargs.{key_text}"
                    )
        environment = config.get("environment") or {}
        if not isinstance(environment, dict) or environment.get("type", "none") != "none":
            raise SkillPackageError("managed Skill evaluation only supports environment.type=none")
        mcp = config.get("mcp") or {}
        if not isinstance(mcp, dict) or mcp.get("servers"):
            raise SkillPackageError("managed Skill evaluation cannot configure MCP servers")
        skills = config.get("skills") or []
        if not isinstance(skills, list) or not skills:
            raise SkillPackageError("evals/eval.yaml must install the Skill via skills")
        for item in skills:
            if not isinstance(item, dict) or item.get("source") != "local_path":
                raise SkillPackageError("managed Skill evaluation only supports local_path Skills")
            path = item.get("path", ".")
            if not isinstance(path, str) or not path.strip():
                raise SkillPackageError("Skill eval local_path must be a relative path")
            if path.strip() not in {".", "./"}:
                _safe_path(path)
        cases = config.get("cases") or {}
        case_files = cases.get("files") if isinstance(cases, dict) else None
        if not isinstance(case_files, list) or not case_files:
            raise SkillPackageError("evals/eval.yaml must declare cases.files")
        for raw_case in case_files:
            case_path = _safe_path(raw_case)
            if case_path not in files:
                # skill-up examples resolve paths from the package root; also
                # accept a path relative to evals/ for editor convenience.
                relative = str(PurePosixPath("evals") / case_path)
                if relative not in files:
                    raise SkillPackageError(f"evaluation case is not in the Skill package: {raw_case}")

        def reject_scripts(node: Any, location: str = "config") -> None:
            if isinstance(node, dict):
                if node.get("type") == "script" or "script_path" in node:
                    raise SkillPackageError(
                        f"managed Skill evaluation cannot execute judge scripts ({location})"
                    )
                for key, value in node.items():
                    reject_scripts(value, f"{location}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    reject_scripts(value, f"{location}[{index}]")

        reject_scripts(config.get("judge"), "judge")
        for raw_case in case_files:
            case_path = _safe_path(raw_case)
            case_bytes = files.get(case_path) or files.get(str(PurePosixPath("evals") / case_path))
            if case_bytes is None:
                continue
            try:
                case_config = yaml.safe_load(case_bytes.decode("utf-8")) or {}
            except (UnicodeDecodeError, yaml.YAMLError) as exc:
                raise SkillPackageError(f"invalid evaluation case {raw_case}: {exc}") from exc
            reject_scripts(case_config.get("judge"), f"case:{raw_case}.judge")
        return eval_path, config

    def start_evaluation(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> dict[str, Any]:
        record = self.store.get_skill_version(tenant_id, skill_name, version)
        if not record:
            raise KeyError("Skill version not found")
        self._validate_eval_config(record)
        if not _EVAL_CAPACITY.acquire(blocking=False):
            raise SkillPackageError(
                "skill-up evaluation queue is full; retry after an active run completes"
            )
        run_id = uuid.uuid4().hex
        try:
            claim = getattr(self.store, "claim_skill_evaluation", None)
            if not callable(claim):
                # A backend that has not adopted the single-flight contract
                # must fail closed rather than silently reintroduce duplicate
                # evaluation runs.
                raise SkillPackageError(
                    "persistence backend does not support atomic Skill evaluation claims"
                )
            run = claim(run_id, str(record["version_id"]), str(tenant_id))
            if not run:
                raise SkillPackageError(
                    "this Skill version already has an evaluation in progress"
                )
            future = _EVAL_EXECUTOR.submit(
                self._execute_evaluation, run_id, record
            )
            future.add_done_callback(lambda _future: _EVAL_CAPACITY.release())
        except Exception:
            _EVAL_CAPACITY.release()
            raise
        return run

    def get_evaluation(self, tenant_id: str, run_id: str) -> Optional[dict]:
        return self.store.get_skill_evaluation(run_id, tenant_id)

    def _execute_evaluation(self, run_id: str, record: Mapping[str, Any]) -> None:
        version_id = str(record["version_id"])
        self.store.update_skill_evaluation_run(run_id, "running")
        self.store.set_skill_evaluation(version_id, "running", run_id=run_id)
        report: dict[str, Any] = {"run_id": run_id}
        try:
            eval_path, _config = self._validate_eval_config(record)
            package_root = self._materialize(record)
            actual_eval = package_root / eval_path
            report_root = self.root / ".evaluations" / run_id
            report_root.mkdir(parents=True, exist_ok=True)
            command = os.environ.get("SKILL_UP_BIN", "skill-up")
            command_parts = [command] if os.path.sep in command else [shutil.which(command) or command]
            timeout = max(1, min(int(os.environ.get("AD_AGENT_SKILL_UP_TIMEOUT", "900")), 1800))
            evaluation_env = self._evaluation_environment()
            evaluation_env["AD_AGENT_REPO_ROOT"] = str(
                Path(__file__).resolve().parents[2]
            )
            evaluation_env["AD_AGENT_SKILLS_ROOT"] = str(package_root)
            eval_config = _config
            generated_eval: Optional[Path] = None
            engine_name = str((_config.get("engine") or {}).get("name", ""))
            if engine_name in {"ad-agent-runtime", "claude_sdk"}:
                # The platform owns these adapters. User packages may provide
                # cases and judges, but never the command that runs them.
                adapter_name = (
                    "claude_sdk_engine.py" if engine_name == "claude_sdk"
                    else "skill_up_engine.py"
                )
                adapter = Path(__file__).resolve().parent / "evals" / adapter_name
                generated_eval = package_root / f".skill-up-eval-{run_id}.yaml"
                eval_config = dict(_config)
                original_engine = _config.get("engine") or {}
                eval_config["engine"] = {
                    "name": engine_name,
                    **({"model": original_engine["model"]} if "model" in original_engine else {}),
                    "custom": {
                        "transport": "local",
                        "response_format": "session_result",
                        "timeout_seconds": timeout,
                        "local": {
                            "command": "python3",
                            "args": [
                                str(adapter), "--input", "${input_file}",
                                "--output", "${output_file}",
                            ],
                            "cwd": "${workspace}",
                            "input_file": "inputs/ad-agent-session.json",
                            "output_file": "outputs/ad-agent-session-result.json",
                        },
                    },
                }
                original_kwargs = original_engine.get("kwargs") or {}
                if original_kwargs and engine_name == "claude_sdk":
                    # skill-up's Custom Engine contract uses string kwargs;
                    # normalize YAML scalar values before generating the
                    # platform-owned config (the adapter parses bounded ints).
                    eval_config["engine"]["custom"]["kwargs"] = {
                        str(key): str(value) for key, value in original_kwargs.items()
                    }
                generated_eval.write_text(
                    yaml.safe_dump(eval_config, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                actual_eval = generated_eval
            validation = subprocess.run(
                command_parts + ["validate", str(actual_eval)],
                cwd=str(package_root), capture_output=True, text=True,
                timeout=timeout, check=False, env=evaluation_env,
            )
            report["validate_exit_code"] = validation.returncode
            report["validate_stdout"] = validation.stdout[-12000:]
            report["validate_stderr"] = validation.stderr[-12000:]
            if validation.returncode != 0:
                status = "failed"
                error = "skill-up eval configuration validation failed"
            else:
                run = subprocess.run(
                    command_parts + [
                        "run", str(actual_eval),
                        "--output-dir", str(report_root), "--no-delete",
                    ],
                    cwd=str(package_root), capture_output=True, text=True,
                    timeout=timeout, check=False, env=evaluation_env,
                )
                report["run_exit_code"] = run.returncode
                report["stdout"] = run.stdout[-16000:]
                report["stderr"] = run.stderr[-16000:]
                result_files = [
                    str(path.relative_to(report_root))
                    for path in report_root.rglob("result.json")
                    if path.is_file()
                ]
                report["result_files"] = result_files[:20]
                status = "passed" if run.returncode == 0 else "failed"
                error = None if status == "passed" else "skill-up evaluation failed"
            # Provider credentials must never be retained in an evaluation
            # report, even if an Agent prints them accidentally.
            from .runtime.runtime import AgentRuntime
            safe_report = AgentRuntime._redact_for_persistence(report)
            self.store.update_skill_evaluation_run(run_id, status, safe_report, error)
            self.store.set_skill_evaluation(version_id, status, run_id, safe_report)
            if generated_eval is not None:
                generated_eval.unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            error = "skill-up evaluation timed out"
            self.store.update_skill_evaluation_run(run_id, "error", report, error)
            self.store.set_skill_evaluation(version_id, "error", run_id, report)
        except Exception as exc:
            error = f"skill-up evaluation failed to start: {type(exc).__name__}: {exc}"
            self.store.update_skill_evaluation_run(run_id, "error", report, error)
            self.store.set_skill_evaluation(version_id, "error", run_id, report)

    @staticmethod
    def _evaluation_environment() -> dict[str, str]:
        """Remove advertising credentials from the skill-up subprocess.

        The selected model credential may be needed by a built-in Engine, but
        provider credentials and service API keys are never part of a Skill
        evaluation environment.  This is defense in depth in addition to
        Runtime payload redaction.
        """
        environment = dict(os.environ)
        secret_markers = (
            "ACCESS_TOKEN", "REFRESH_TOKEN", "DEVELOPER_TOKEN", "CLIENT_SECRET",
            "APP_SECRET", "PRIVATE_KEY", "SERVICE_ACCOUNT", "BC_ID", "PARTNER_ID",
            "PERTER_ID", "MCC", "AD_AGENT_API_KEY", "AD_PLATFORM_CREDENTIAL",
        )
        provider_prefixes = ("META_", "TIKTOK_", "GOOGLE_ADS_", "DV360_")
        for key in list(environment):
            upper = key.upper()
            if any(marker in upper for marker in secret_markers) or any(
                upper.startswith(prefix) for prefix in provider_prefixes
            ):
                environment.pop(key, None)
        return environment
