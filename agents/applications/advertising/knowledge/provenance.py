"""Generic source provenance inference for Markdown Knowledge documents."""

from __future__ import annotations

from pathlib import PurePosixPath


_CODE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java",
    ".js", ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".sh",
    ".sql", ".swift", ".ts", ".tsx",
}


def infer_source_kind(source_ref: str, source: str = "") -> str:
    """Classify provenance without depending on a product or repository layout."""
    reference = str(source_ref or "").strip().lower()
    owner = str(source or "").strip().lower()
    if reference.startswith(("http://", "https://")):
        return "official"
    if reference.startswith(("raw://", "upload://", "managed://")) or "user" in owner:
        return "user"
    path = reference.removeprefix("code://").split("?", 1)[0].rstrip("/")
    if PurePosixPath(path).suffix in _CODE_SUFFIXES or reference.startswith("code://"):
        return "code"
    if reference:
        return "internal"
    return "inferred"


__all__ = ["infer_source_kind"]
