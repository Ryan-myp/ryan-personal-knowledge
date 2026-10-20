"""Bounded Agnes image and asynchronous video generation client."""

from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import re
from collections.abc import Mapping
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

import requests

from agents.tools.creative_media.models import (
    AGNES_MEDIA_BASE_URL,
    FREE_AGNES_MEDIA_MODELS,
    is_approved_free_media_model,
)


_IMAGE_TYPES = {
    "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda value: (
        len(value) >= 12 and value.startswith(b"RIFF") and value[8:12] == b"WEBP"
    ),
}
_VIDEO_TYPES = {
    "video/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
    "video/quicktime": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
    "video/webm": lambda value: value.startswith(b"\x1a\x45\xdf\xa3"),
}
_VIDEO_JOB_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
_IMAGE_SIZES = frozenset({"1K", "2K", "3K", "4K"})
_IMAGE_RATIOS = frozenset({
    "1:1", "4:3", "3:2", "16:9", "9:16", "2:3", "3:4", "21:9",
})
_VIDEO_RATIOS = frozenset({"16:9", "9:16", "1:1"})
_VIDEO_SIZES = frozenset({"720P", "1080P"})
_VIDEO_RESULT_HOSTS = frozenset({"platform-outputs.agnes-ai.space"})
_VIDEO_STATUSES = {
    "queued": "processing",
    "pending": "processing",
    "processing": "processing",
    "running": "processing",
    "completed": "completed",
    "complete": "completed",
    "success": "completed",
    "succeeded": "completed",
    "failed": "failed",
    "error": "failed",
    "cancelled": "failed",
    "canceled": "failed",
}


