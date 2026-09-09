"""Read-only deployment report for Plugin package integrity and trust."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .plugin_package import PluginPackageError, validate_plugin_directory


def build_plugin_preflight(
    directory: str | Path,
    *,
    signing_key: Optional[str] = None,
    require_signature: bool = False,
) -> dict:
    """Validate a package without importing or executing any package file."""
    try:
        package = validate_plugin_directory(
            directory,
            signing_key=signing_key,
            require_signature=require_signature,
        )
    except (PluginPackageError, OSError) as exc:
        message = str(exc)
        if require_signature and "signature" not in message.lower():
            message = "signature verification required: " + message
        return {
            "format_version": 1,
            "status": "blocked",
            "package": str(Path(directory).resolve()),
            "validated": False,
            "signature_required": bool(require_signature),
            "signature_verified": False,
            "executable": None,
            "external_calls": 0,
            "network_called": False,
            "issues": [f"{type(exc).__name__}: {message}"],
        }
    manifest = package.manifest
    issues: list[str] = []
    if manifest.executable and not manifest.trusted:
        issues.append("executable Plugin must be trusted")
    if manifest.executable and require_signature and not package.signature_verified:
        issues.append("executable Plugin requires a verified signature")
    return {
        "format_version": 1,
        "status": "blocked" if issues else "ready_for_reviewed_deployment",
        "package": str(Path(directory).resolve()),
        "validated": True,
        "plugin_id": manifest.plugin_id,
        "version": manifest.version,
        "source": manifest.source,
        "trusted": manifest.trusted,
        "executable": manifest.executable,
        "signature_required": bool(require_signature),
        "signature_verified": package.signature_verified,
        "package_digest": package.package_digest,
        "external_calls": 0,
        "network_called": False,
        "issues": issues,
    }
