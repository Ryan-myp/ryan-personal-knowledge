"""Bounded OpenAI-compatible embedding adapter for trusted model settings."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

import httpx

from .semantic import validate_vector


MAX_EMBEDDING_BATCH = 64
MAX_EMBEDDING_TEXT_CHARS = 8_000
MAX_EMBEDDING_DIMENSIONS = 8_192


class OpenAICompatibleEmbeddingProvider:
    """Call an operator-configured embeddings endpoint with bounded inputs."""

    def __init__(
        self,
        configuration_provider: Callable[[], Mapping[str, Any]],
        *,
        client: Any = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not callable(configuration_provider):
            raise TypeError("configuration_provider must be callable")
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self.configuration_provider = configuration_provider
        self.client = client or httpx.Client()
        self.timeout_seconds = float(timeout_seconds)

    @property
    def fingerprint(self) -> str:
        try:
            config = self._configuration()
        except (RuntimeError, TypeError, ValueError):
            config = {"model": "", "base_url": ""}
        material = "\n".join((
            str(config["model"]),
            str(config["base_url"]),
        ))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def configured(self) -> bool:
        try:
            self._configuration()
        except (RuntimeError, TypeError, ValueError):
            return False
        return True

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise ValueError("embedding input must be a sequence of texts")
        if not texts or len(texts) > MAX_EMBEDDING_BATCH:
            raise ValueError("embedding batch size is outside supported limits")
        normalized = []
        for text in texts:
            if not isinstance(text, str) or len(text) > MAX_EMBEDDING_TEXT_CHARS:
                raise ValueError("embedding text is outside supported limits")
            normalized.append(text)

        configuration = self._configuration()
        url = self._endpoint(str(configuration["base_url"]))
        try:
            response = self.client.post(
                url,
                headers={
                    "Authorization": f"Bearer {configuration['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": configuration["model"],
                    "input": normalized,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            raise RuntimeError(
                f"embedding request failed ({type(error).__name__})"
            ) from None
        return self._vectors(payload, len(normalized))

    def _configuration(self) -> dict[str, str]:
        raw = self.configuration_provider()
        if not isinstance(raw, Mapping):
            raise RuntimeError("knowledge embedding model is not configured")
        model = str(raw.get("model") or "").strip()
        base_url = str(raw.get("base_url") or "").strip().rstrip("/")
        api_key = str(raw.get("api_key") or "").strip()
        if not model or not base_url or not api_key:
            raise RuntimeError("knowledge embedding model is not configured")
        self._endpoint(base_url)
        return {"model": model, "base_url": base_url, "api_key": api_key}

    @staticmethod
    def _endpoint(base_url: str) -> str:
        parsed = urlsplit(str(base_url or "").strip())
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("embedding endpoint must be a valid HTTP(S) URL")
        if parsed.scheme == "http" and parsed.hostname.lower() not in {
            "localhost", "127.0.0.1", "::1",
        }:
            raise ValueError("remote embedding endpoints must use HTTPS")
        path = parsed.path.rstrip("/")
        endpoint_path = path if path.endswith("/embeddings") else f"{path}/embeddings"
        return parsed._replace(path=endpoint_path).geturl()

    @staticmethod
    def _vectors(payload: Any, expected_count: int) -> list[list[float]]:
        if not isinstance(payload, Mapping):
            raise ValueError("embedding response is malformed")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise ValueError("embedding response item count does not match request")
        ordered: list[list[float] | None] = [None] * expected_count
        expected_dimension = None
        for item in data:
            if not isinstance(item, Mapping):
                raise ValueError("embedding response item is malformed")
            index = item.get("index")
            if isinstance(index, bool) or not isinstance(index, int):
                raise ValueError("embedding response index is invalid")
            if index < 0 or index >= expected_count or ordered[index] is not None:
                raise ValueError("embedding response indexes are invalid")
            vector = validate_vector(
                item.get("embedding") or (),
                expected_dimension=expected_dimension,
            )
            if len(vector) > MAX_EMBEDDING_DIMENSIONS:
                raise ValueError("embedding dimension exceeds supported limits")
            if expected_dimension is None:
                expected_dimension = len(vector)
            ordered[index] = list(vector)
        if any(vector is None for vector in ordered):
            raise ValueError("embedding response is incomplete")
        return [vector for vector in ordered if vector is not None]


__all__ = [
    "MAX_EMBEDDING_BATCH",
    "MAX_EMBEDDING_DIMENSIONS",
    "MAX_EMBEDDING_TEXT_CHARS",
    "OpenAICompatibleEmbeddingProvider",
]
