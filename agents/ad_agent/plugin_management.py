"""Tenant-scoped control plane for immutable Plugin package snapshots.

This service owns package declaration validation and durable release pointers;
it is deliberately not a plugin executor.  A package uploaded by a user can
be inspected, versioned, activated as a deployment candidate, deactivated, or
uninstalled from the control plane.  It cannot import ``entrypoint`` files or
register a Provider Tool.  A trusted deployment host must separately bind an
already-reviewed executable contribution to :class:`PluginLoader`.
"""

from __future__ import annotations

import base64
import io
import os
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

from .core.plugin_package import (
    PluginPackage,
    PluginPackageError,
    normalize_plugin_files,
    package_digest,
    validate_plugin_directory,
    validate_plugin_payload,
)
from .core.plugins import PluginManifest, plugin_version_satisfies


def _encode_files(files: Mapping[str, bytes]) -> dict[str, dict[str, str]]:
    return {
        str(path): {
            "encoding": "base64",
            "content": base64.b64encode(bytes(data)).decode("ascii"),
        }
        for path, data in sorted(files.items())
    }


class PluginPackageManager:
    """CRUD and release management for user-visible Plugin packages."""

    def __init__(self, store: Any):
        self.store = store

    @staticmethod
    def _public(record: Mapping[str, Any], *, include_files: bool = False) -> dict[str, Any]:
        result = {
            key: record.get(key)
            for key in (
                "package_id", "tenant_id", "plugin_id", "version", "manifest",
                "package_digest", "signature_verified", "status", "created_by",
                "created_at", "updated_at", "activated_at", "last_error",
            )
        }
        files = record.get("files") or {}
        result["files"] = files if include_files else sorted(files)
        # Do not expose a persisted file body from list endpoints.  The
        # detail endpoint is explicit because package assets may be large.
        return result

    @staticmethod
    def _validate_user_package(
        manifest_payload: Mapping[str, Any], raw_files: Mapping[str, Any]
    ) -> PluginPackage:
        package = validate_plugin_payload(manifest_payload, raw_files)
        manifest = package.manifest
        # User/API uploads are staging data only.  Trusted executable plugins
        # can be installed by a reviewed deployment host, never by this API.
        if manifest.trusted or manifest.executable:
            raise PermissionError(
                "user Plugin uploads cannot declare trusted or executable contributions"
            )
        if manifest.source == "builtin":
            raise PluginPackageError("builtin Plugin packages are deployment-owned")
        return package

    def create_package(
        self, tenant_id: str, manifest_payload: Mapping[str, Any],
        raw_files: Mapping[str, Any], created_by: str,
    ) -> dict[str, Any]:
        package = self._validate_user_package(manifest_payload, raw_files)
        return self._store_package(tenant_id, package, created_by)

    def create_archive(
        self, tenant_id: str, archive: bytes, created_by: str,
    ) -> dict[str, Any]:
        """Validate and store a standard ``plugin.manifest.json`` ZIP.

        Extraction is confined to a temporary directory after validating every
        ZIP entry.  The directory validator then applies the canonical digest
        and optional signature rules.  No archive file is imported or run.
        """
        if not isinstance(archive, (bytes, bytearray)):
            raise PluginPackageError("Plugin archive must be bytes")
        if len(archive) > 16 * 1024 * 1024:
            raise PluginPackageError("Plugin archive exceeds 16777216 bytes")
        try:
            zfile = zipfile.ZipFile(io.BytesIO(bytes(archive)))
        except (TypeError, zipfile.BadZipFile) as exc:
            raise PluginPackageError("request body must be a valid Plugin ZIP archive") from exc

        entries: dict[str, bytes] = {}
        total_size = 0
        with zfile:
            infos = [info for info in zfile.infolist() if not info.is_dir()]
            if not infos or len(infos) > 512:
                raise PluginPackageError("Plugin archive must contain 1..512 files")
            for info in infos:
                raw_path = str(info.filename or "").replace("\\", "/")
                path = PurePosixPath(raw_path)
                if (
                    not raw_path or path.is_absolute() or ".." in path.parts
                    or "." in path.parts or any(not part for part in path.parts)
                ):
                    raise PluginPackageError(f"unsafe Plugin archive path: {info.filename!r}")
                normalized = path.as_posix()
                mode = (info.external_attr >> 16) & 0o170000
                if stat.S_ISLNK(mode):
                    raise PluginPackageError(
                        f"symbolic links are not allowed in Plugin archives: {normalized}"
                    )
                if info.file_size > 2 * 1024 * 1024:
                    raise PluginPackageError(
                        f"Plugin file {normalized} exceeds 2097152 bytes"
                    )
                total_size += int(info.file_size)
                if total_size > 16 * 1024 * 1024:
                    raise PluginPackageError("Plugin archive exceeds 16777216 bytes uncompressed")
                if normalized in entries:
                    raise PluginPackageError(f"duplicate Plugin archive file: {normalized}")
                entries[normalized] = zfile.read(info)

        if "plugin.manifest.json" not in entries:
            prefixes = {path.split("/", 1)[0] for path in entries if "/" in path}
            if len(prefixes) == 1:
                prefix = next(iter(prefixes)) + "/"
                candidate = {
                    path[len(prefix):]: data
                    for path, data in entries.items()
                    if path.startswith(prefix) and path[len(prefix):]
                }
                if "plugin.manifest.json" in candidate:
                    entries = candidate
        if "plugin.manifest.json" not in entries:
            raise PluginPackageError("Plugin archive requires plugin.manifest.json")

        signing_key = os.environ.get("AD_AGENT_PLUGIN_PACKAGE_SIGNING_KEY")
        require_signature = os.environ.get("AD_AGENT_REQUIRE_PLUGIN_SIGNATURE") == "1"
        with tempfile.TemporaryDirectory(prefix="ad-agent-plugin-validate-") as root:
            directory = Path(root)
            for relative, data in entries.items():
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            package = validate_plugin_directory(
                directory,
                signing_key=signing_key,
                require_signature=require_signature,
            )
        self._validate_user_package(package.manifest.to_dict(), _encode_files(package.files))
        return self._store_package(tenant_id, package, created_by)

    def _store_package(
        self, tenant_id: str, package: PluginPackage, created_by: str,
    ) -> dict[str, Any]:
        manifest = package.manifest
        try:
            record = self.store.create_plugin_package(
                package_id=uuid.uuid4().hex,
                tenant_id=str(tenant_id or "default"),
                plugin_id=manifest.plugin_id,
                version=manifest.version,
                manifest=manifest.to_dict(),
                files=_encode_files(package.files),
                package_digest=package.package_digest,
                signature_verified=package.signature_verified,
                created_by=str(created_by),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper() or "unique" in str(exc):
                raise PluginPackageError(
                    f"Plugin package version already exists: "
                    f"{manifest.plugin_id}@{manifest.version}"
                ) from exc
            raise
        return self._public(record)

    def get_package(
        self, tenant_id: str, plugin_id: str, version: Optional[str] = None,
        *, include_files: bool = False,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_plugin_package(tenant_id, plugin_id, version)
        if not record:
            return None
        self._verify_record(record)
        return self._public(record, include_files=include_files)

    def list_packages(
        self, tenant_id: str, plugin_id: Optional[str] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.store.list_plugin_packages(tenant_id, plugin_id, limit)
        return [self._public(record) for record in records]

    def health(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict[str, Any]]:
        """Return integrity/dependency health without executing package code."""
        record = self.store.get_plugin_package(tenant_id, plugin_id, version)
        if not record:
            return None
        try:
            manifest = self._verify_record(record)
        except PluginPackageError as exc:
            return {
                "package_id": record.get("package_id"),
                "tenant_id": str(tenant_id),
                "plugin_id": str(plugin_id),
                "version": str(version),
                "status": "unhealthy",
                "integrity": "failed",
                "dependencies": [],
                "error": str(exc),
                "execution_probe": "not_run",
            }

        dependencies = []
        dependency_errors = []
        for dependency, constraint in manifest.dependencies.items():
            dependency_record = self.store.get_plugin_package(tenant_id, dependency)
            compatible = False
            actual_version = None
            if dependency_record:
                actual_version = dependency_record.get("version")
                try:
                    compatible = (
                        dependency_record.get("status") == "active"
                        and plugin_version_satisfies(str(actual_version), constraint)
                    )
                except ValueError:
                    compatible = False
            item = {
                "plugin_id": dependency,
                "constraint": constraint,
                "version": actual_version,
                "active": bool(dependency_record and dependency_record.get("status") == "active"),
                "compatible": compatible,
            }
            dependencies.append(item)
            if not compatible:
                dependency_errors.append(dependency)
        healthy = not dependency_errors and record.get("status") != "uninstalled"
        return {
            "package_id": record.get("package_id"),
            "tenant_id": str(tenant_id),
            "plugin_id": manifest.plugin_id,
            "version": manifest.version,
            "status": "healthy" if healthy else "unhealthy",
            "integrity": "verified",
            "dependencies": dependencies,
            "error": (
                f"inactive or incompatible dependencies: {', '.join(dependency_errors)}"
                if dependency_errors else None
            ),
            "execution_probe": "not_run",
            "runtime_loaded": False,
        }

    @staticmethod
    def _verify_record(record: Mapping[str, Any]) -> PluginManifest:
        """Detect tampering before a stored package can be released."""
        try:
            manifest = PluginManifest(**dict(record.get("manifest") or {}))
            files = normalize_plugin_files(record.get("files") or {})
        except (TypeError, ValueError) as exc:
            raise PluginPackageError(f"stored Plugin package is invalid: {exc}") from exc
        actual = package_digest(files)
        if actual != str(record.get("package_digest") or ""):
            raise PluginPackageError("stored Plugin package digest mismatch")
        if manifest.plugin_id != str(record.get("plugin_id") or ""):
            raise PluginPackageError("stored Plugin package ID does not match manifest")
        if manifest.version != str(record.get("version") or ""):
            raise PluginPackageError("stored Plugin package version does not match manifest")
        if manifest.trusted or manifest.executable:
            raise PluginPackageError(
                "user Plugin package cannot be activated as an executable contribution"
            )
        return manifest

    def activate(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_plugin_package(tenant_id, plugin_id, version)
        if not record:
            return None
        manifest = self._verify_record(record)
        # Resolve dependencies inside the same tenant and against the current
        # release pointers.  This is the persisted equivalent of the
        # PluginRegistry dependency gate; a package can never silently become
        # active while one of its declared prerequisites is absent or stale.
        for dependency, constraint in manifest.dependencies.items():
            dependency_record = self.store.get_plugin_package(tenant_id, dependency)
            if not dependency_record or dependency_record.get("status") != "active":
                raise PluginPackageError(
                    f"Plugin dependency '{dependency}' is not active for this tenant"
                )
            try:
                compatible = plugin_version_satisfies(
                    str(dependency_record.get("version")), constraint
                )
            except ValueError as exc:
                raise PluginPackageError(
                    f"invalid dependency constraint for '{dependency}'"
                ) from exc
            if not compatible:
                raise PluginPackageError(
                    f"Plugin dependency '{dependency}' does not satisfy {constraint}"
                )
        activated = self.store.activate_plugin_package(tenant_id, plugin_id, version)
        if not activated:
            return None
        result = self._public(activated)
        result["runtime_loaded"] = False
        result["activation_note"] = (
            "control-plane release only; user package code is never imported or executed"
        )
        return result

    def deactivate(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict[str, Any]]:
        record = self.store.deactivate_plugin_package(tenant_id, plugin_id, version)
        return self._public(record) if record else None

    def uninstall(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict[str, Any]]:
        record = self.store.uninstall_plugin_package(tenant_id, plugin_id, version)
        return self._public(record) if record else None
