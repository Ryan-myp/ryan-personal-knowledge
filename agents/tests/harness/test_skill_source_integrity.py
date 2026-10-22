import pytest

from agents.agent_harness import SkillBinding, StaticSkillSource
from agents.agent_harness.skills import InMemorySkillCatalog, MarkdownSkillSource


def test_markdown_source_reads_declared_identity_description_and_version(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: declared-skill\ndescription: Evidence review\n"
        "version: 2.3.4\nmetadata:\n  team: growth\n---\n\n# Different heading\n",
        encoding="utf-8",
    )
    binding, = MarkdownSkillSource.from_directory(tmp_path).list_skills()
    assert binding.name == "declared-skill"
    assert binding.description == "Evidence review"
    assert binding.version == "2.3.4"
    assert binding.metadata["team"] == "growth"


@pytest.mark.parametrize("target", ["SKILL.md", "references/escape.md"])
def test_markdown_source_rejects_symlinked_text_inputs(tmp_path, target):
    outside = tmp_path / "outside.md"
    outside.write_text("unrelated private file", encoding="utf-8")
    root = tmp_path / "package"
    root.mkdir()
    (root / "SKILL.md").write_text("# Valid package", encoding="utf-8")
    link = root / target
    link.parent.mkdir(exist_ok=True)
    if link.exists():
        link.unlink()
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        MarkdownSkillSource.from_directory(root)


def test_markdown_source_bounds_the_root_instruction_file(tmp_path):
    (tmp_path / "SKILL.md").write_text("x" * 100_001, encoding="utf-8")
    with pytest.raises(ValueError, match="limit"):
        MarkdownSkillSource.from_directory(tmp_path)


def test_registered_skill_cannot_be_changed_through_publisher_owned_dictionaries():
    metadata = {"always_on": True, "nested": {"labels": ["original"]}}
    references = {"references/a.md": "original guidance"}
    binding = SkillBinding(
        name="snapshot", instructions="stable instructions",
        metadata=metadata, reference_documents=references,
    )
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [binding]))
    references["references/a.md"] = "modified guidance"
    metadata["always_on"] = False
    metadata["nested"]["labels"].append("changed")
    stored, = catalog.list_skills()
    assert stored.metadata["always_on"] is True
    assert list(stored.metadata["nested"]["labels"]) == ["original"]
    assert stored.reference_documents["references/a.md"] == "original guidance"
    with pytest.raises(TypeError):
        stored.metadata["always_on"] = False
    with pytest.raises(TypeError):
        stored.reference_documents["references/a.md"] = "changed"


def test_skill_catalog_does_not_select_a_skill_only_because_its_long_body_mentions_a_topic():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [
        SkillBinding(
            name="billing", description="Invoices and payments",
            instructions="General background: attribution. " * 300,
        ),
        SkillBinding(
            name="measurement", description="Attribution analysis",
            instructions="Measure supported observations.",
        ),
    ]))
    context = catalog.build_context("attribution")
    assert "## Skill: measurement" in context
    assert "## Skill: billing" not in context


def test_scenario_source_scope_does_not_force_unrelated_skills():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("scenario-scope", [
        SkillBinding(name="billing", description="Invoices", instructions="UNRELATED"),
        SkillBinding(name="measurement", description="Attribution", instructions="RELEVANT"),
    ]))
    context = catalog.build_context("attribution", source_ids=["scenario-scope"])
    assert "RELEVANT" in context
    assert "UNRELATED" not in context
    assert catalog.build_context("unmatched", source_ids=["scenario-scope"]) == ""


def test_nested_identity_and_metadata_version_are_read_as_declared(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nskill:\n  name: packaged\n  description: Packaged guidance\n"
        "  metadata:\n    version: 3.2.1\n---\n# Package\n", encoding="utf-8",
    )
    binding, = MarkdownSkillSource.from_directory(tmp_path).list_skills()
    assert binding.name == "packaged"
    assert binding.version == "3.2.1"


@pytest.mark.parametrize("header", [
    "---\nname: unfinished\n",
    "---\n[]\n---\n",
    "---\nskill: text\n---\n",
    "---\nname: []\n---\n",
    "---\ndescription: []\n---\n",
    "---\nmetadata: text\n---\n",
    "---\nmetadata: &loop\n  self: *loop\n---\n",
    "---\n!!python/object/apply:os.system ['not-executed']\n---\n",
])
def test_invalid_or_recursive_frontmatter_is_rejected(tmp_path, header):
    (tmp_path / "SKILL.md").write_text(header, encoding="utf-8")
    with pytest.raises(ValueError):
        MarkdownSkillSource.from_directory(tmp_path)


def test_registration_failure_rolls_back_the_compiled_reference_index():
    catalog = InMemorySkillCatalog()
    binding = SkillBinding(name="sample", description="Attribution", instructions="unused")
    with pytest.raises(TypeError):
        catalog.register_source(StaticSkillSource("source", [binding, object()]))
    assert catalog.list_skills() == []
    catalog.register_source(StaticSkillSource("source", [binding]))
    assert "sample" in catalog.build_context("attribution")


