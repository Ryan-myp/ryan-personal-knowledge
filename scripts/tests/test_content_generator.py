from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "content_generator.py"
SPEC = importlib.util.spec_from_file_location("content_generator", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
content_generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(content_generator)


def test_generate_document_preserves_code_template_braces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generated_path = content_generator.generate_document("infra", "cache-layer")

    assert generated_path == "knowledge/infra/cache-layer-deep.md"
    generated = Path(generated_path).read_text(encoding="utf-8")
    assert "self.cache = {}" in generated


@pytest.mark.parametrize(
    ("domain", "topic"),
    [
        ("../outside", "cache-layer"),
        ("infra", "../outside"),
        (r"..\outside", "cache-layer"),
    ],
)
def test_generate_document_rejects_path_traversal(
    tmp_path,
    monkeypatch,
    domain,
    topic,
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        content_generator.generate_document(domain, topic)

    assert not (tmp_path / "outside").exists()
