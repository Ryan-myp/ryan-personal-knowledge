"""Application-neutral Skill catalog and standard Markdown Skill source."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .reference_selection import select_reference_excerpts


_REFERENCE_SUFFIXES = frozenset({
    ".md", ".markdown", ".txt", ".yaml", ".yml", ".json",
})
_MAX_REFERENCE_FILES = 128
_MAX_REFERENCE_CHARS = 100_000
_MAX_REFERENCE_CONTEXT_CHARS = 1_200


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
        content = skill_file.read_text(encoding="utf-8")
        name = root.name
        description = ""
        first_heading = re.search(r"(?m)^#\s+(.+?)\s*$", content)
        if first_heading:
            description = first_heading.group(1).strip()
        reference_documents = cls._read_reference_documents(root)
        return cls(
            source_id or f"markdown:{name}",
            [SkillBinding(
                name=name,
                instructions=content,
                description=description,
                metadata={"path": str(skill_file)},
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
        candidates = sorted(reference_root.rglob("*"))
        for path in candidates:
            if path.is_symlink() or not path.is_file():
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
    ) -> None:
        if max_context_chars <= 0 or max_skills <= 0:
            raise ValueError("Skill catalog limits must be positive")
        self.max_context_chars = int(max_context_chars)
        self.max_skills = int(max_skills)
        self._lock = threading.RLock()
        self._skills: dict[str, SkillBinding] = {}
        self._sources: dict[str, list[str]] = {}

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
                self._sources[source_id] = list(names)
            except Exception:
                for name in names:
                    self._skills.pop(name, None)
                raise
        return names

    def unregister_source(self, source_id: str) -> list[str]:
        with self._lock:
            names = list(self._sources.pop(str(source_id), []))
            for name in names:
                self._skills.pop(name, None)
            return names

    def list_skills(self) -> list[SkillBinding]:
        with self._lock:
            return list(self._skills.values())

    @staticmethod
    def _score(skill: SkillBinding, terms: set[str]) -> int:
        haystack = " ".join(
            (
                skill.name,
                skill.description,
                skill.instructions,
                " ".join(skill.reference_documents.keys()),
            )
        ).casefold()
        return sum(1 for term in terms if term and term in haystack)

    def build_context(
        self,
        user_input: str,
        *,
        source_ids: Sequence[str] | None = None,
    ) -> str:
        terms = {
            token.casefold()
            for token in re.findall(r"[\w-]{2,}", str(user_input or ""))
        }
        for run in re.findall(r"[\u3400-\u9fff]+", str(user_input or "")):
            terms.update(run[index:index + 2] for index in range(len(run) - 1))
        allowed_sources = (
            {str(item).strip() for item in source_ids if str(item).strip()}
            if source_ids is not None else None
        )
        with self._lock:
            allowed_names = (
                {
                    name
                    for source_id in allowed_sources or ()
                    for name in self._sources.get(source_id, ())
                }
                if allowed_sources is not None else None
            )
            skills = sorted(
                (
                    skill for skill in self._skills.values()
                    if (
                        skill.name in allowed_names
                        if allowed_names is not None else
                        skill.metadata.get("always_on") is True or self._score(skill, terms) > 0
                    )
                ),
                key=lambda item: (-self._score(item, terms), item.name),
            )[:self.max_skills]
        chunks: list[str] = []
        remaining = self.max_context_chars
        for skill in skills:
            separator_chars = int(bool(chunks))
            remaining -= separator_chars
            if remaining <= 0:
                break
            header = f"## Skill: {skill.name} (v{skill.version})\n"
            reference_text = select_reference_excerpts(
                "\n".join((
                    user_input,
                    skill.name,
                    skill.description,
                )),
                skill.reference_documents,
                max_documents=2,
                max_chars=min(
                    _MAX_REFERENCE_CONTEXT_CHARS,
                    max(0, remaining // 3),
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
            instruction_budget = max(
                0, remaining - len(header) - len(reference_block)
            )
            chunk = (
                header
                + skill.instructions.strip()[:instruction_budget]
                + reference_block
            )[:remaining]
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
            if remaining <= 0:
                break
        return "\n".join(chunks)

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
