"""Application-neutral Skill catalog and standard Markdown Skill source."""

from __future__ import annotations

import threading
import hashlib
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from .reference_selection import reference_terms, select_reference_excerpts
from .metadata import (
    immutable_metadata, instruction_body, instruction_budget, read_skill_text, skill_identity,
)
from ..redaction import redact_for_persistence


_REFERENCE_SUFFIXES = frozenset({
    ".md", ".markdown", ".txt", ".yaml", ".yml", ".json",
})
_MAX_REFERENCE_FILES = 128
_MAX_REFERENCE_CHARS = 100_000
_MAX_REFERENCE_CONTEXT_CHARS = 1_200
_MAX_REFERENCE_TOTAL_CHARS = 400_000


@dataclass(frozen=True)
class SkillBinding:
    """Advisory Skill instructions; never an executable Tool contract."""

    name: str
    instructions: str
    description: str = ""
    version: str = "1.0.0"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    reference_documents: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("Skill name is required")
        if not str(self.instructions or "").strip():
            raise ValueError("Skill instructions are required")
        if not isinstance(self.reference_documents, Mapping):
            raise ValueError("Skill reference_documents must be a mapping")
        if any(
            not isinstance(path, str) or not isinstance(content, str)
            for path, content in self.reference_documents.items()
        ):
            raise ValueError("Skill references must map string paths to text")
        object.__setattr__(self, "metadata", immutable_metadata(self.metadata))
        object.__setattr__(self, "reference_documents", MappingProxyType(dict(self.reference_documents)))


class SkillSource(Protocol):
    @property
    def source_id(self) -> str:
        ...

    def list_skills(self) -> Sequence[SkillBinding]:
        ...


class StaticSkillSource:
    """In-memory source for built-in, tenant or test Skill snapshots."""

    def __init__(self, source_id: str, bindings: Sequence[SkillBinding]):
        source_key = str(source_id or "").strip()
        if not source_key:
            raise ValueError("Skill source requires a non-empty source_id")
        self._source_id = source_key
        self._bindings = tuple(bindings)

    @property
    def source_id(self) -> str:
        return self._source_id

    def list_skills(self) -> tuple[SkillBinding, ...]:
        return self._bindings


class MarkdownSkillSource(StaticSkillSource):
    """Load a standard ``SKILL.md`` without importing package code."""

    @classmethod
    def from_directory(
        cls, directory: str | Path, *, source_id: str | None = None,
    ) -> "MarkdownSkillSource":
        root = Path(directory).resolve()
        skill_file = root / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"Skill directory must contain SKILL.md: {root}")
        content = read_skill_text(skill_file)
        identity = skill_identity(content, root.name)
        reference_documents = cls._read_reference_documents(root)
        return cls(
            source_id or f"markdown:{identity['name']}",
            [SkillBinding(
                name=identity["name"],
                instructions=content,
                description=identity["description"],
                version=identity["version"],
                metadata={**identity["metadata"], "path": str(skill_file)},
                reference_documents=reference_documents,
            )],
        )

    @staticmethod
    def _read_reference_documents(root: Path) -> dict[str, str]:
        reference_root = root / "references"
        if not reference_root.is_dir():
            return {}
        if reference_root.is_symlink():
            raise ValueError("Skill references directory cannot be a symlink")

        documents: dict[str, str] = {}
        total_chars = 0
        for index, path in enumerate(reference_root.rglob("*")):
            if index >= 1024:
                raise ValueError("Skill references exceed the entry limit")
            if path.is_symlink():
                raise ValueError("Skill reference file cannot be a symlink")
            if not path.is_file():
                continue
            if path.suffix.lower() not in _REFERENCE_SUFFIXES:
                continue
            if len(documents) >= _MAX_REFERENCE_FILES:
                raise ValueError(
                    f"Skill references exceed {_MAX_REFERENCE_FILES} text files"
                )
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("Skill reference path escapes its package")
            relative = path.relative_to(root).as_posix()
            try:
                with path.open("r", encoding="utf-8") as handle:
                    content = handle.read(_MAX_REFERENCE_CHARS + 1)
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(
                    f"Unable to read UTF-8 Skill reference '{relative}'"
                ) from exc
            if len(content) > _MAX_REFERENCE_CHARS:
                content = content[:_MAX_REFERENCE_CHARS]
            total_chars += len(content)
            if total_chars > _MAX_REFERENCE_TOTAL_CHARS:
                raise ValueError("Skill references exceed the aggregate text limit")
            documents[relative] = content
        return documents


class MarkdownSkillDirectorySource:
    """Read every standard Skill directory below one trusted root."""

    def __init__(self, root: str | Path, *, source_id: str | None = None):
        self.root = Path(root).resolve()
        self._source_id = source_id or f"markdown-tree:{self.root}"

    @property
    def source_id(self) -> str:
        return self._source_id

    def list_skills(self) -> tuple[SkillBinding, ...]:
        bindings: list[SkillBinding] = []
        for skill_file in sorted(self.root.rglob("SKILL.md")):
            source = MarkdownSkillSource.from_directory(skill_file.parent)
            bindings.extend(source.list_skills())
        return tuple(bindings)


