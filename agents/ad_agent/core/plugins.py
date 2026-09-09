"""Provider-neutral plugin contracts for the ad-agent Harness.

This module deliberately owns plugin *lifecycle and metadata*, not business
routing or provider execution.  A plugin contribution still has to enter the
existing ToolRegistry/Runtime gates before it can do work.

There are two important classes of package:

* trusted source plugins, which may contribute executable Capability/Feature
  code after deployment review; and
* managed Skill packages, which are advisory context and are never executable.

The registry is intentionally small and dependency-free.  It is the first
common seam for the later Plugin SDK; existing convention-based discovery can
adopt it without changing the Runtime's provider-neutral behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import logging
import re
import threading
from typing import Any, Iterable, Mapping, Optional, Protocol

from .security import is_sensitive_field


logger = logging.getLogger(__name__)


PLUGIN_API_VERSION = "1"
_PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]{1,127}$")
_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_VERSION_INPUT_RE = re.compile(
    r"^(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?"
    r"((?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)
class PluginKind(str, Enum):
    """Supported extension points of the Agent Harness."""

    SKILL = "skill"
    CAPABILITY = "capability"
    TOOL_PROVIDER = "tool_provider"
    FEATURE = "feature"
    POLICY = "policy"
    RENDERER = "renderer"
    EVALUATOR = "evaluator"
    MEMORY = "memory"


class PluginState(str, Enum):
    """Observable lifecycle state for an installed plugin contribution."""

    DISCOVERED = "discovered"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


def _normalise_version(value: Any) -> str:
    """Validate and canonicalize a plugin version as complete semver.

    Manifests historically used ``1``/``1.2`` shorthand. Accepting that
    input and storing ``1.0.0``/``1.2.0`` preserves package compatibility while
    keeping the immutable PluginManifest contract in full MAJOR.MINOR.PATCH
    form.
    """
    raw = str(value or "").strip()
    if _VERSION_RE.fullmatch(raw):
        return raw
    match = _VERSION_INPUT_RE.fullmatch(raw)
    if not match:
        raise ValueError(
            f"invalid plugin version: {value!r}; expected MAJOR.MINOR.PATCH"
        )
    major, minor, patch, suffix = match.groups()
    normalized = f"{major}.{minor or 0}.{patch or 0}{suffix or ''}"
    if not _VERSION_RE.fullmatch(normalized):
        raise ValueError(
            f"invalid plugin version: {value!r}; expected MAJOR.MINOR.PATCH"
        )
    return normalized


def normalize_plugin_version(value: Any) -> str:
    """Public validator shared by Skill and Plugin package loaders."""
    return _normalise_version(value)


def _constraint_version_tuple(value: Any) -> tuple[int, int, int]:
    """Parse a semver range base without weakening manifest version rules."""
    raw = str(value or "").strip()
    if _VERSION_RE.fullmatch(raw):
        return _version_tuple(raw)
    match = re.fullmatch(r"(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?", raw)
    if not match:
        raise ValueError(f"invalid plugin dependency version: {value!r}")
    return tuple(int(part or 0) for part in match.groups())


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"invalid plugin version: {value!r}")
    return tuple(int(part) for part in match.groups())


def _validate_metadata(value: Any, path: str = "metadata") -> None:
    """Reject credential-shaped manifest metadata before it is persisted."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            if is_sensitive_field(key):
                raise ValueError(f"Plugin {path} contains protected field {key!r}")
            _validate_metadata(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_metadata(child, f"{path}[{index}]")


def _satisfies(version: str, constraint: str) -> bool:
    """Evaluate the small, deterministic constraint subset used by plugins."""

    constraint = str(constraint or "*").strip()
    if constraint in {"", "*"}:
        return True
    actual = _version_tuple(version)
    if constraint.startswith("^"):
        base = _constraint_version_tuple(constraint[1:])
        return actual >= base and actual[0] == base[0]
    if constraint.startswith("~"):
        base = _constraint_version_tuple(constraint[1:])
        return actual >= base and actual[:2] == base[:2]
    for operator in (">=", "<=", ">", "<", "="):
        if constraint.startswith(operator):
            expected = _constraint_version_tuple(constraint[len(operator):])
            return {
                ">=": actual >= expected,
                "<=": actual <= expected,
                ">": actual > expected,
                "<": actual < expected,
                "=": actual == expected,
            }[operator]
    # A bare major/minor is a convenient compatibility constraint.
    parts = constraint.split(".")
    if all(part.isdigit() for part in parts) and 1 <= len(parts) <= 3:
        expected = tuple(int(part) for part in parts)
        return actual[:len(expected)] == expected
    raise ValueError(f"unsupported plugin dependency constraint: {constraint!r}")


def plugin_version_satisfies(version: str, constraint: str) -> bool:
    """Public dependency check shared by in-process and persisted plugins."""
    return _satisfies(str(version), str(constraint))


@dataclass(frozen=True)
class PluginManifest:
    """Versioned, auditable declaration for one Harness extension.

    ``executable`` is an explicit security declaration.  Managed/user Skill
    packages must remain ``executable=False``; only trusted source packages
    can contribute executable objects, and those objects still pass the
    Runtime's normal authorization and Tool gates.
    """

    plugin_id: str
    version: str
    kinds: tuple[str, ...] = (PluginKind.SKILL.value,)
    api_version: str = PLUGIN_API_VERSION
    display_name: str = ""
    description: str = ""
    source: str = "builtin"
    trusted: bool = False
    executable: bool = False
    entrypoint: Optional[str] = None
    dependencies: Mapping[str, str] = field(default_factory=dict)
    permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        plugin_id = str(self.plugin_id or "").strip().lower()
        if not _PLUGIN_ID_RE.fullmatch(plugin_id):
            raise ValueError(f"invalid plugin_id: {self.plugin_id!r}")
        object.__setattr__(self, "plugin_id", plugin_id)
        object.__setattr__(self, "version", _normalise_version(self.version))
        api_version = str(self.api_version or "").strip()
        if not api_version or api_version != PLUGIN_API_VERSION:
            raise ValueError(
                f"unsupported plugin API version {api_version!r}; expected {PLUGIN_API_VERSION}"
            )
        object.__setattr__(self, "api_version", api_version)
        kinds = tuple(dict.fromkeys(str(kind).strip().lower() for kind in self.kinds if str(kind).strip()))
        valid_kinds = {kind.value for kind in PluginKind}
        unknown = sorted(set(kinds) - valid_kinds)
        if not kinds or unknown:
            raise ValueError(f"invalid plugin kinds: {unknown or 'empty'}")
        object.__setattr__(self, "kinds", kinds)
        source = str(self.source or "builtin").strip().lower()
        if source not in {"builtin", "trusted", "managed", "external"}:
            raise ValueError(f"unsupported plugin source: {source!r}")
        if bool(self.executable) and not bool(self.trusted):
            raise ValueError("executable plugins must be trusted")
        if source == "managed" and bool(self.executable):
            raise ValueError("managed Skill packages cannot be executable plugins")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "trusted", bool(self.trusted))
        object.__setattr__(self, "executable", bool(self.executable))
        if self.entrypoint is not None:
            entrypoint = str(self.entrypoint).strip()
            if not entrypoint or ".." in entrypoint or entrypoint.startswith(("/", "\\")):
                raise ValueError("plugin entrypoint must be a safe relative identifier")
            object.__setattr__(self, "entrypoint", entrypoint)
        dependencies = {
            str(name).strip().lower(): str(constraint).strip()
            for name, constraint in dict(self.dependencies or {}).items()
        }
        if any(not _PLUGIN_ID_RE.fullmatch(name) for name in dependencies):
            raise ValueError("plugin dependency IDs must be valid plugin IDs")
        for constraint in dependencies.values():
            _satisfies(self.version, constraint) if constraint in {"*", ""} else _validate_constraint(constraint)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "permissions", tuple(dict.fromkeys(str(item).strip() for item in self.permissions if str(item).strip())))
        metadata = dict(self.metadata or {})
        _validate_metadata(metadata)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "kinds": list(self.kinds),
            "api_version": self.api_version,
            "display_name": self.display_name,
            "description": self.description,
            "source": self.source,
            "trusted": self.trusted,
            "executable": self.executable,
            "entrypoint": self.entrypoint,
            "dependencies": dict(self.dependencies),
            "permissions": list(self.permissions),
            "metadata": dict(self.metadata),
        }


