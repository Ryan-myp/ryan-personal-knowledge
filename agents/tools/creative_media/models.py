"""Agnes media models currently approved for free-tier use."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit


AGNES_MEDIA_BASE_URL = "https://apihub.agnes-ai.com/v1"
FREE_AGNES_MEDIA_MODELS: dict[str, dict[str, str]] = {
    "image_generation": {
        "model": "agnes-image-2.5-flash",
        "name": "Agnes Image 2.5 Flash",
        "availability": "free",
    },
    "video_generation": {
        "model": "agnes-video-2.5-flash",
        "name": "Agnes Video 2.5 Flash",
        "availability": "free_limited_time",
    },
}


def is_approved_free_media_model(purpose: str, model: Any) -> bool:
    """Return whether a media model is on the explicitly approved free list."""
    option = FREE_AGNES_MEDIA_MODELS.get(str(purpose or "").strip().lower())
    return bool(
        option
        and isinstance(model, str)
        and model.strip().casefold() == option["model"].casefold()
    )


def validate_free_media_configuration(
    purpose: str,
    model: Any,
    base_url: Any,
) -> str:
    """Validate both the free model ID and the official Agnes API endpoint."""
    if not is_approved_free_media_model(purpose, model):
        raise ValueError("only the latest free Agnes Flash media model is allowed")

    raw = str(base_url or "").strip().rstrip("/")
    if not raw:
        return AGNES_MEDIA_BASE_URL
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as error:
        raise ValueError("media model base URL is invalid") from error
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname != "apihub.agnes-ai.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in (None, 443)
        or raw != AGNES_MEDIA_BASE_URL
    ):
        raise ValueError("free Agnes media models require the official Agnes API URL")
    return AGNES_MEDIA_BASE_URL


def public_media_model_catalog() -> dict[str, dict[str, str]]:
    """Return a copy of non-secret model options for settings clients."""
    return {
        purpose: {**option, "base_url": AGNES_MEDIA_BASE_URL}
        for purpose, option in FREE_AGNES_MEDIA_MODELS.items()
    }


def profile_supports_free_media_model(profile: Mapping[str, Any]) -> bool:
    """Handle legacy profile rows without trusting their model names."""
    purpose = str(profile.get("purpose") or "chat").strip().lower()
    if purpose not in FREE_AGNES_MEDIA_MODELS:
        return True
    return is_approved_free_media_model(purpose, profile.get("model"))
