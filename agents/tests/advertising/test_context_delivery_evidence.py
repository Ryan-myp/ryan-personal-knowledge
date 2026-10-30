import json
from types import SimpleNamespace

from agents.applications.advertising.integrations.integration import AdvertisingContextProvider
from agents.applications.advertising.integrations.ad_turn_context import AdTurnContextService
from agents.applications.advertising.run.ad_run_projection import AdvertisingRunProjection
from agents.applications.advertising.run.ad_runtime_context import AdvertisingRuntimeContext
from agents.evals.advertising.skill_up_engine import _structured_evidence
from agents.agent_harness import ModelTurn, TurnRequest
from agents.evals.advertising.skill_up_engine import run
from agents.tests.advertising.harness_models import ScriptedHarnessModel


def test_dynamic_tool_guidance_refreshes_once_per_tool_set_and_cleans_up(monkeypatch):
    calls = []
    def guidance(_query, tools, **_kwargs):
        calls.append([tool.name for tool in tools])
        return "新技能:" + ",".join(calls[-1])
    owner = SimpleNamespace(
        tool_selector=SimpleNamespace(build_selected_skill_context=guidance),
        _sessions={},
    )
    provider = AdvertisingContextProvider(owner)
    monkeypatch.setattr(provider, "build_context", lambda *_: {
        "skill_context": {"conversation_state": "用户约束"},
        "structured_input": {}, "capability_catalog": "",
    })
    request = TurnRequest("继续", run_id="r", tenant_id="t")
    first = SimpleNamespace(name="read", contract_version="1", skill_refs=[])
    second = SimpleNamespace(name="analyze", contract_version="1", skill_refs=["analysis"])
    assert "新技能:read" in provider.build_tool_context(request, [], [first])["prompt"]
    assert "新技能:analyze" in provider.build_tool_context(request, [], [second])["prompt"]
    assert "用户约束" in provider.build_tool_context(request, [], [second])["prompt"]
    assert calls == [["read"], ["analyze"]]
    provider.cleanup(request)
    assert not provider._selected_contexts


def test_selected_guidance_refreshes_budget_and_bounds_new_text(monkeypatch):
    owner = SimpleNamespace(_sessions={}, tool_selector=SimpleNamespace(
        build_selected_skill_context=lambda *_args, **_kwargs: "指导" * 10000,
    ))
    provider = AdvertisingContextProvider(owner)
    monkeypatch.setattr(provider, "build_context", lambda *_: {
        "skill_context": {"context_budget": {"aggregate_used": 999999}},
        "structured_input": {}, "capability_catalog": "",
    })
    result = provider.build_tool_context(TurnRequest("分析", run_id="bounded"), [], [])
    context = result["skill_context"]
    assert len(context["expert_knowledge"]) == 6000
    assert context["context_budget"]["aggregate_used"] == 6000
    assert context["context_budget"]["truncated"]["expert_knowledge"]


def test_rendered_context_records_only_complete_delivered_knowledge():
    prompt, evidence = AdvertisingContextProvider._render_context({
        "expert_knowledge": "g" * 6000,
        "publisher_context": "p" * 3500,
        "knowledge": [
            {"document_id": f"doc-{index}", "excerpt": "x" * 1200}
            for index in range(8)
        ],
    })
    block = prompt.split("Retrieved knowledge:\n", 1)[1].split("\n\n", 1)[0]
    rows = json.loads(block)
    assert rows
    assert [item["document_id"] for item in evidence["documents"]] == [
        item["document_id"] for item in rows
    ]
    assert evidence["source"] == "automatic_rag"
    assert evidence["prompt_chars"] == len(block)
    assert evidence["claims_answer_grounded"] is False


def test_no_budget_or_no_records_cannot_claim_knowledge_delivery():
    evidence = AdvertisingContextProvider._append_advisory_context(
        [],
        {"knowledge": [{"document_id": "doc", "excerpt": "text"}]},
        10,
    )
    assert evidence["documents"] == []
    _, empty = AdvertisingContextProvider._render_context({})
    assert empty["documents"] == []


def test_local_catalog_context_preserves_scope_but_omits_unrelated_advisory_documents(monkeypatch):
    provider = AdvertisingContextProvider(SimpleNamespace())
    session = SimpleNamespace(ctx=SimpleNamespace(metadata={"skill_context": {
        "expert_knowledge": "unrelated-expert-instructions-" * 200,
        "publisher_context": "unrelated-blueprint-details-" * 100,
        "knowledge": [{"document_id": "unrelated-doc", "excerpt": "general advice"}],
        "memory_context": "Use the current template draft.",
    }}))
    monkeypatch.setattr(provider, "_prepare_context_session", lambda *_: session)
    monkeypatch.setattr(provider, "_structured_input", lambda *_: {"account_id": "selected-account"})
    monkeypatch.setattr(provider, "_capability_catalog", lambda *_: "registered local template tools")
    request = TurnRequest(
        "列出模板", run_id="catalog", context={"_agent_local_catalog": True},
    )
    result = provider.build_context(request, [])
    assert "selected-account" in result["prompt"]
    assert "Use the current template draft." in result["prompt"]
    assert "unrelated-expert" not in result["prompt"]
    assert "unrelated-blueprint" not in result["prompt"]
    assert result["knowledge_context"]["documents"] == []