def _validate_constraint(constraint: str) -> None:
    """Validate a dependency constraint without needing a resolver."""

    candidates = [constraint]
    if constraint.startswith(("^", "~")):
        candidates = [constraint[1:]]
    else:
        for operator in (">=", "<=", ">", "<", "="):
            if constraint.startswith(operator):
                candidates = [constraint[len(operator):]]
                break
    if not candidates[0].strip():
        raise ValueError(f"unsupported plugin dependency constraint: {constraint!r}")
    parts = candidates[0].split(".")
    if not (all(part.isdigit() for part in parts) and 1 <= len(parts) <= 3):
        raise ValueError(f"unsupported plugin dependency constraint: {constraint!r}")


class PluginLifecycle(Protocol):
    """Optional hooks implemented by trusted source plugins."""

    def load(self, registry: "PluginRegistry") -> None: ...

    def activate(self, registry: "PluginRegistry") -> None: ...

    def deactivate(self, registry: "PluginRegistry") -> None: ...

    def unload(self, registry: "PluginRegistry") -> None: ...


@dataclass
class PluginRecord:
    manifest: PluginManifest
    contribution: Any = None
    lifecycle: Optional[PluginLifecycle] = None
    state: PluginState = PluginState.DISCOVERED
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "state": self.state.value,
            "error": self.error,
            "has_contribution": self.contribution is not None,
        }


