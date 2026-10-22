"""Optional, recoverable semantic retrieval with bounded embedding work."""

from collections import OrderedDict
import hashlib
import math
from threading import RLock
import time
from typing import Any, Callable, Iterable, Mapping

from agents.agent_platform.data.embedding_runtime import EMBEDDING_RUNNER
from agents.agent_platform.data.semantic import validate_vector


_RETRIEVAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, TimeoutError)


class WikiSemanticRetrieval:
    def __init__(
        self, provider: Any, index: Any, *, sanitize: Callable[[str], str],
        retry_after_seconds: float = 5.0,
    ) -> None:
        self.provider = provider
        self.index = index
        self.sanitize = sanitize
        self.retry_after_seconds = retry_after_seconds
        self.timeout_seconds = 2.0
        self.batch_size = 64
        self.top_k = 64
        self._lock = RLock()
        self._fingerprints: dict[str, str] = {}
        self._errors: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._queries: OrderedDict[tuple[str, str], tuple[float, tuple]] = OrderedDict()

    def configure(self, provider: Any, index: Any) -> None:
        with self._lock:
            self.provider, self.index = provider, index
            self._fingerprints.clear()
            self._errors.clear()
            self._queries.clear()

    @property
    def configured(self) -> bool:
        if self.provider is None or self.index is None:
            return False
        try:
            value = getattr(self.provider, "configured", True)
            return bool(value() if callable(value) else value)
        except _RETRIEVAL_ERRORS:
            return False

    def text(self, chunk: Any) -> str:
        parts = (
            chunk.title, " ".join(chunk.heading_path), " ".join(chunk.tags),
            chunk.category, chunk.subcategory, chunk.excerpt,
        )
        return " ".join(
            self.sanitize(str(part or "")) for part in parts if part
        ).strip()[:8_000]

    def fingerprint(self, chunks: Iterable[Any]) -> str:
        identity = getattr(self.provider, "fingerprint", "")
        identity = identity() if callable(identity) else identity
        digest = hashlib.sha256(str(identity or "").encode("utf-8"))
        for chunk in chunks:
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(b"\0")
            digest.update(self.text(chunk).encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    def is_current(self, scope: str, fingerprint: str) -> bool:
        checker = getattr(self.index, "is_current", None)
        try:
            if callable(checker):
                return bool(checker(scope=scope, fingerprint=fingerprint))
            return self._fingerprints.get(scope) == fingerprint
        except _RETRIEVAL_ERRORS as error:
            self._record_error(scope, error)
            return False

    def status(self, chunks: Iterable[Any], *, scope: str) -> dict[str, Any]:
        chunks = list(chunks)
        fingerprint = self.fingerprint(chunks)
        configured = self.configured
        current = configured and self.is_current(scope, fingerprint)
        with self._lock:
            error = self._errors.get(scope)
        return {
            "scope": scope, "configured": configured, "current": bool(current),
            "available": bool(current and not self._cooling_down(scope)),
            "chunk_count": len(chunks), "fingerprint": fingerprint,
            "error_type": error[0] if error else None,
        }

    def _record_error(self, scope: str, error: BaseException) -> None:
        with self._lock:
            self._errors[scope] = (
                type(error).__name__, time.monotonic() + self.retry_after_seconds,
            )
            self._errors.move_to_end(scope)
            while len(self._errors) > 256:
                self._errors.popitem(last=False)

    def _cooling_down(self, scope: str) -> bool:
        with self._lock:
            error = self._errors.get(scope)
            return bool(error and error[1] > time.monotonic())

    def _embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        method = getattr(self.provider, "embed", None)
        if not callable(method):
            raise TypeError("embedding provider must expose embed()")
        raw = EMBEDDING_RUNNER.embed(method, texts, timeout=self.timeout_seconds)
        if not isinstance(raw, (list, tuple)) or len(raw) != len(texts):
            raise ValueError("embedding provider returned an incomplete batch")
        vectors = [validate_vector(vector) for vector in raw]
        if any(len(vector) != len(vectors[0]) for vector in vectors):
            raise ValueError("embedding dimensions differ within a batch")
        return vectors

    def rebuild(self, chunks: Iterable[Any], *, scope: str) -> bool:
        if not self.configured:
            self._record_error(scope, RuntimeError("embedding not configured"))
            return False
        chunks = list(chunks)
        records = []
        try:
            fingerprint = self.fingerprint(chunks)
            for offset in range(0, len(chunks), self.batch_size):
                batch = chunks[offset:offset + self.batch_size]
                vectors = self._embed([self.text(chunk) for chunk in batch])
                records.extend(
                    {"chunk_id": chunk.chunk_id, "document_id": chunk.document_id,
                     "vector": vector}
                    for chunk, vector in zip(batch, vectors)
                )
            if fingerprint != self.fingerprint(chunks):
                raise RuntimeError("embedding model changed during rebuild")
            kwargs = {"scope": scope}
            if callable(getattr(self.index, "is_current", None)):
                kwargs["fingerprint"] = fingerprint
            self.index.rebuild(records, **kwargs)
            with self._lock:
                self._fingerprints[scope] = fingerprint
                self._errors.pop(scope, None)
            return True
        except _RETRIEVAL_ERRORS as error:
            self._record_error(scope, error)
            return False

    def _query_vector(self, query: str) -> tuple[float, ...]:
        identity = self.fingerprint(())
        key = (identity, query)
        with self._lock:
            cached = self._queries.get(key)
            if cached and cached[0] > time.monotonic():
                self._queries.move_to_end(key)
                return cached[1]
        vector = self._embed([query])[0]
        with self._lock:
            self._queries[key] = (time.monotonic() + 30.0, vector)
            self._queries.move_to_end(key)
            while len(self._queries) > 256:
                self._queries.popitem(last=False)
        return vector

    def search(
        self, query: str, chunks: Iterable[Any], *, scope: str,
    ) -> dict[str, float] | None:
        if not self.configured or self._cooling_down(scope):
            return None
        chunks = list(chunks)
        if not self.is_current(scope, self.fingerprint(chunks)):
            return None
        try:
            fingerprint = self.fingerprint(chunks)
            vector = self._query_vector(self.sanitize(str(query or ""))[:8_000])
            if fingerprint != self.fingerprint(chunks):
                raise RuntimeError("embedding model changed during query")
            rows = self.index.search(vector, scope=scope, limit=self.top_k)
            result = self._scores(rows)
            with self._lock:
                self._errors.pop(scope, None)
            return result
        except _RETRIEVAL_ERRORS as error:
            self._record_error(scope, error)
            return None

    @staticmethod
    def _scores(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
        result = {}
        for row in rows:
            if not isinstance(row, Mapping) or not row.get("chunk_id"):
                continue
            try:
                score = float(row.get("score", 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(score):
                result[str(row["chunk_id"])] = max(-1.0, min(1.0, score))
        return result