def test_aggregate_budget_counts_serialized_knowledge_not_just_strings():
    context = {
        **{key: "x" * limit for key, limit in AdTurnContextService._CONTEXT_LIMITS.items()
           if key != "knowledge"},
        "knowledge": [{"document_id": "doc", "excerpt": "k" * 5000}],
    }
    truncated = {}
    used = AdTurnContextService._enforce_aggregate_budget(context, truncated)
    expected = sum(
        len(value) if isinstance(value, str)
        else len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        for key, value in context.items() if key in AdTurnContextService._CONTEXT_LIMITS
    )
    assert used == expected
    assert used <= AdTurnContextService._AGGREGATE_CONTEXT_LIMIT
    assert context["knowledge"][0]["excerpt"] == "k" * 5000


def test_automatic_evidence_survives_projection_and_eval_without_faking_tool_calls():
    evidence = {
        "source": "automatic_rag", "documents": [
            {"document_id": "doc", "sha256": "a" * 64, "excerpt_chars": 4},
        ], "prompt_chars": 100, "claims_answer_grounded": False,
    }
    runtime = SimpleNamespace(_sessions={"session": SimpleNamespace(
        ctx=SimpleNamespace(metadata={"skill_context": {
            "knowledge_context": evidence, "knowledge_context_run_id": "run",
        }}),
    )})
    projected = AdvertisingRunProjection.application_state_from_run(
        runtime, {"run_id": "run"}, "session", "question",
    )
    assert projected["knowledge_context"] == evidence
    result = _structured_evidence({"reply": "answer", **projected})
    assert result["knowledge_context"] == evidence
    assert result["results"] == []


def test_rejected_new_run_cannot_reuse_previous_run_knowledge_receipts():
    runtime = SimpleNamespace(_sessions={"session": SimpleNamespace(
        ctx=SimpleNamespace(metadata={"skill_context": {
            "knowledge_context_run_id": "previous-run",
            "knowledge_context": {"documents": [{"document_id": "old-doc"}]},
        }}),
    )})
    projected = AdvertisingRunProjection.application_state_from_run(
        runtime, {"run_id": "new-run", "request_validation_error": "denied"},
        "session", "request",
    )
    assert projected["knowledge_context"] == {}


def test_composed_run_exposes_real_local_context_and_model_metrics(tmp_path):
    result = run({
        "case_id": "automatic-context",
        "prompt": "讲解程序化广告中 SSP 和 DSP 的区别，不需要账户数据。",
        "workspace": str(tmp_path),
    }, model_adapter=ScriptedHarnessModel(ModelTurn(
        content="SSP 服务供给方，DSP 服务需求方。",
        usage={"input_tokens": 10, "output_tokens": 5},
    )))
    evidence = result["metadata"]["runtime_result"]
    assert evidence["knowledge_context"]["documents"]
    assert evidence["results"] == []
    assert evidence["usage"]["input_tokens"] == 10
    assert evidence["model_metrics"]["attempts"] == 1
    assert evidence["model_metrics"]["completed"] == 1
    assert evidence["model_metrics"]["message_chars_peak"] > 0


def test_context_is_built_once_per_run_and_delivery_is_not_reused_next_run(monkeypatch):
    owner = SimpleNamespace()
    provider = AdvertisingContextProvider(owner)
    contexts = [
        {"knowledge": [{"document_id": "doc", "excerpt": "evidence"}]},
        {"knowledge": []},
    ]
    built = []

    def prepare(*_args):
        built.append(True)
        return SimpleNamespace(ctx=SimpleNamespace(metadata={"skill_context": contexts.pop(0)}))

    monkeypatch.setattr(provider, "_prepare_context_session", prepare)
    monkeypatch.setattr(provider, "_structured_input", lambda *_: {})
    monkeypatch.setattr(provider, "_capability_catalog", lambda *_: "")
    request = TurnRequest(user_input="question", run_id="first")
    first = provider.build_context(request, [])
    again = provider.build_context(request, [])
    assert first["knowledge_context"] == again["knowledge_context"]
    assert len(built) == 1
    provider.cleanup(request)
    second = provider.build_context(TurnRequest(user_input="hello", run_id="second"), [])
    assert second["knowledge_context"]["documents"] == []
    assert len(built) == 2