class PluginRegistry:
    """Thread-safe registry for trusted and advisory plugin contributions.

    Registration never imports a package and never performs provider I/O.
    Lifecycle hooks run only for trusted executable contributions.  Runtime
    remains the owner of Tool execution, so this registry is not a bypass for
    account, permission, dry-run, confirmation, or audit gates.
    """

    def __init__(self, api_version: str = PLUGIN_API_VERSION):
        if str(api_version) != PLUGIN_API_VERSION:
            raise ValueError(f"unsupported PluginRegistry API version: {api_version!r}")
        self.api_version = PLUGIN_API_VERSION
        self._records: dict[str, PluginRecord] = {}
        self._lock = threading.RLock()

    def register(
        self,
        manifest: PluginManifest,
        contribution: Any = None,
        lifecycle: Optional[PluginLifecycle] = None,
        *,
        replace: bool = False,
    ) -> PluginRecord:
        if not isinstance(manifest, PluginManifest):
            raise TypeError("plugin manifest must be a PluginManifest")
        if lifecycle is not None and not manifest.executable:
            raise ValueError("lifecycle hooks require an executable trusted plugin")
        with self._lock:
            current = self._records.get(manifest.plugin_id)
            if current is not None and not replace:
                raise ValueError(f"plugin '{manifest.plugin_id}' is already registered")
            if current is not None and current.state == PluginState.ACTIVE:
                self._deactivate_locked(current)
            record = PluginRecord(manifest, contribution, lifecycle)
            self._records[manifest.plugin_id] = record
            return record

    def get(self, plugin_id: str) -> PluginRecord:
        with self._lock:
            try:
                return self._records[str(plugin_id).strip().lower()]
            except KeyError as exc:
                raise KeyError(f"plugin '{plugin_id}' is not registered") from exc

    def list(self, *, kind: Optional[str] = None, state: Optional[PluginState] = None) -> list[PluginRecord]:
        with self._lock:
            records = list(self._records.values())
            if kind:
                wanted = str(kind).strip().lower()
                records = [record for record in records if wanted in record.manifest.kinds]
            if state:
                wanted_state = PluginState(state)
                records = [record for record in records if record.state == wanted_state]
            return list(sorted(records, key=lambda record: record.manifest.plugin_id))

    def load(self, plugin_id: str) -> PluginRecord:
        with self._lock:
            return self._load_locked(str(plugin_id).strip().lower(), set())

    def activate(self, plugin_id: str) -> PluginRecord:
        with self._lock:
            return self._activate_locked(str(plugin_id).strip().lower(), set())

    def deactivate(self, plugin_id: str) -> PluginRecord:
        with self._lock:
            record = self.get(plugin_id)
            self._ensure_no_active_dependents(record.manifest.plugin_id)
            self._deactivate_locked(record)
            return record

    def unregister(self, plugin_id: str) -> bool:
        with self._lock:
            key = str(plugin_id).strip().lower()
            record = self._records.get(key)
            if record is None:
                return False
            self._ensure_no_active_dependents(key)
            self._deactivate_locked(record)
            if record.lifecycle is not None:
                hook = getattr(record.lifecycle, "unload", None)
                if callable(hook):
                    hook(self)
            self._records.pop(key, None)
            return True

    def upgrade(
        self,
        manifest: PluginManifest,
        contribution: Any = None,
        lifecycle: Optional[PluginLifecycle] = None,
    ) -> PluginRecord:
        """Atomically replace a trusted contribution with rollback on failure.

        The new object is activated before the old record is discarded. If
        loading or activation fails, the previous record is restored and
        reactivated when necessary. This is an in-process lifecycle contract;
        package import and sandbox policy remain deployment-host concerns.
        """
        if not isinstance(manifest, PluginManifest):
            raise TypeError("plugin manifest must be a PluginManifest")
        if not manifest.executable or not manifest.trusted:
            raise ValueError("only trusted executable plugins can be upgraded")
        if lifecycle is None:
            raise ValueError("trusted plugin upgrades require a lifecycle object")
        with self._lock:
            key = manifest.plugin_id
            previous = self._records.get(key)
            previous_state = previous.state if previous else None
            if previous is not None:
                self._ensure_no_active_dependents(key)
                if previous.state == PluginState.ACTIVE:
                    self._deactivate_locked(previous)
            replacement = PluginRecord(manifest, contribution, lifecycle)
            self._records[key] = replacement
            try:
                return self._activate_locked(key, set())
            except Exception:
                # Remove any partially loaded replacement before restoring the
                # old opaque contribution. A failed cleanup is recorded but
                # never hides the original upgrade failure.
                try:
                    self._deactivate_locked(replacement)
                    unload = getattr(lifecycle, "unload", None)
                    if callable(unload):
                        unload(self)
                except Exception:
                    logger.exception("failed to clean up rejected plugin upgrade %s", key)
                if previous is not None:
                    self._records[key] = previous
                    if previous_state == PluginState.ACTIVE:
                        self._activate_locked(key, set())
                else:
                    self._records.pop(key, None)
                raise

    def snapshot(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.list()]

    def _ensure_no_active_dependents(self, plugin_id: str) -> None:
        dependents = [
            record.manifest.plugin_id
            for record in self._records.values()
            if record.state == PluginState.ACTIVE
            and plugin_id in record.manifest.dependencies
        ]
        if dependents:
            raise ValueError(
                f"plugin '{plugin_id}' has active dependents: {', '.join(sorted(dependents))}"
            )

    def _load_locked(self, key: str, visiting: set[str]) -> PluginRecord:
        record = self.get(key)
        if record.state in {PluginState.LOADED, PluginState.ACTIVE}:
            return record
        if key in visiting:
            raise ValueError(f"plugin dependency cycle detected at '{key}'")
        visiting.add(key)
        try:
            for dependency, constraint in record.manifest.dependencies.items():
                dependency_record = self._load_locked(dependency, visiting)
                if not _satisfies(dependency_record.manifest.version, constraint):
                    raise ValueError(
                        f"plugin '{key}' requires '{dependency}' {constraint}, "
                        f"found {dependency_record.manifest.version}"
                    )
            if record.lifecycle is not None:
                hook = getattr(record.lifecycle, "load", None)
                if callable(hook):
                    hook(self)
            record.state = PluginState.LOADED
            record.error = None
            return record
        except Exception as exc:
            record.state = PluginState.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            visiting.remove(key)

    def _activate_locked(self, key: str, visiting: set[str]) -> PluginRecord:
        if key in visiting:
            raise ValueError(f"plugin dependency cycle detected at '{key}'")
        record = self._load_locked(key, set())
        if record.state == PluginState.ACTIVE:
            return record
        visiting.add(key)
        try:
            # Activation is dependency-ordered.  A plugin never observes an
            # inactive dependency after this method returns successfully.
            for dependency in record.manifest.dependencies:
                self._activate_locked(dependency, visiting)
            if not record.manifest.executable and record.lifecycle is not None:
                raise ValueError(
                    f"advisory plugin '{record.manifest.plugin_id}' has lifecycle hooks"
                )
            if record.lifecycle is not None:
                hook = getattr(record.lifecycle, "activate", None)
                if callable(hook):
                    hook(self)
            record.state = PluginState.ACTIVE
            record.error = None
            return record
        except Exception as exc:
            record.state = PluginState.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            visiting.remove(key)

    def _deactivate_locked(self, record: PluginRecord) -> None:
        if record.state != PluginState.ACTIVE:
            return
        try:
            if record.lifecycle is not None:
                hook = getattr(record.lifecycle, "deactivate", None)
                if callable(hook):
                    hook(self)
            record.state = PluginState.INACTIVE
            record.error = None
        except Exception as exc:
            record.state = PluginState.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            raise