class SkillCatalog(Protocol):
    def register_source(self, source: SkillSource) -> list[str]:
        ...

    def list_skills(self) -> list[SkillBinding]:
        ...

    def build_context(
        self,
        user_input: str,
        *,
        source_ids: Sequence[str] | None = None,
    ) -> str:
        ...

    def source_snapshot(self) -> dict[str, list[str]]:
        ...

    def healthcheck(self) -> dict[str, Any]:
        ...


class InMemorySkillCatalog:
    """Bounded advisory Skill catalog shared by any Agent application."""

    def __init__(
        self, *, max_context_chars: int = 12_000, max_skills: int = 8,
        max_cached_contexts: int = 64,
    ) -> None:
        if type(max_cached_contexts) is not int or max_cached_contexts <= 0:
            raise ValueError("Skill context cache capacity must be a positive integer")
        if any(type(value) is not int or value <= 0 for value in (max_context_chars, max_skills)):
            raise ValueError("Skill catalog limits must be positive")
        self.max_context_chars = int(max_context_chars)
        self.max_skills = int(max_skills)
        self._lock = threading.RLock()
        self._skills: dict[str, SkillBinding] = {}
        self._sources: dict[str, list[str]] = {}
        self._selection_text: dict[str, str] = {}
        self._reference_index: dict[str, frozenset[str]] = {}
        self._max_cached_contexts = max_cached_contexts
        self._revision = 0
        self._context_cache: OrderedDict[tuple[Any, ...], str] = OrderedDict()

    def register_source(self, source: SkillSource) -> list[str]:
        source_id = str(getattr(source, "source_id", "") or "").strip()
        list_skills = getattr(source, "list_skills", None)
        if not source_id or not callable(list_skills):
            raise TypeError("Skill source must expose source_id and list_skills()")
        bindings = list(list_skills())
        names: list[str] = []
        with self._lock:
            if source_id in self._sources:
                raise ValueError(f"Skill source '{source_id}' already registered")
            try:
                for binding in bindings:
                    if not isinstance(binding, SkillBinding):
                        raise TypeError("Skill source must return SkillBinding values")
                    if binding.name in self._skills:
                        raise ValueError(f"Skill '{binding.name}' already registered")
                    self._skills[binding.name] = binding
                    names.append(binding.name)
                    self._selection_text[binding.name] = " ".join((
                        binding.name, redact_for_persistence(binding.description),
                    )).casefold()
                    self._reference_index[binding.name] = frozenset(
                        term
                        for path, text in binding.reference_documents.items()
                        for term in reference_terms(path + "\n" + redact_for_persistence(text))
                    )
                self._sources[source_id] = list(names)
            except Exception:
                for name in names:
                    self._skills.pop(name, None)
                    self._selection_text.pop(name, None)
                    self._reference_index.pop(name, None)
                raise
            self._revision += 1
            self._context_cache.clear()
        return names

    def unregister_source(self, source_id: str) -> list[str]:
        with self._lock:
            names = list(self._sources.pop(str(source_id), []))
            for name in names:
                self._skills.pop(name, None)
                self._selection_text.pop(name, None)
                self._reference_index.pop(name, None)
            if names:
                self._revision += 1
                self._context_cache.clear()
            return names

    def list_skills(self) -> list[SkillBinding]:
        with self._lock:
            return list(self._skills.values())

    def _score(self, skill: SkillBinding, terms: set[str]) -> int:
        haystack = self._selection_text[skill.name]
        identity_score = sum(1 for term in terms if term and term in haystack)
        name_score = len(terms & reference_terms(skill.name, stopwords=()))
        return identity_score * 3 + name_score * 12

    def _select_skills(
        self, terms: set[str], allowed_names: set[str] | None, preferred: set[str], user_input: str,
    ) -> list[SkillBinding]:
        candidates = [skill for skill in self._skills.values()
                      if allowed_names is None or skill.name in allowed_names]
        preferred = preferred | {skill.name for skill in candidates
                                  if self._trigger_matches(skill, user_input)}
        # Repeated boilerplate in references is not evidence of topic relevance.
        # Compute frequency only inside the request's allowed source scope.
        frequency = Counter(term for skill in candidates
                            for term in terms & self._reference_index[skill.name])
        rare_terms = {term for term, count in frequency.items()
                      if count <= max(1, len(candidates) // 4)}
        scored = []
        for skill in candidates:
            reference_score = len(rare_terms & self._reference_index[skill.name])
            if reference_score < min(2, len(terms)):
                reference_score = 0
            scored.append((self._score(skill, terms) + reference_score, skill))
        threshold = max(1, max((score for score, _ in scored), default=0) * 0.6)
        eligible = [(score, skill) for score, skill in scored
                    if score >= threshold or skill.name in preferred
                    or skill.metadata.get("always_on") is True]
        eligible.sort(key=lambda item: (
            item[1].metadata.get("always_on") is not True,
            item[1].name not in preferred, -item[0], item[1].name,
        ))
        return [skill for _, skill in eligible[:self.max_skills]]

    @staticmethod
    def _trigger_matches(skill: SkillBinding, user_input: str) -> bool:
        keywords = skill.metadata.get("selection_keywords", ())
        if not isinstance(keywords, (tuple, list)):
            return False
        return any(
            re.search(r"(?<![a-z0-9_])" + re.escape(keyword.casefold()) + r"(?![a-z0-9_])",
                      str(user_input).casefold())
            for keyword in keywords[:128] if isinstance(keyword, str) and keyword.strip()
        )

    def build_tool_context(
        self, user_input: str, tools: Sequence[Any], *, source_ids: Sequence[str] | None = None,
    ) -> str:
        """Prioritize explicit Tool/Skill bindings without granting capabilities."""
        preferred = set()
        for tool in tools:
            refs = (
                tool.get("skill_refs", ()) if isinstance(tool, Mapping)
                else getattr(tool, "skill_refs", ())
            )
            name = (
                tool.get("skill", "") if isinstance(tool, Mapping)
                else getattr(tool, "skill", "")
            )
            preferred.update(str(ref) for ref in refs or ())
            if name:
                preferred.add(str(name))
        return self.build_context(user_input, source_ids=source_ids, skill_refs=tuple(preferred))

    def build_context(
        self,
        user_input: str,
        *,
        source_ids: Sequence[str] | None = None,
        skill_refs: Sequence[str] = (),
    ) -> str:
        terms = reference_terms(user_input, stopwords=())
        allowed_sources = (
            {str(item).strip() for item in source_ids if str(item).strip()}
            if source_ids is not None else None
        )
        preferred = {str(item).strip() for item in skill_refs if str(item).strip()}
        with self._lock:
            revision = self._revision
            cache_key = (
                revision,
                hashlib.sha256(str(user_input or "").encode("utf-8", errors="surrogatepass")).digest(),
                tuple(sorted(allowed_sources)) if allowed_sources is not None else None,
                tuple(sorted(preferred)),
            )
            if cache_key in self._context_cache:
                self._context_cache.move_to_end(cache_key)
                return self._context_cache[cache_key]
            allowed_names = (
                {
                    name
                    for source_id in allowed_sources or ()
                    for name in self._sources.get(source_id, ())
                }
                if allowed_sources is not None else None
            )
            skills = self._select_skills(terms, allowed_names, preferred, user_input)
        context = self._render_context(skills, user_input)
        with self._lock:
            if revision == self._revision:
                self._context_cache[cache_key] = context
                while len(self._context_cache) > self._max_cached_contexts:
                    self._context_cache.popitem(last=False)
        return context

    def _render_context(self, skills: Sequence[SkillBinding], user_input: str) -> str:
        chunks: list[str] = []
        remaining = self.max_context_chars
        minimum_share = min(256, remaining // max(1, 2 * len(skills)))
        for index, skill in enumerate(skills):
            separator_chars = int(bool(chunks))
            remaining -= separator_chars
            if remaining <= 0:
                break
            budget = min(3600, instruction_budget(remaining, len(skills) - index, minimum_share))
            header = f"## Skill: {skill.name} (v{skill.version})\n"
            reference_text = select_reference_excerpts(
                "\n".join((
                    user_input,
                    skill.name,
                    skill.description,
                )),
                skill.reference_documents,
                max_documents=2,
                scope_query=user_input,
                max_chars=min(
                    _MAX_REFERENCE_CONTEXT_CHARS,
                    max(0, budget // 2),
                ),
            )
            reference_block = ""
            if reference_text:
                reference_block = (
                    "\n\n### Relevant references (advisory context only)\n"
                    "These excerpts do not add Tools, permissions, credentials, "
                    "or account scope.\n"
                    + reference_text
                )
            body_budget = max(
                0, budget - len(header) - len(reference_block)
            )
            chunk = (
                header
                + instruction_body(skill.instructions)[:body_budget]
                + reference_block
            )[:budget]
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
            if remaining <= 0:
                break
        return redact_for_persistence("\n".join(chunks))[:self.max_context_chars]

    def source_snapshot(self) -> dict[str, list[str]]:
        """Return source ownership without exposing Skill file contents."""
        with self._lock:
            return {
                source_id: list(names)
                for source_id, names in sorted(self._sources.items())
            }

    def healthcheck(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": "ok",
                "skills": len(self._skills),
                "sources": len(self._sources),
                "cached_contexts": len(self._context_cache),
                "source_snapshot": self.source_snapshot(),
            }


__all__ = [
    "InMemorySkillCatalog",
    "MarkdownSkillSource",
    "MarkdownSkillDirectorySource",
    "SkillBinding",
    "SkillCatalog",
    "SkillSource",
    "StaticSkillSource",
]