def test_reference_aggregate_limit_is_checked_before_registration(tmp_path, monkeypatch):
    from agents.agent_harness import skills

    (tmp_path / "SKILL.md").write_text("# Guidance", encoding="utf-8")
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "a.md").write_text("a" * 20, encoding="utf-8")
    (refs / "b.md").write_text("b" * 20, encoding="utf-8")
    monkeypatch.setattr(skills, "_MAX_REFERENCE_TOTAL_CHARS", 30)
    with pytest.raises(ValueError, match="aggregate"):
        MarkdownSkillSource.from_directory(tmp_path)


@pytest.mark.parametrize("metadata", [
    "not a mapping", {1: "not a string key"}, {"bad": object()},
    {"bad": float("nan")}, {"huge": list(range(4100))},
])
def test_binding_rejects_unbounded_or_non_data_metadata(metadata):
    with pytest.raises(ValueError):
        SkillBinding(name="sample", instructions="guidance", metadata=metadata)


def test_metadata_snapshot_accepts_finite_data_and_read_errors_are_typed(tmp_path):
    from agents.agent_harness.skills.metadata import read_skill_text

    binding = SkillBinding(
        name="sample", instructions="guidance",
        metadata={"confidence": 0.8, "optional": None, "revision": 2},
    )
    assert binding.metadata["confidence"] == 0.8
    with pytest.raises(ValueError, match="UTF-8"):
        read_skill_text(tmp_path / "missing.md")


def test_repeated_skill_context_reuses_cache_but_publication_invalidates_it(monkeypatch):
    from agents.agent_harness import skills

    scans = []
    select = skills.select_reference_excerpts

    def count(*args, **kwargs):
        scans.append(True)
        return select(*args, **kwargs)

    monkeypatch.setattr(skills, "select_reference_excerpts", count)
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="measurement", description="Attribution",
        instructions="VERSION ONE", reference_documents={"references/a.md": "Attribution evidence"},
    )]))
    first = catalog.build_context("attribution", source_ids=["source"])
    assert first == catalog.build_context("attribution", source_ids=["source"])
    assert len(scans) == 1
    catalog.unregister_source("source")
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="measurement", description="Attribution", version="2.0.0",
        instructions="VERSION TWO",
    )]))
    assert "VERSION TWO" in catalog.build_context("attribution", source_ids=["source"])
    assert len(scans) == 2


def test_skill_context_cache_is_bounded_and_keeps_source_scope_separate():
    catalog = InMemorySkillCatalog(max_cached_contexts=2)
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="measurement", instructions="GUIDANCE", metadata={"always_on": True},
    )]))
    for index in range(4):
        catalog.build_context(f"question-{index}", source_ids=["source"])
    assert catalog.healthcheck()["cached_contexts"] <= 2
    assert catalog.build_context("question-3", source_ids=[]) == ""


def test_inflight_old_skill_render_cannot_repopulate_cache_after_publication(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from agents.agent_harness import skills

    entered, release = Event(), Event()
    original = skills.select_reference_excerpts

    def block(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="sample", description="Attribution", instructions="OLD",
    )]))
    with ThreadPoolExecutor(max_workers=1) as executor:
        with monkeypatch.context() as patch:
            patch.setattr(skills, "select_reference_excerpts", block)
            running = executor.submit(catalog.build_context, "attribution")
            try:
                assert entered.wait(3)
                catalog.unregister_source("source")
                catalog.register_source(StaticSkillSource("source", [SkillBinding(
                    name="sample", description="Attribution", version="2.0.0", instructions="NEW",
                )]))
            finally:
                release.set()
            assert "OLD" in running.result(timeout=5)
    assert "NEW" in catalog.build_context("attribution")


def test_query_and_reference_index_use_the_same_hyphen_tokenization():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="measurement", description="Observations", instructions="GUIDANCE",
        reference_documents={"references/evidence.md": "Disclosed click observations."},
    )]))
    assert "GUIDANCE" in catalog.build_context("disclosed-click")


def test_shared_skill_tokenization_preserves_unicode_words():
    topic = "\u03b1\u03c0\u03cc\u03b4\u03bf\u03c3\u03b7"
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="measurement", description=topic, instructions="GUIDANCE",
    )]))
    assert "GUIDANCE" in catalog.build_context(topic)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, float("nan"), float("inf")])
def test_skill_context_cache_requires_a_positive_integer_capacity(limit):
    with pytest.raises(ValueError):
        InMemorySkillCatalog(max_cached_contexts=limit)


def test_invalid_metadata_diagnostics_do_not_echo_private_header_values(tmp_path):
    import traceback

    (tmp_path / "SKILL.md").write_text(
        "---\nname: sample\nversion: PRIVATE_HEADER_VALUE\n---\n# Guidance",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as error:
        MarkdownSkillSource.from_directory(tmp_path)
    assert "PRIVATE_HEADER_VALUE" not in str(error.value)
    assert "PRIVATE_HEADER_VALUE" not in "".join(traceback.format_exception(error.value))
