"""Identity-scoped local storage for chat media and document attachments."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.agent_harness.messages import InputMedia, MediaFrame
from agents.deployments.advertising.api.chat_documents import (
    CHAT_DOCUMENT_TYPES,
    IMAGE_EXTENSIONS,
    MAX_DOCUMENT_BYTES,
    VIDEO_EXTENSIONS,
    detect_chat_attachment_type,
    extract_chat_document_text,
)


_MIB = 1024 * 1024
_MAX_ATTACHMENTS_PER_TURN = 5
_MAX_TURN_BYTES = 80 * _MIB
_MAX_SESSION_ATTACHMENTS = 50
_DEFAULT_MAX_SESSION_BYTES = 200 * _MIB
_MAX_VIDEO_SECONDS = 300.0
_MAX_VIDEO_FRAMES = 6
_MIME_SIGNATURES = {
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")
    and data[12:16] == b"IHDR",
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    "video/mp4": lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
    "video/quicktime": lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
    "video/webm": lambda data: data.startswith(b"\x1a\x45\xdf\xa3"),
}


@dataclass(frozen=True)
class StoredChatMedia:
    """Stored file bytes and the safe metadata shown in the transcript."""

    metadata: dict[str, Any]
    content: bytes

    def to_input_media(self) -> InputMedia:
        media_type = self.metadata["media_type"]
        frames = (
            _extract_video_frames(self.content, media_type)
            if media_type.startswith("video/")
            else ()
        )
        extracted_text = (
            extract_chat_document_text(
                self.content,
                filename=self.metadata["filename"],
                media_type=media_type,
            )
            if self.metadata.get("attachment_kind") == "document"
            else ""
        )
        return InputMedia(
            attachment_id=self.metadata["id"],
            filename=self.metadata["filename"],
            media_type=media_type,
            content=self.content,
            frames=frames,
            extracted_text=extracted_text,
        )


class ChatMediaStore:
    """Filesystem-backed media store with tenant, user and session isolation."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_image_bytes: int = 15 * _MIB,
        max_video_bytes: int = 50 * _MIB,
        max_document_bytes: int = MAX_DOCUMENT_BYTES,
        max_session_bytes: int = _DEFAULT_MAX_SESSION_BYTES,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_image_bytes = int(max_image_bytes)
        self.max_video_bytes = int(max_video_bytes)
        self.max_document_bytes = int(max_document_bytes)
        self.max_session_bytes = int(max_session_bytes)
        self._write_lock = threading.RLock()
        if (
            self.max_image_bytes <= 0
            or self.max_video_bytes <= 0
            or self.max_document_bytes <= 0
            or self.max_session_bytes <= 0
        ):
            raise ValueError("chat media size limits must be positive")

    @staticmethod
    def _scope_key(value: str, label: str) -> str:
        normalized = str(value or "").strip()
        if not normalized or len(normalized) > 200:
            raise ValueError(f"{label} must be non-empty and at most 200 characters")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def _scope_path(
        cls,
        root: Path,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> Path:
        return root / cls._scope_key(tenant_id, "tenant_id") / cls._scope_key(
            user_id, "user_id",
        ) / cls._scope_key(session_id, "session_id")

    @staticmethod
    def _safe_filename(value: str) -> str:
        filename = str(value or "").replace("\\", "/").split("/")[-1].strip()
        filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
        filename = filename[:200]
        if not filename or filename in {".", ".."}:
            raise ValueError("attachment filename is invalid")
        return filename

    def save(
        self,
        content: bytes,
        *,
        filename: str,
        content_type: str,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Validate content and atomically store one scoped attachment."""
        if not isinstance(content, bytes) or not content:
            raise ValueError("attachment content must be non-empty")
        if len(content) > self.max_upload_bytes:
            raise ValueError(
                f"attachment exceeds the {self.max_upload_bytes // _MIB} MiB size limit"
            )
        clean_name = self._safe_filename(filename)
        media_type = detect_chat_attachment_type(
            content,
            filename=clean_name,
            content_type=content_type,
            media_signatures=_MIME_SIGNATURES,
        )
        if media_type.startswith("image/"):
            max_bytes = self.max_image_bytes
        elif media_type.startswith("video/"):
            max_bytes = self.max_video_bytes
        else:
            max_bytes = self.max_document_bytes
        if len(content) > max_bytes:
            raise ValueError(
                f"attachment exceeds the {max_bytes // _MIB} MiB size limit"
            )
        folder = self._scope_path(
            self.root, tenant_id, user_id, session_id,
        )
        with self._write_lock:
            self._ensure_private_scope(folder)
            self._enforce_session_quota(folder, len(content))
            attachment_id = str(uuid.uuid4())
            metadata = {
                "id": attachment_id,
                "filename": clean_name,
                "media_type": media_type,
                "attachment_kind": (
                    "document"
                    if media_type.startswith("text/")
                    or media_type in {
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    }
                    else "media"
                ),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            data_path = folder / f"{attachment_id}.bin"
            metadata_path = folder / f"{attachment_id}.json"
            self._write_atomic(data_path, content)
            try:
                serialized = json.dumps(
                    metadata, ensure_ascii=False,
                ).encode("utf-8")
                self._write_atomic(metadata_path, serialized)
            except Exception:
                data_path.unlink(missing_ok=True)
                raise
        return {key: value for key, value in metadata.items() if key != "sha256"}

    def load(
        self,
        attachment_id: str,
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> StoredChatMedia:
        folder, safe_id = self._paths(
            attachment_id, session_id, tenant_id, user_id,
        )
        try:
            metadata = json.loads((folder / f"{safe_id}.json").read_text("utf-8"))
            content = (folder / f"{safe_id}.bin").read_bytes()
        except (OSError, ValueError, TypeError) as error:
            raise FileNotFoundError("chat attachment not found") from error
        if (
            not isinstance(metadata, dict)
            or metadata.get("id") != safe_id
            or not isinstance(content, bytes)
            or not content
            or hashlib.sha256(content).hexdigest() != metadata.get("sha256")
        ):
            raise FileNotFoundError("chat attachment not found")
        public = {
            key: metadata[key]
            for key in (
                "id", "filename", "media_type", "attachment_kind", "size"
            )
            if key in metadata
        }
        return StoredChatMedia(public, content)

    def load_for_model(
        self,
        attachment_ids: list[str],
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[InputMedia, ...]:
        """Load an explicitly bounded set of attachments for one model turn."""
        if len(attachment_ids) > _MAX_ATTACHMENTS_PER_TURN:
            raise ValueError("a chat turn supports at most 5 attachments")
        unique_ids = tuple(dict.fromkeys(attachment_ids))
        metadata_rows = [
            self._read_metadata(
                attachment_id,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            for attachment_id in unique_ids
        ]
        total_size = sum(int(item["size"]) for item in metadata_rows)
        if total_size > _MAX_TURN_BYTES:
            raise ValueError("combined chat attachments exceed the 80 MiB limit")
        attachments = tuple(
            self.load(
                str(metadata["id"]),
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
            ).to_input_media()
            for metadata in metadata_rows
        )
        document_chars = sum(len(item.extracted_text) for item in attachments)
        if document_chars > 60_000:
            raise ValueError(
                "本轮文档提取内容超过 60000 字符，请拆分文件后分批分析"
            )
        return attachments

    @property
    def max_upload_bytes(self) -> int:
        return max(
            self.max_image_bytes,
            self.max_video_bytes,
            self.max_document_bytes,
        )

    def max_upload_bytes_for(
        self,
        filename: str,
        content_type: str,
    ) -> int:
        extension = Path(filename).suffix.lower()
        media_type = str(content_type or "").split(";", 1)[0].strip().lower()
        if extension in IMAGE_EXTENSIONS:
            return self.max_image_bytes
        if extension in VIDEO_EXTENSIONS:
            return self.max_video_bytes
        if extension in CHAT_DOCUMENT_TYPES:
            return self.max_document_bytes
        if media_type.startswith("image/"):
            return self.max_image_bytes
        if media_type.startswith("video/"):
            return self.max_video_bytes
        return self.max_document_bytes

    def delete_session(
        self, session_id: str, *, tenant_id: str, user_id: str,
    ) -> None:
        folder = self._scope_path(
            self.root, tenant_id, user_id, session_id,
        )
        with self._write_lock:
            if folder.exists():
                shutil.rmtree(folder)

    def delete(
        self,
        attachment_id: str,
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> bool:
        """Delete one attachment inside the authenticated conversation scope."""
        folder, safe_id = self._paths(
            attachment_id, session_id, tenant_id, user_id,
        )
        with self._write_lock:
            data_path = folder / f"{safe_id}.bin"
            metadata_path = folder / f"{safe_id}.json"
            existed = data_path.exists() or metadata_path.exists()
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        return existed

    def _paths(
        self,
        attachment_id: str,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[Path, str]:
        try:
            safe_id = str(uuid.UUID(str(attachment_id)))
        except (ValueError, TypeError, AttributeError) as error:
            raise FileNotFoundError("chat attachment not found") from error
        folder = self._scope_path(
            self.root, tenant_id, user_id, session_id,
        )
        return folder, safe_id

    def _read_metadata(
        self,
        attachment_id: str,
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        folder, safe_id = self._paths(
            attachment_id, session_id, tenant_id, user_id,
        )
        try:
            metadata = json.loads(
                (folder / f"{safe_id}.json").read_text("utf-8")
            )
        except (OSError, ValueError, TypeError) as error:
            raise FileNotFoundError("chat attachment not found") from error
        if (
            not isinstance(metadata, dict)
            or metadata.get("id") != safe_id
            or not isinstance(metadata.get("size"), int)
            or isinstance(metadata.get("size"), bool)
            or metadata["size"] <= 0
            or metadata["size"] > self.max_upload_bytes
        ):
            raise FileNotFoundError("chat attachment not found")
        return metadata

    def _enforce_session_quota(self, folder: Path, incoming_bytes: int) -> None:
        metadata_files = tuple(folder.glob("*.json"))
        if len(metadata_files) >= _MAX_SESSION_ATTACHMENTS:
            raise ValueError(
                f"a conversation can store at most {_MAX_SESSION_ATTACHMENTS} attachments"
            )
        used_bytes = sum(
            path.stat().st_size
            for path in folder.glob("*.bin")
            if path.is_file()
        )
        if used_bytes + incoming_bytes > self.max_session_bytes:
            limit_mib = self.max_session_bytes // _MIB
            raise ValueError(
                f"conversation attachments exceed the {limit_mib} MiB storage limit"
            )

    def _ensure_private_scope(self, folder: Path) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        current = self.root
        for part in folder.relative_to(self.root).parts:
            current = current / part
            current.mkdir(mode=0o700, exist_ok=True)
            os.chmod(current, 0o700)

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".upload-", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def _extract_video_frames(content: bytes, media_type: str) -> tuple[MediaFrame, ...]:
    """Sample at most six evenly spaced video frames for vision models."""
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError(
            "视频理解需要部署环境安装 ffmpeg 和 ffprobe；文件已保存，可直接播放"
        )
    suffix = ".webm" if media_type == "video/webm" else ".mp4"
    with tempfile.TemporaryDirectory(prefix="agent-video-") as directory:
        video_path = Path(directory) / f"input{suffix}"
        video_path.write_bytes(content)
        try:
            probe = subprocess.run(
                [
                    ffprobe, "-v", "error", "-show_entries",
                    "format=duration", "-of",
                    "default=noprint_wrappers=1:nokey=1", str(video_path),
                ],
                check=True,
                capture_output=True,
                timeout=8,
                text=True,
            )
            duration = float(probe.stdout.strip())
            if not math.isfinite(duration) or not 0 < duration <= _MAX_VIDEO_SECONDS:
                raise ValueError("视频长度必须在 5 分钟以内")
            frame_rate = min(_MAX_VIDEO_FRAMES / duration, 1.0)
            extraction = subprocess.run(
                [
                    ffmpeg, "-v", "error", "-i", str(video_path),
                    "-vf", f"fps={frame_rate:.8f},scale=768:-2",
                    "-frames:v", str(_MAX_VIDEO_FRAMES), "-f", "image2pipe",
                    "-vcodec", "mjpeg", "-q:v", "8", "-fs", "12000000",
                    "pipe:1",
                ],
                check=True,
                capture_output=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("视频抽帧超时，请使用更短的视频") from error
        except (subprocess.CalledProcessError, ValueError) as error:
            if isinstance(error, ValueError):
                raise
            raise ValueError("无法读取该视频格式，请使用 MP4 或 WebM") from error
    frames_data = _split_jpeg_frames(extraction.stdout)
    if not frames_data:
        raise ValueError("未能从视频中读取画面帧")
    return tuple(
        MediaFrame(
            timestamp_seconds=duration * (index + 0.5) / len(frames_data),
            media_type="image/jpeg",
            content=frame,
        )
        for index, frame in enumerate(frames_data)
    )


def _split_jpeg_frames(payload: bytes) -> list[bytes]:
    frames: list[bytes] = []
    offset = 0
    while len(frames) < _MAX_VIDEO_FRAMES:
        start = payload.find(b"\xff\xd8", offset)
        if start < 0:
            break
        end = payload.find(b"\xff\xd9", start + 2)
        if end < 0:
            break
        frames.append(payload[start:end + 2])
        offset = end + 2
    return frames


__all__ = ["ChatMediaStore", "StoredChatMedia"]
