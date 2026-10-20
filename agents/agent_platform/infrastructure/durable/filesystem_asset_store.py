"""Identity-scoped durable storage for generated creative assets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from agents.agent_harness.core.security import is_sensitive_field, redact_sensitive_text


_MIB = 1024 * 1024
_MAX_METADATA_BYTES = 32 * 1024
_MAX_ASSETS_PER_USER = 500
_ASSET_ID = re.compile(r"^[0-9a-f]{32}$")
_MIME_SIGNATURES = {
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda content: (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ),
    "video/mp4": lambda content: (
        len(content) >= 12 and content[4:8] == b"ftyp"
    ),
    "video/quicktime": lambda content: (
        len(content) >= 12 and content[4:8] == b"ftyp"
    ),
    "video/webm": lambda content: content.startswith(b"\x1a\x45\xdf\xa3"),
}
_METADATA_FIELDS = frozenset({
    "kind",
    "status",
    "prompt",
    "name",
    "model",
    "model_profile_id",
    "model_endpoint",
    "provider_job_id",
    "model_endpoint_hash",
    "width",
    "height",
    "duration_seconds",
    "aspect_ratio",
    "quality",
    "duration_seconds",
    "frame_rate",
    "error_code",
    "platform_assets",
    "created_at",
    "updated_at",
    "sha256",
    "size",
    "image_size",
    "filename",
    "media_type",
    "asset_id",
})


@dataclass(frozen=True)
class StoredCreativeAsset:
    """Metadata and optional verified media bytes for one creative asset."""

    metadata: dict[str, Any]
    content: bytes | None
    path: Path | None


class FilesystemCreativeAssetStore:
    """Private filesystem store partitioned by trusted tenant and user IDs."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_image_bytes: int = 20 * _MIB,
        max_video_bytes: int = 120 * _MIB,
        max_user_bytes: int = 1024 * _MIB,
        max_assets_per_user: int = _MAX_ASSETS_PER_USER,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_image_bytes = int(max_image_bytes)
        self.max_video_bytes = int(max_video_bytes)
        self.max_user_bytes = int(max_user_bytes)
        self.max_assets_per_user = int(max_assets_per_user)
        self._lock = threading.RLock()
        if min(
            self.max_image_bytes,
            self.max_video_bytes,
            self.max_user_bytes,
            self.max_assets_per_user,
        ) <= 0:
            raise ValueError("creative asset limits must be positive")

    def put(
        self,
        content: bytes,
        *,
        filename: str,
        media_type: str,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate and atomically persist a completed generated asset."""
        media_type = self._validate_content(content, media_type)
        clean_name = self._safe_filename(filename)
        folder = self._scope_path(tenant_id, user_id)
        asset_id = uuid.uuid4().hex
        timestamp = self._now()
        row = self._clean_metadata(metadata)
        row.update({
            "asset_id": asset_id,
            "filename": clean_name,
            "media_type": media_type,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "status": str(row.get("status") or "ready"),
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        with self._lock:
            self._ensure_private_scope(folder)
            self._enforce_quota(folder, len(content), adding_asset=True)
            self._write_asset(folder, asset_id, content, row)
        return dict(row)

    def create_pending(
        self,
        *,
        filename: str,
        media_type: str,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist a bounded provider job record before long polling begins."""
        clean_name = self._safe_filename(filename)
        media_type = self._normalized_media_type(media_type)
        if not media_type.startswith("video/"):
            raise ValueError("pending creative assets must be video")
        row = self._clean_metadata(metadata)
        asset_id = uuid.uuid4().hex
        timestamp = self._now()
        row.update({
            "asset_id": asset_id,
            "filename": clean_name,
            "media_type": media_type,
            "size": 0,
            "sha256": "",
            "status": str(row.get("status") or "processing"),
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        folder = self._scope_path(tenant_id, user_id)
        with self._lock:
            self._ensure_private_scope(folder)
            self._enforce_quota(folder, 0, adding_asset=True)
            self._write_metadata(folder, asset_id, row)
        return dict(row)

    def get(
        self,
        asset_id: str,
        *,
        tenant_id: str,
        user_id: str,
        include_content: bool = True,
    ) -> StoredCreativeAsset:
        """Load a verified asset, hiding cross-principal records as missing."""
        folder, safe_id = self._paths(asset_id, tenant_id, user_id)
        metadata_path = folder / f"{safe_id}.json"
        data_path = folder / f"{safe_id}.bin"
        try:
            if metadata_path.is_symlink():
                raise OSError("invalid metadata path")
            row = json.loads(metadata_path.read_text("utf-8"))
            if not isinstance(row, dict) or row.get("asset_id") != safe_id:
                raise ValueError("invalid metadata record")
            content = None
            verified_path = None
            if row.get("status") == "ready":
                if data_path.is_symlink():
                    raise OSError("invalid content path")
                max_bytes = (
                    self.max_image_bytes
                    if str(row.get("media_type") or "").startswith("image/")
                    else self.max_video_bytes
                )
                actual_size, actual_digest, signature_bytes = self._file_integrity(
                    data_path,
                    max_bytes=max_bytes,
                )
                if (
                    actual_size != int(row.get("size") or 0)
                    or actual_digest != row.get("sha256")
                    or not self._matches_signature(
                        signature_bytes, row.get("media_type"),
                    )
                ):
                    raise ValueError("asset integrity check failed")
                if include_content:
                    content = data_path.read_bytes()
                verified_path = data_path
            public = self._public_metadata(row)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise FileNotFoundError("creative asset not found") from error
        return StoredCreativeAsset(public, content, verified_path)

    def list(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return a bounded metadata-only listing for the trusted principal."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("asset list limit must be an integer")
        if limit < 1 or limit > 100:
            raise ValueError("asset list limit must be between 1 and 100")
        folder = self._scope_path(tenant_id, user_id)
        if not folder.is_dir() or folder.is_symlink():
            return []
        rows: list[dict[str, Any]] = []
        for path in folder.glob("*.json"):
            if path.is_symlink():
                continue
            try:
                row = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if (
                isinstance(row, dict)
                and _ASSET_ID.fullmatch(str(row.get("asset_id") or ""))
                and path.stem == row["asset_id"]
            ):
                rows.append(self._public_metadata(row))
        rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return rows[:limit]

    def update(
        self,
        asset_id: str,
        *,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Atomically update safe mutable metadata without replacing content."""
        folder, safe_id = self._paths(asset_id, tenant_id, user_id)
        changes = self._clean_metadata(metadata)
        immutable = {
            "asset_id", "filename", "media_type", "size", "sha256", "created_at",
        }
        if immutable & set(changes):
            raise ValueError("creative asset metadata contains immutable fields")
        metadata_path = folder / f"{safe_id}.json"
        with self._lock:
            self.get(
                safe_id, tenant_id=tenant_id, user_id=user_id,
            )
            # The public projection excludes integrity fields; retain them from
            # the existing private record before writing the updated manifest.
            previous = self._read_private_metadata(metadata_path)
            updated = dict(previous)
            updated.update(changes)
            updated["updated_at"] = self._now()
            self._write_metadata(folder, safe_id, updated)
        return self._public_metadata(updated)

    def complete(
        self,
        asset_id: str,
        content: bytes,
        *,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Verify and attach completed video bytes to its pending job record."""
        folder, safe_id = self._paths(asset_id, tenant_id, user_id)
        changes = self._clean_metadata(metadata)
        immutable = {
            "asset_id", "filename", "media_type", "size", "sha256", "created_at",
        }
        if immutable & set(changes):
            raise ValueError("creative asset metadata contains immutable fields")
        with self._lock:
            row = self._read_private_metadata(folder / f"{safe_id}.json")
            if row.get("status") not in {"pending", "processing", "submitting"}:
                raise ValueError("creative asset is not a pending video job")
            media_type = self._validate_content(content, row.get("media_type"))
            self._enforce_quota(
                folder,
                len(content),
                current_size=int(row.get("size") or 0),
            )
            updated = dict(row)
            updated.update(changes)
            updated.update({
                "media_type": media_type,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "status": "ready",
                "updated_at": self._now(),
            })
            self._write_asset(folder, safe_id, content, updated)
        return self._public_metadata(updated)

    def _scope_path(self, tenant_id: str, user_id: str) -> Path:
        return self.root / self._scope_hash(tenant_id, "tenant_id") / self._scope_hash(
            user_id, "user_id",
        )

    @staticmethod
    def _scope_hash(value: str, label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized or len(normalized) > 256:
            raise ValueError(f"{label} must be non-empty and at most 256 characters")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_filename(value: str) -> str:
        filename = str(value or "").replace("\\", "/").split("/")[-1].strip()
        filename = "".join(
            character for character in filename
            if character >= " " and character != "\x7f"
        )[:200]
        if not filename or filename in {".", ".."}:
            raise ValueError("creative asset filename is invalid")
        return filename

    @staticmethod
    def _normalized_media_type(value: Any) -> str:
        media_type = str(value or "").split(";", 1)[0].strip().lower()
        if media_type not in _MIME_SIGNATURES:
            raise ValueError("unsupported creative asset media type")
        return media_type

    @classmethod
    def _matches_signature(cls, content: bytes, media_type: Any) -> bool:
        normalized = str(media_type or "").strip().lower()
        matcher = _MIME_SIGNATURES.get(normalized)
        return bool(matcher and matcher(content))

    def _validate_content(self, content: bytes, media_type: Any) -> str:
        if not isinstance(content, bytes) or not content:
            raise ValueError("creative asset content must be non-empty")
        normalized = self._normalized_media_type(media_type)
        max_bytes = (
            self.max_image_bytes
            if normalized.startswith("image/")
            else self.max_video_bytes
        )
        if len(content) > max_bytes:
            raise ValueError("creative asset exceeds the configured size limit")
        if not self._matches_signature(content, normalized):
            raise ValueError("creative asset content does not match its media type")
        return normalized

    @classmethod
    def _clean_metadata(cls, metadata: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(metadata, Mapping):
            raise ValueError("creative asset metadata must be an object")
        cleaned: dict[str, Any] = {}
        for key, value in metadata.items():
            field = str(key)
            if field not in _METADATA_FIELDS or is_sensitive_field(field):
                raise ValueError("creative asset metadata contains an unsupported field")
            cleaned[field] = cls._clean_metadata_value(value, depth=0)
        encoded = json.dumps(
            cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > _MAX_METADATA_BYTES:
            raise ValueError("creative asset metadata exceeds the size limit")
        return cleaned

    @classmethod
    def _clean_metadata_value(cls, value: Any, *, depth: int) -> Any:
        if depth > 4:
            raise ValueError("creative asset metadata is nested too deeply")
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return value
        if isinstance(value, float):
            if value != value or abs(value) == float("inf"):
                raise ValueError("creative asset metadata contains an invalid number")
            return value
        if isinstance(value, str):
            return redact_sensitive_text(value)[:4000]
        if isinstance(value, Mapping):
            result = {}
            for raw_key, child in value.items():
                key = str(raw_key)
                if len(key) > 100 or is_sensitive_field(key):
                    raise ValueError("creative asset metadata contains a protected field")
                result[key] = cls._clean_metadata_value(child, depth=depth + 1)
            return result
        if isinstance(value, (list, tuple)):
            if len(value) > 100:
                raise ValueError("creative asset metadata list is too large")
            return [
                cls._clean_metadata_value(item, depth=depth + 1)
                for item in value
            ]
        raise ValueError("creative asset metadata contains an unsupported value")

    def _ensure_private_scope(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in (self.root, folder.parent, folder):
            if path.is_symlink():
                raise OSError("creative asset storage path is invalid")
            os.chmod(path, 0o700)

    def _enforce_quota(
        self,
        folder: Path,
        new_size: int,
        *,
        current_size: int = 0,
        adding_asset: bool = False,
    ) -> None:
        metadata_paths = list(folder.glob("*.json"))
        if adding_asset and len(metadata_paths) >= self.max_assets_per_user:
            raise ValueError("creative asset count quota exceeded")
        total_size = 0
        for path in metadata_paths:
            if path.is_symlink():
                continue
            try:
                row = json.loads(path.read_text("utf-8"))
                total_size += max(0, int(row.get("size") or 0))
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        if total_size - current_size + new_size > self.max_user_bytes:
            raise ValueError("creative asset storage quota exceeded")

    def _write_asset(
        self,
        folder: Path,
        asset_id: str,
        content: bytes,
        metadata: Mapping[str, Any],
    ) -> None:
        content_path = folder / f"{asset_id}.bin"
        metadata_path = folder / f"{asset_id}.json"
        self._write_atomic(content_path, content)
        try:
            self._write_metadata(folder, asset_id, metadata)
        except (OSError, TypeError, ValueError):
            content_path.unlink(missing_ok=True)
            raise

    def _write_metadata(
        self,
        folder: Path,
        asset_id: str,
        metadata: Mapping[str, Any],
    ) -> None:
        if not _ASSET_ID.fullmatch(asset_id):
            raise ValueError("creative asset ID is invalid")
        encoded = json.dumps(
            dict(metadata),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._write_atomic(folder / f"{asset_id}.json", encoded)

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".creative-", dir=path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _file_integrity(path: Path, *, max_bytes: int) -> tuple[int, str, bytes]:
        digest = hashlib.sha256()
        total = 0
        prefix = bytearray()
        if path.stat().st_size > max_bytes:
            raise ValueError("asset file exceeds the size limit")
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("asset file exceeds the size limit")
                if len(prefix) < 16:
                    prefix.extend(chunk[:16 - len(prefix)])
        return total, digest.hexdigest(), bytes(prefix)

    def _paths(
        self,
        asset_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[Path, str]:
        safe_id = str(asset_id or "").strip()
        if not _ASSET_ID.fullmatch(safe_id):
            raise FileNotFoundError("creative asset not found")
        return self._scope_path(tenant_id, user_id), safe_id

    @staticmethod
    def _read_private_metadata(path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise FileNotFoundError("creative asset not found")
        try:
            row = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError, TypeError) as error:
            raise FileNotFoundError("creative asset not found") from error
        if not isinstance(row, dict):
            raise FileNotFoundError("creative asset not found")
        return row

    @staticmethod
    def _public_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = ["FilesystemCreativeAssetStore", "StoredCreativeAsset"]
