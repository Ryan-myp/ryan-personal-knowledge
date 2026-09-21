"""Safe package-level manifest and integrity validation for Plugins.

This module validates a package directory without importing or executing any
file.  It is intentionally usable for both trusted source packages and
managed Skill packages.  Whether a validated package may contribute executable
objects remains a deployment/Loader decision.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

from .plugins import PluginManifest


PLUGIN_MANIFEST_FILENAME = "plugin.manifest.json"
_MAX_FILES = 512
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_PACKAGE_BYTES = 16 * 1024 * 1024
_SHA256_RE = r"^[0-9a-f]{64}$"


class PluginPackageError(ValueError):
    """Raised when a Plugin package is malformed or fails integrity checks."""


def _decode_payload_file(value: Any, path: str) -> bytes:
    """Decode the JSON representation used by the package control plane.

    Package files are data at this boundary.  The helper deliberately only
    decodes UTF-8/base64 content; it never opens, imports, or executes a file.
    """
    import base64

    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    if not isinstance(value, Mapping):
        raise PluginPackageError(f"Plugin file {path} must be text or an encoded object")
    content = value.get("content")
    encoding = str(value.get("encoding", "utf-8")).strip().lower()
    if not isinstance(content, str):
        raise PluginPackageError(f"Plugin file {path}.content must be a string")
    if encoding in {"utf-8", "text"}:
        return content.encode("utf-8")
    if encoding in {"base64", "base64url"}:
        try:
            return base64.b64decode(content, validate=True)
        except (TypeError, ValueError) as exc:
            raise PluginPackageError(f"Plugin file {path} has invalid base64") from exc
    raise PluginPackageError(f"unsupported encoding for Plugin file {path}: {encoding}")


def normalize_plugin_files(raw_files: Mapping[str, Any]) -> dict[str, bytes]:
    """Normalize package files supplied through a JSON management API."""
    if not isinstance(raw_files, Mapping):
        raise PluginPackageError("Plugin package files must be an object")
    if not raw_files or len(raw_files) > _MAX_FILES:
        raise PluginPackageError(f"Plugin package must contain 1..{_MAX_FILES} files")
    normalized: dict[str, bytes] = {}
    total = 0
    for raw_path, raw_value in raw_files.items():
        path = _safe_path(raw_path)
        if path in normalized:
            raise PluginPackageError(f"duplicate Plugin package file: {path}")
        data = _decode_payload_file(raw_value, path)
        if len(data) > _MAX_FILE_BYTES:
            raise PluginPackageError(f"Plugin file {path} exceeds {_MAX_FILE_BYTES} bytes")
        total += len(data)
        if total > _MAX_PACKAGE_BYTES:
            raise PluginPackageError(f"Plugin package exceeds {_MAX_PACKAGE_BYTES} bytes")
        normalized[path] = data
    return dict(sorted(normalized.items()))


@dataclass(frozen=True)
class PluginPackage:
    manifest: PluginManifest
    files: Mapping[str, bytes]
    package_digest: str
    signature_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "files": sorted(self.files),
            "package_digest": self.package_digest,
            "signature_verified": self.signature_verified,
        }


def _safe_path(raw: Any) -> str:
    value = str(raw or "").replace("\\", "/")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or any(not part for part in path.parts)
    ):
        raise PluginPackageError(f"unsafe Plugin package path: {raw!r}")
    return path.as_posix()


def package_digest(files: Mapping[str, bytes]) -> str:
    """Return a deterministic digest over relative names and file contents."""

    digest = hashlib.sha256()
    for raw_path in sorted(files):
        path = _safe_path(raw_path)
        data = files[raw_path]
        if not isinstance(data, bytes):
            raise PluginPackageError(f"Plugin package file {path} is not bytes")
        encoded_path = path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _file_hashes(files: Mapping[str, bytes]) -> dict[str, str]:
    return {
        _safe_path(path): hashlib.sha256(data).hexdigest()
        for path, data in files.items()
    }


def _signed_payload(
    manifest: PluginManifest,
    file_hashes: Mapping[str, str],
    digest: str,
) -> bytes:
    return json.dumps(
        {
            "manifest": manifest.to_dict(),
            "files": dict(sorted(file_hashes.items())),
            "package_digest": digest,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_plugin_manifest(
    manifest: PluginManifest,
    files: Mapping[str, bytes],
    *,
    signing_key: Optional[str] = None,
) -> dict[str, Any]:
    """Build the JSON document written as ``plugin.manifest.json``.

    The manifest file itself is excluded from ``files`` to avoid a recursive
    digest.  The signature covers the normalized Plugin Manifest, every file
    hash, and the package digest.
    """

    normalized_files = {_safe_path(path): data for path, data in files.items()}
    file_hashes = _file_hashes(normalized_files)
    digest = package_digest(normalized_files)
    document: dict[str, Any] = {
        "manifest": manifest.to_dict(),
        "files": file_hashes,
        "package_digest": digest,
        "signature_algorithm": "hmac-sha256" if signing_key else None,
        "signature": None,
    }
    if signing_key:
        document["signature"] = hmac.new(
            str(signing_key).encode("utf-8"),
            _signed_payload(manifest, file_hashes, digest),
            hashlib.sha256,
        ).hexdigest()
    return document


def _verify_declared_integrity(
    document: Mapping[str, Any],
    manifest: PluginManifest,
    files: Mapping[str, bytes],
    *,
    signing_key: Optional[str],
    require_signature: bool,
) -> bool:
    """Verify a supplied package declaration against received file bytes."""
    expected_files = document.get("files")
    if not isinstance(expected_files, Mapping):
        raise PluginPackageError("Plugin manifest.files must be an object")
    normalized_expected = {
        _safe_path(path): str(value).lower()
        for path, value in expected_files.items()
    }
    if set(normalized_expected) != set(files):
        raise PluginPackageError("Plugin manifest file list does not match package contents")
    actual_hashes = _file_hashes(files)
    if any(
        not isinstance(value, str) or not re.fullmatch(_SHA256_RE, value)
        for value in normalized_expected.values()
    ):
        raise PluginPackageError("Plugin manifest contains an invalid file digest")
    if normalized_expected != actual_hashes:
        raise PluginPackageError("Plugin manifest file digest mismatch")
    actual_digest = package_digest(files)
    if str(document.get("package_digest") or "").lower() != actual_digest:
        raise PluginPackageError("Plugin package digest mismatch")

    signature = document.get("signature")
    algorithm = document.get("signature_algorithm")
    if require_signature and not signing_key:
        raise PluginPackageError("signing key is required for Plugin package verification")
    if signature is None and algorithm is None:
        if require_signature:
            raise PluginPackageError("signed Plugin package is required")
        return False
    if algorithm != "hmac-sha256" or not isinstance(signature, str) or not signing_key:
        raise PluginPackageError("Plugin package signature cannot be verified")
    expected_signature = hmac.new(
        str(signing_key).encode("utf-8"),
        _signed_payload(manifest, actual_hashes, actual_digest),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature.lower(), expected_signature):
        raise PluginPackageError("Plugin package signature mismatch")
    return True


def validate_plugin_payload(
    manifest_payload: Mapping[str, Any],
    raw_files: Mapping[str, Any],
    *,
    signing_key: Optional[str] = None,
    require_signature: bool = False,
) -> PluginPackage:
    """Validate a package submitted as a declaration plus file snapshot.

    This is the in-memory equivalent of :func:`validate_plugin_directory` for
    the management API.  It intentionally accepts no executable object and
    derives all hashes from the received bytes, so callers cannot claim an
    arbitrary digest or use the API to bypass package integrity checks.
    """
    if not isinstance(manifest_payload, Mapping):
        raise PluginPackageError("Plugin manifest must be an object")
    document = dict(manifest_payload)
    raw_manifest = document.get("manifest")
    if raw_manifest is None:
        raw_manifest = document
        document = {}
    if not isinstance(raw_manifest, Mapping):
        raise PluginPackageError("Plugin manifest.manifest must be an object")
    try:
        manifest = PluginManifest(**dict(raw_manifest))
    except (TypeError, ValueError) as exc:
        raise PluginPackageError(f"invalid Plugin declaration: {exc}") from exc
    files = normalize_plugin_files(raw_files)
    # Raw management uploads have no caller-supplied integrity envelope and
    # are normalized locally. A standard package document must be verified
    # against the received bytes instead of being regenerated.
    if document:
        signature_verified = _verify_declared_integrity(
            document,
            manifest,
            files,
            signing_key=signing_key,
            require_signature=require_signature,
        )
    else:
        if require_signature:
            raise PluginPackageError("signed Plugin package is required")
        signature_verified = False
    return PluginPackage(manifest, files, package_digest(files), signature_verified)


def validate_plugin_directory(
    directory: str | Path,
    *,
    signing_key: Optional[str] = None,
    require_signature: bool = False,
) -> PluginPackage:
    """Validate a package and its ``plugin.manifest.json`` without execution."""

    root = Path(directory).resolve()
    if not root.is_dir():
        raise PluginPackageError("Plugin package must be a directory")
    manifest_path = root / PLUGIN_MANIFEST_FILENAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PluginPackageError(f"{PLUGIN_MANIFEST_FILENAME} is required")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PluginPackageError(f"invalid Plugin manifest: {exc}") from exc
    if not isinstance(document, dict):
        raise PluginPackageError("Plugin manifest must be an object")
    raw_manifest = document.get("manifest")
    if not isinstance(raw_manifest, Mapping):
        raise PluginPackageError("Plugin manifest.manifest must be an object")
    try:
        manifest = PluginManifest(**dict(raw_manifest))
    except (TypeError, ValueError) as exc:
        raise PluginPackageError(f"invalid Plugin declaration: {exc}") from exc

    files: dict[str, bytes] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path == manifest_path:
            continue
        relative = _safe_path(path.relative_to(root).as_posix())
        if path.is_symlink():
            raise PluginPackageError(f"Plugin package contains non-regular file: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PluginPackageError(f"Plugin package contains non-regular file: {relative}")
        data = path.read_bytes()
        if len(data) > _MAX_FILE_BYTES:
            raise PluginPackageError(f"Plugin file {relative} exceeds {_MAX_FILE_BYTES} bytes")
        total += len(data)
        if total > _MAX_PACKAGE_BYTES:
            raise PluginPackageError(
                f"Plugin package exceeds {_MAX_PACKAGE_BYTES} bytes uncompressed"
            )
        files[relative] = data
    if not files:
        raise PluginPackageError("Plugin package must contain at least one file")
    if len(files) > _MAX_FILES:
        raise PluginPackageError(f"Plugin package contains more than {_MAX_FILES} files")

    signature_verified = _verify_declared_integrity(
        document,
        manifest,
        files,
        signing_key=signing_key,
        require_signature=require_signature,
    )

    return PluginPackage(manifest, files, package_digest(files), signature_verified)