def test_blueprint_context_uses_canonical_namespace_contract_and_scoped_cache():
    queries = []
    runtime = SimpleNamespace(
        tool_selector=SimpleNamespace(build_context_for_input=lambda *_args, **_kwargs: {
            "namespaces": ["provider-b", "provider-a", "provider-a"],
            "needs_creation_context": True,
        }),
        creation_card_builder=SimpleNamespace(
            llm_context=lambda **kwargs: queries.append(kwargs) or "scoped blueprints",
        ),
    )
    service = AdvertisingRuntimeContext(runtime)
    assert service.build_skill_context("question", [], None, "tenant")[
        "publisher_context"
    ] == "scoped blueprints"
    service.build_skill_context("another", [], None, "tenant")
    assert queries == [{"providers": ["provider-a", "provider-b"]}]


def test_read_only_context_does_not_build_creation_blueprints():
    def forbidden(**_kwargs):
        raise AssertionError("read-only requests must not build blueprints")

    service = AdvertisingRuntimeContext(SimpleNamespace(
        tool_selector=SimpleNamespace(build_context_for_input=lambda *_args, **_kwargs: {
            "namespaces": ["example"], "needs_creation_context": False,
        }), creation_card_builder=SimpleNamespace(llm_context=forbidden),
    ))
    assert not service.build_skill_context("report", [], None, "tenant").get("publisher_context")


def test_creation_selection_is_serialized_once_but_keeps_workflow_instructions():
    selection = {"available": True, "blueprint_id": "unique-blueprint", "create_tools": ["create_parent"],
                 "preset_values": {"parent.name": "unique-preset"},
                 "resource_lookup_requirements": [{"lookup_tool": "unique-lookup"}]}
    prompt = AdvertisingContextProvider._render_prompt({}, {"creation_selection": selection})
    assert prompt.count("unique-blueprint") == 1
    assert prompt.count("unique-preset") == 1
    assert prompt.count("unique-lookup") == 1
    assert "必须完成蓝图声明的全部层级" in prompt


def test_context_build_failure_clears_previous_advisory_data():
    def failed(*_args):
        raise RuntimeError("private upstream details")

    events = []
    runtime = SimpleNamespace(
        _memory_manager=None, _build_skill_context=failed,
        registry=SimpleNamespace(list_all=lambda: []),
    )
    session = SimpleNamespace(ctx=SimpleNamespace(metadata={
        "skill_context": {"knowledge": [{"document_id": "previous", "excerpt": "old"}]},
    }))
    AdTurnContextService().prepare(
        runtime=runtime, session=session, session_id="session",
        tenant_id="tenant", user_id="user", safe_user_input="question",
        trace=SimpleNamespace(stage_status=lambda *args, **kwargs: events.append((args, kwargs))),
    )
    assert session.ctx.metadata["skill_context"] == {}
    assert events[-1][0][2] == "failed"
    assert "private upstream details" not in str(events)


def test_conversation_constraints_and_resource_evidence_survive_dense_advisory_context():
    context = {
        **{key: 'x' * limit for key, _label, limit in AdvertisingContextProvider._ADVISORY_CONTEXT_FIELDS},
        'knowledge': [{'document_id': 'guide', 'excerpt': 'knowledge ' * 500}],
        'conversation_state': 'USER_CONSTRAINT: do not change budgets',
        'conversation_task_state': 'EXACT_RESOURCE_ID: resource-42',
        'memory_context': 'USER_PREFERENCE: Chinese',
    }
    parts = []
    AdvertisingContextProvider._append_advisory_context(parts, context, 8000)
    rendered = '\n\n'.join(parts)
    assert 'USER_CONSTRAINT' in rendered
    assert 'EXACT_RESOURCE_ID' in rendered
    assert 'USER_PREFERENCE' in rendered
    assert len(rendered) <= 8000


def test_unused_skill_copy_cannot_evict_conversation_before_selected_context():
    from agents.applications.advertising.integrations.ad_turn_context import AdTurnContext
    runtime = SimpleNamespace(
        platform_application=SimpleNamespace(agent=SimpleNamespace(skill_catalog=SimpleNamespace(
            handles_managed_guidance=True))),
        registry=SimpleNamespace(list_all=lambda: []),
        _build_skill_context=lambda *_: {
            'expert_knowledge': 'unused duplicate ' * 1000,
            'publisher_context': 'p' * 3500,
            'knowledge': [{'document_id': str(i), 'excerpt': 'k' * 900} for i in range(8)],
        },
        _build_prior_tool_results_context=lambda _: 'r' * 4000,
    )
    session = SimpleNamespace(ctx=SimpleNamespace(metadata={'conversation_digest': 'RECENT_REQUEST ' * 100}))
    AdTurnContextService._store_skill_context(
        runtime=runtime, session=session, safe_user_input='continue', tenant_id='t',
        context=AdTurnContext(memory_context='m' * 2400),
    )
    context = session.ctx.metadata['skill_context']
    assert not context['expert_knowledge']
    assert 'RECENT_REQUEST' in context['conversation_digest']
