"""Bounded projection of provider media into the chat presentation contract."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit, urlunsplit

_MAX_GALLERY_ITEMS = 12
_IMAGE_URL_FIELDS = ("url", "url_128", "image_url", "image_uri", "web_uri")
_VIDEO_URL_FIELDS = ("preview_url", "video_url", "source", "url")
_POSTER_FIELDS = ("video_cover_url", "cover_url", "thumbnail_url", "picture", "poster")
_FACEBOOK_VIDEO_PATHS = (
    re.compile(r"^/[^/]+/videos/\d+/?$"),
    re.compile(r"^/reel/\d+/?$"),
)
_CREATIVE_ASSET_PATH = re.compile(r"^/creative/assets/[0-9a-f]{32}$")


def _facebook_video_permalink(value: Any) -> str:
    """Normalize only known Facebook video permalink shapes."""
    raw = str(value or "").strip()
    if not raw or len(raw) > 4096 or raw.startswith("//"):
        return ""
    candidate = (
        f"https://www.facebook.com{raw}"
        if raw.startswith("/")
        else raw
    )
    try:
        parsed = urlsplit(candidate)
        host = str(parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or host not in {"facebook.com", "www.facebook.com", "m.facebook.com"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return ""

    path = parsed.path or "/"
    if any(pattern.fullmatch(path) for pattern in _FACEBOOK_VIDEO_PATHS):
        return urlunsplit(("https", "www.facebook.com", path, "", ""))
    if path.rstrip("/") in {"/watch", "/video.php"}:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if re.fullmatch(r"\d{1,30}", video_id):
            return urlunsplit((
                "https",
                "www.facebook.com",
                path,
                f"v={video_id}",
                "",
            ))
    return ""


def _safe_remote_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url or len(url) > 4096:
        return ""
    try:
        parsed = urlsplit(url)
        host = str(parsed.hostname or "").strip(".").lower()
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal"))
    ):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return ""
    return url


def _safe_creative_asset_url(value: Any) -> str:
    """Accept only opaque IDs on the authenticated creative-asset route."""
    raw = str(value or "").strip()
    return raw if _CREATIVE_ASSET_PATH.fullmatch(raw) else ""


def _safe_media_url(value: Any) -> str:
    return _safe_creative_asset_url(value) or _safe_remote_url(value)


def _first_url(row: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    return next(
        (
            url for field in fields
            if (url := _safe_media_url(row.get(field)))
        ),
        "",
    )


def media_gallery_from_results(results: Any) -> list[dict[str, Any]]:
    """Extract safe media previews or provider-page fallbacks from Tool results."""
    if not isinstance(results, (list, tuple)):
        return []
    gallery: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        if not isinstance(result, Mapping) or result.get("success") is False:
            continue
        data = result.get("data")
        if not isinstance(data, Mapping):
            continue
        for key in ("image_assets", "images"):
            rows = data.get(key)
            if isinstance(rows, list):
                _append_rows(gallery, seen, rows, "image")
        for key in ("video_assets", "videos"):
            rows = data.get(key)
            if isinstance(rows, list):
                _append_rows(gallery, seen, rows, "video")
        if len(gallery) >= _MAX_GALLERY_ITEMS:
            return gallery[:_MAX_GALLERY_ITEMS]
    return gallery


def _append_rows(
    gallery: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    rows: list[Any],
    kind: str,
) -> None:
    fields = _IMAGE_URL_FIELDS if kind == "image" else _VIDEO_URL_FIELDS
    for row in rows:
        if len(gallery) >= _MAX_GALLERY_ITEMS:
            return
        if not isinstance(row, Mapping):
            continue
        url = _first_url(row, fields)
        permalink_url = (
            _facebook_video_permalink(row.get("permalink_url"))
            if kind == "video" else ""
        )
        if not url and not permalink_url:
            continue
        resource_id = str(
            row.get("id")
            or row.get("image_id")
            or row.get("video_id")
            or row.get("hash")
            or ""
        ).strip()
        identity = (kind, resource_id or url or permalink_url)
        if identity in seen:
            continue
        seen.add(identity)
        item = {
            "kind": kind,
            "id": resource_id,
            "name": str(
                row.get("name") or row.get("file_name") or row.get("title") or ""
            )[:200],
        }
        if kind == "image":
            item["url"] = url
            width = row.get("original_width", row.get("width"))
            height = row.get("original_height", row.get("height"))
            if isinstance(width, int) and not isinstance(width, bool) and width > 0:
                item["width"] = width
            if isinstance(height, int) and not isinstance(height, bool) and height > 0:
                item["height"] = height
        else:
            if url:
                item["url"] = url
            poster = _first_url(row, _POSTER_FIELDS)
            if poster:
                item["poster"] = poster
            if permalink_url:
                item["permalink_url"] = permalink_url
            expires = str(
                row.get("preview_url_expire_time")
                or row.get("expires_at")
                or ""
            ).strip()
            if expires and len(expires) <= 80:
                item["expires_at"] = expires
        gallery.append(item)