class PluginLoader:
    """Controlled Manifest loader for the PluginRegistry.

    The loader parses declarations only. It deliberately does not import an
    ``entrypoint`` or execute files from a package. A deployment host may pass
    an already-reviewed in-process contribution; managed/user packages must
    use the non-executable path.
    """

    def __init__(
        self,
        registry: PluginRegistry,
        *,
        allow_trusted_source: bool = False,
        approved_permissions: Optional[Iterable[str]] = None,
    ):
        self.registry = registry
        self.allow_trusted_source = bool(allow_trusted_source)
        # Permission approval is deployment-owned.  An absent approval set is
        # fail-closed for manifests that request permissions; it does not
        # affect the existing permission checks on individual Tools.
        self.approved_permissions = frozenset(
            str(permission).strip()
            for permission in (approved_permissions or ())
            if str(permission).strip()
        )

    def install(
        self,
        manifest: PluginManifest,
        contribution: Any = None,
        lifecycle: Optional[PluginLifecycle] = None,
        *,
        replace: bool = False,
        activate: bool = True,
    ) -> PluginRecord:
        if not isinstance(manifest, PluginManifest):
            raise TypeError("plugin manifest must be a PluginManifest")
        self._validate_deployment(manifest)
        record = self.registry.register(
            manifest,
            contribution=contribution,
            lifecycle=lifecycle,
            replace=replace,
        )
        if activate:
            return self.registry.activate(manifest.plugin_id)
        return record

    def upgrade(
        self,
        manifest: PluginManifest,
        contribution: Any,
        lifecycle: PluginLifecycle,
    ) -> PluginRecord:
        """Upgrade a reviewed trusted contribution with rollback semantics."""
        if not isinstance(manifest, PluginManifest):
            raise TypeError("plugin manifest must be a PluginManifest")
        self._validate_deployment(manifest)
        return self.registry.upgrade(manifest, contribution, lifecycle)

    def _validate_deployment(self, manifest: PluginManifest) -> None:
        if manifest.executable and not self.allow_trusted_source:
            raise PermissionError(
                "executable plugins require a trusted deployment loader"
            )
        requested_permissions = set(manifest.permissions)
        if requested_permissions - self.approved_permissions:
            missing = ", ".join(sorted(requested_permissions - self.approved_permissions))
            raise PermissionError(
                f"Plugin permissions require deployment approval: {missing}"
            )

    def load_manifest(
        self,
        payload: Mapping[str, Any],
        contribution: Any = None,
        lifecycle: Optional[PluginLifecycle] = None,
        *,
        replace: bool = False,
        activate: bool = True,
    ) -> PluginRecord:
        """Build and install a manifest from a JSON-compatible mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("plugin manifest payload must be an object")
        fields = {
            key: payload[key]
            for key in (
                "plugin_id", "version", "kinds", "api_version", "display_name",
                "description", "source", "trusted", "executable", "entrypoint",
                "dependencies", "permissions", "metadata",
            )
            if key in payload
        }
        return self.install(
            PluginManifest(**fields),
            contribution=contribution,
            lifecycle=lifecycle,
            replace=replace,
            activate=activate,
        )

    def load_package(
        self,
        directory: str,
        *,
        signing_key: Optional[str] = None,
        require_signature: bool = False,
        contribution: Any = None,
        lifecycle: Optional[PluginLifecycle] = None,
        replace: bool = False,
        activate: bool = True,
    ) -> PluginRecord:
        """Validate a package directory, then install only its declaration.

        This method never imports the package entrypoint. Executable code must
        be bound separately by a trusted deployment host after review.
        """

        from .plugin_package import validate_plugin_directory

        package = validate_plugin_directory(
            directory,
            signing_key=signing_key,
            require_signature=require_signature,
        )
        if package.manifest.executable and contribution is None:
            raise ValueError(
                "an executable Plugin package requires a trusted host contribution"
            )
        return self.install(
            package.manifest,
            contribution=contribution,
            lifecycle=lifecycle,
            replace=replace,
            activate=activate,
        )


def manifest_for_builtin(
    plugin_id: str,
    version: str = "1.0.0",
    *,
    kinds: tuple[str, ...] | list[str],
    description: str = "",
    metadata: Optional[Mapping[str, Any]] = None,
) -> PluginManifest:
    """Create a trusted manifest for already-reviewed in-process extensions."""

    return PluginManifest(
        plugin_id=plugin_id,
        version=version,
        kinds=tuple(kinds),
        source="builtin",
        trusted=True,
        executable=True,
        description=description,
        metadata=dict(metadata or {}),
    )


def manifest_for_managed_skill(
    tenant_id: str,
    skill_name: str,
    version: str,
    *,
    description: str = "",
) -> PluginManifest:
    """Create a non-executable, tenant-scoped manifest for managed context."""

    tenant = str(tenant_id or "default").strip().lower()
    name = str(skill_name or "").strip().lower()
    return PluginManifest(
        plugin_id=f"managed:{managed_tenant_key(tenant)}:skill:{name}",
        version=version,
        kinds=(PluginKind.SKILL.value,),
        source="managed",
        trusted=False,
        executable=False,
        description=description,
        metadata={"tenant_id": tenant, "skill_name": name, "advisory_only": True},
    )


def managed_tenant_key(tenant_id: str) -> str:
    """Return a collision-resistant safe ID component for a tenant."""

    tenant = str(tenant_id or "default").strip().lower()
    return hashlib.sha256(tenant.encode("utf-8")).hexdigest()[:16]