class MediaProviderError(RuntimeError):
    """Safe provider failure code without response bodies or credentials."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AgnesMediaClient:
    """Small HTTP adapter with explicit response, URL and byte limits."""

    def __init__(
        self,
        configuration: Mapping[str, Any],
        *,
        request: Callable[..., Any] | None = None,
        download: Callable[..., bytes] | None = None,
        timeout_seconds: float = 500.0,
        max_image_bytes: int = 20 * 1024 * 1024,
        max_video_bytes: int = 120 * 1024 * 1024,
        max_response_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        if not isinstance(configuration, Mapping):
            raise ValueError("media model configuration is unavailable")
        self.model = self._required_text(configuration.get("model"), "model")
        self.api_key = self._required_text(configuration.get("api_key"), "api_key")
        self.base_url = self._validate_base_url(configuration.get("base_url"))
        if self.base_url != AGNES_MEDIA_BASE_URL:
            raise ValueError("free Agnes media models require the official Agnes API URL")
        self.timeout_seconds = float(timeout_seconds)
        self.max_image_bytes = int(max_image_bytes)
        self.max_video_bytes = int(max_video_bytes)
        self.max_response_bytes = int(max_response_bytes)
        if (
            self.timeout_seconds <= 0
            or self.max_image_bytes <= 0
            or self.max_video_bytes <= 0
            or self.max_response_bytes <= 0
        ):
            raise ValueError("media client limits must be positive")
        self._request = request or requests.request
        self._download = download or self._download_response

    def generate_image(
        self,
        prompt: str,
        size: str = "2K",
        aspect_ratio: str = "1:1",
    ) -> list[dict[str, Any]]:
        """Generate at most one bounded image and require a real image signature."""
        prompt = self._prompt(prompt)
        size = str(size or "2K").strip()
        aspect_ratio = str(aspect_ratio or "1:1").strip()
        if not is_approved_free_media_model("image_generation", self.model):
            raise ValueError("only the latest free Agnes Image Flash model is allowed")
        if size not in _IMAGE_SIZES:
            raise ValueError("unsupported image size")
        if size in {"3K", "4K"} and self.model.lower().endswith("-flash"):
            raise ValueError("Agnes Image 2.5 Flash supports 1K or 2K output")
        if aspect_ratio not in _IMAGE_RATIOS:
            raise ValueError("unsupported image aspect ratio")
        payload = self._request_json(
            "POST",
            f"{self.base_url}/images/generations",
            json={
                "model": self.model,
                "prompt": prompt,
                "size": size,
                "ratio": aspect_ratio,
                "response_format": "b64_json",
                "n": 1,
            },
        )
        return [self._parse_image_result(payload)]

    def _parse_image_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        rows = payload.get("data")
        if not isinstance(rows, list) or not rows or len(rows) > 1:
            raise ValueError("image provider returned an invalid result")
        row = rows[0]
        if not isinstance(row, Mapping):
            raise ValueError("image provider returned an invalid result")
        media_type = str(row.get("mime_type") or row.get("mimeType") or "").lower()
        content = self._image_content(row)
        self._validate_output(content, media_type, _IMAGE_TYPES, self.max_image_bytes)
        detected_type = next(
            kind for kind, matcher in _IMAGE_TYPES.items() if matcher(content)
        )
        return {"content": content, "media_type": detected_type}

    def _image_content(self, row: Mapping[str, Any]) -> bytes:
        encoded = row.get("b64_json") or row.get("b64")
        if isinstance(encoded, str):
            if len(encoded) > ((self.max_image_bytes + 2) // 3) * 4 + 8:
                raise ValueError("generated image exceeds the size limit")
            try:
                return base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as error:
                raise ValueError("image provider returned invalid base64") from error
        return self._download_safe_url(
            row.get("url"),
            max_bytes=self.max_image_bytes,
            accepted_types=_IMAGE_TYPES,
        )

    def submit_video(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        duration_seconds: int = 5,
        resolution: str = "720P",
    ) -> dict[str, str]:
        """Submit one asynchronous video generation request."""
        prompt = self._prompt(prompt)
        if not is_approved_free_media_model("video_generation", self.model):
            raise ValueError("only the latest free Agnes Video Flash model is allowed")
        aspect_ratio = str(aspect_ratio or "").strip()
        resolution = str(resolution or "").strip().upper()
        if aspect_ratio not in _VIDEO_RATIOS:
            raise ValueError("unsupported video aspect ratio")
        self._validate_video_parameters(duration_seconds, resolution)
        payload = self._request_json(
            "POST",
            f"{self.base_url}/videos",
            json={
                "model": self.model,
                "prompt": prompt,
                "mode": "text",
                "seconds": str(duration_seconds),
                "size": resolution,
                "aspect_ratio": aspect_ratio,
                "n": 1,
            },
        )
        return self._parse_video_submission(payload)

    def _parse_video_submission(self, payload: Mapping[str, Any]) -> dict[str, str]:
        row = self._data_object(payload)
        provider_job_id = str(
            row.get("video_id") or row.get("task_id") or row.get("id") or ""
        ).strip()
        if not _VIDEO_JOB_ID.fullmatch(provider_job_id):
            raise ValueError("video provider returned an invalid job ID")
        raw_status = str(row.get("status") or "processing").strip().lower()
        status = _VIDEO_STATUSES.get(raw_status, "")
        if not status:
            raise ValueError("video provider returned an unknown job status")
        return {
            "video_id": provider_job_id,
            "status": status,
            "model": self.model,
        }

    def poll_video(self, video_id: str) -> dict[str, Any]:
        """Poll a provider job and download a validated result when complete."""
        provider_job_id = str(video_id or "").strip()
        if not _VIDEO_JOB_ID.fullmatch(provider_job_id):
            raise ValueError("video job ID is invalid")
        if not is_approved_free_media_model("video_generation", self.model):
            raise ValueError("only the latest free Agnes Video Flash model is allowed")
        payload = self._request_json(
            "GET",
            f"{self._origin()}/agnesapi",
            params={
                "video_id": provider_job_id,
                "model_name": self.model,
            },
        )
        return self._parse_video_status(self._data_object(payload))

    def _parse_video_status(self, row: Mapping[str, Any]) -> dict[str, Any]:
        raw_status = str(row.get("status") or "processing").strip().lower()
        status = _VIDEO_STATUSES.get(raw_status)
        if status == "failed":
            return {"status": "failed", "error": "video_provider_job_failed"}
        if status != "completed":
            return {"status": "processing"}

        media_type = str(
            row.get("mime_type") or row.get("media_type") or "video/mp4"
        ).lower()
        if media_type not in _VIDEO_TYPES:
            return {"status": "failed", "error": "video_result_invalid"}
        content, error = self._video_content(row)
        if error:
            return {"status": "failed", "error": error}
        try:
            self._validate_output(
                content, media_type, _VIDEO_TYPES, self.max_video_bytes,
            )
        except ValueError:
            return {"status": "failed", "error": "video_result_invalid"}
        detected_type = next(
            kind for kind, matcher in _VIDEO_TYPES.items() if matcher(content)
        )
        return {
            "status": "completed",
            "content": content,
            "media_type": detected_type,
        }

    def _video_content(
        self,
        row: Mapping[str, Any],
    ) -> tuple[bytes | None, str | None]:
        encoded = row.get("b64_json") or row.get("b64")
        if isinstance(encoded, str):
            if len(encoded) > ((self.max_video_bytes + 2) // 3) * 4 + 8:
                return None, "video_result_too_large"
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                return None, "video_result_invalid"
        else:
            url = row.get("video_url") or row.get("url")
            try:
                content = self._download_safe_url(
                    url,
                    max_bytes=self.max_video_bytes,
                    accepted_types=_VIDEO_TYPES,
                    allowed_hosts=_VIDEO_RESULT_HOSTS,
                )
            except MediaProviderError as error:
                code = {
                    "media_result_url_unsafe": "video_result_url_unsafe",
                    "media_result_too_large": "video_result_too_large",
                    "media_result_invalid": "video_result_invalid",
                    "media_provider_download_failed": "video_provider_download_failed",
                }.get(error.code, "video_provider_download_failed")
                return None, code
        return content, None

    @staticmethod
    def _required_text(value: Any, label: str) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 8192:
            raise ValueError(f"media {label} is not configured")
        return text

    @staticmethod
    def _prompt(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("creative prompt must be text")
        prompt = value.strip()
        if not prompt or len(prompt) > 4000:
            raise ValueError("creative prompt must contain 1 to 4000 characters")
        if any(ord(character) < 32 and character not in "\n\t\r" for character in prompt):
            raise ValueError("creative prompt contains unsupported characters")
        return prompt

    @staticmethod
    def _validate_base_url(value: Any) -> str:
        raw = str(value or "").strip().rstrip("/")
        if not raw or len(raw) > 2048:
            raise ValueError("media model base URL is not configured")
        try:
            parsed = urlsplit(raw)
            port = parsed.port
        except ValueError as error:
            raise ValueError("media model base URL is invalid") from error
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or port not in (None, 443)
        ):
            raise ValueError("media model base URL must be a credential-free HTTPS URL")
        if raw != AGNES_MEDIA_BASE_URL:
            raise ValueError("free Agnes media models require the official Agnes API URL")
        return raw

    def _validate_video_parameters(
        self,
        duration_seconds: Any,
        resolution: str,
    ) -> None:
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, int)
            or not 4 <= duration_seconds <= 12
        ):
            raise ValueError("video duration must be between 4 and 12 seconds")
        if resolution not in _VIDEO_SIZES:
            raise ValueError("video resolution must be 720P or 1080P")
        if (
            self.model.casefold()
            == FREE_AGNES_MEDIA_MODELS["video_generation"]["model"].casefold()
            and resolution != "720P"
        ):
            raise ValueError("Agnes Video 2.5 Flash supports 720P output")

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        try:
            response = self._request(
                method,
                url,
                headers=headers,
                timeout=self.timeout_seconds,
                allow_redirects=False,
                stream=True,
                **kwargs,
            )
            response.raise_for_status()
            declared_size = str(
                getattr(response, "headers", {}).get("content-length") or ""
            ).strip()
            if declared_size.isdigit() and int(declared_size) > self.max_response_bytes:
                raise MediaProviderError("media_provider_response_too_large")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > self.max_response_bytes:
                    raise MediaProviderError("media_provider_response_too_large")
            payload = json.loads(content)
        except MediaProviderError:
            raise
        except requests.Timeout as error:
            raise MediaProviderError("media_provider_timeout") from error
        except requests.ConnectionError as error:
            raise MediaProviderError("media_provider_connection_failed") from error
        except requests.HTTPError as error:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            provider_code = self._provider_error_code(response)
            if status_code == 503 and provider_code == "video_queue_full":
                code = "media_provider_video_queue_full"
            else:
                code = self._http_error_code(status_code)
            raise MediaProviderError(
                code
            ) from error
        except (requests.RequestException, TypeError, ValueError) as error:
            raise MediaProviderError("media_provider_request_failed") from error
        finally:
            if "response" in locals():
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        if not isinstance(payload, dict):
            raise MediaProviderError("media_provider_response_invalid")
        return payload

    @staticmethod
    def _http_error_code(status_code: Any) -> str:
        try:
            status = int(status_code)
        except (TypeError, ValueError):
            return "media_provider_request_failed"
        if status in {401, 403}:
            return "media_provider_auth_failed"
        if status == 402:
            return "media_provider_quota_exceeded"
        if status == 404:
            return "media_provider_endpoint_not_found"
        if status in {408, 504}:
            return "media_provider_timeout"
        if status == 429:
            return "media_provider_rate_limited"
        if status in {400, 409, 422}:
            return "media_provider_request_rejected"
        if 500 <= status <= 599:
            return "media_provider_unavailable"
        return "media_provider_request_failed"

    @staticmethod
    def _provider_error_code(response: Any) -> str:
        reader = getattr(response, "iter_content", None)
        if not callable(reader):
            return ""
        body = bytearray()
        try:
            for chunk in reader(chunk_size=4096):
                if not chunk:
                    continue
                if len(body) + len(chunk) > 8192:
                    return ""
                body.extend(chunk)
        except (requests.RequestException, TypeError, ValueError):
            return ""
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ""
        if not isinstance(payload, Mapping):
            return ""
        error = payload.get("error")
        if isinstance(error, Mapping):
            raw_code = error.get("code") or error.get("type")
        else:
            raw_code = payload.get("code")
        return str(raw_code or "").strip().lower()

    @staticmethod
    def _data_object(payload: Mapping[str, Any]) -> dict[str, Any]:
        row = payload.get("data", payload)
        if isinstance(row, list):
            row = row[0] if row else {}
        if not isinstance(row, Mapping):
            raise ValueError("media provider returned an invalid result")
        return dict(row)

    def _origin(self) -> str:
        parsed = urlsplit(self.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    def _download_safe_url(
        self,
        value: Any,
        *,
        max_bytes: int,
        accepted_types: Mapping[str, Any],
        allowed_hosts: frozenset[str] = frozenset(),
    ) -> bytes:
        raw = self._validated_download_url(value, allowed_hosts)
        try:
            content = self._download(raw, max_bytes=max_bytes)
        except MediaProviderError:
            raise
        except (requests.RequestException, OSError, TypeError, ValueError) as error:
            raise MediaProviderError("media_provider_download_failed") from error
        try:
            self._validate_output(content, "", accepted_types, max_bytes)
        except ValueError as error:
            code = (
                "media_result_too_large"
                if "size limit" in str(error)
                else "media_result_invalid"
            )
            raise MediaProviderError(code) from error
        return content

    def _validated_download_url(
        self,
        value: Any,
        allowed_hosts: frozenset[str],
    ) -> str:
        raw = str(value or "").strip()
        if not raw or len(raw) > 4096:
            raise MediaProviderError("media_result_url_unsafe")
        try:
            parsed = urlsplit(raw)
            base = urlsplit(self.base_url)
            port = parsed.port
        except (TypeError, ValueError) as error:
            raise MediaProviderError("media_result_url_unsafe") from error
        hostname = str(parsed.hostname or "").lower()
        base_hostname = str(base.hostname or "").lower()
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if (
            parsed.scheme.lower() != "https"
            or (
                hostname != base_hostname
                and hostname not in allowed_hosts
            )
            or parsed.username
            or parsed.password
            or port not in (None, 443)
            or (address is not None and not address.is_global)
        ):
            raise MediaProviderError("media_result_url_unsafe")
        return raw

    def _download_response(self, url: str, *, max_bytes: int) -> bytes:
        response = requests.get(
            url,
            timeout=self.timeout_seconds,
            allow_redirects=False,
            stream=True,
        )
        try:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise MediaProviderError("media_result_too_large")
            return bytes(content)
        finally:
            response.close()

    @staticmethod
    def _validate_output(
        content: Any,
        media_type: str,
        signatures: Mapping[str, Any],
        max_bytes: int,
    ) -> None:
        if not isinstance(content, bytes) or not content:
            raise ValueError("media provider returned empty content")
        if len(content) > max_bytes:
            raise ValueError("media provider output exceeds the size limit")
        normalized_type = str(media_type or "").split(";", 1)[0].strip().lower()
        if normalized_type and normalized_type not in signatures:
            raise ValueError("media provider returned an unsupported media type")
        if not any(matcher(content) for matcher in signatures.values()):
            raise ValueError("media provider output does not match a media signature")
        if normalized_type and not signatures[normalized_type](content):
            raise ValueError("media provider content does not match its media type")


__all__ = ["AgnesMediaClient", "MediaProviderError"]
