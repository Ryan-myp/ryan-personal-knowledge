from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.agent_harness import (
    AgentApplication,
    ModelTurn,
    StaticToolSource,
    ToolArgumentBinding,
    ToolBinding,
    ToolCall,
    TurnRequest,
)
from agents.agent_harness.core.context import ContextQuery
from agents.agent_harness.core.interfaces import (
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.agent_platform.tools.knowledge import knowledge_search_tool_source
from agents.agent_platform.tools.readonly_recipe import readonly_recipe_tool_source
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)


class _KnowledgeProvider:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.queries = []

    def query_context(self, request: ContextQuery):
        self.queries.append(request)
        return self.documents


def _execute(source, arguments, *, tenant_id="tenant-a"):
    binding = source.list_bindings()[0]
    context = SimpleNamespace(
        request=SimpleNamespace(
            tenant_id=tenant_id,
            user_id="user-a",
            principal=SimpleNamespace(tenant_id=tenant_id),
        ),
        metadata={"principal_tenant_id": tenant_id},
    )
    return binding.executor.execute(context, arguments)


def test_knowledge_search_uses_bounded_context_and_trusted_tenant_scope():
    provider = _KnowledgeProvider([
        {
            "document_id": "meta-basics",
            "title": "Meta campaign basics",
            "platform": "meta",
            "excerpt": "Campaign guidance.",
            "source_ref": "wiki://meta-basics",
        },
    ])
    source = knowledge_search_tool_source(
        provider, required_permission="ads.read",
    )
    binding = source.list_bindings()[0]

    result = binding.executor.execute(
        SimpleNamespace(
            request=SimpleNamespace(
                tenant_id="tenant-trusted",
                principal=SimpleNamespace(tenant_id="tenant-trusted"),
            ),
            metadata={"principal_tenant_id": "tenant-trusted"},
        ),
        {
            "query": "Meta campaign",
            "namespaces": ["meta"],
            "limit": 999,
            "max_excerpt_chars": 100_000,
            "tenant_id": "tenant-attacker",
        },
    )

    assert result.success is True
    assert provider.queries == [
        ContextQuery(
            text="Meta campaign",
            namespaces=("meta",),
            tenant_id="tenant-trusted",
            limit=10,
            max_excerpt_chars=1200,
        )
    ]
    assert result.data["results"][0]["document_id"] == "meta-basics"
    assert "tenant_id" not in binding.definition.input_schema.properties
    assert binding.definition.required_permissions == ["ads.read"]
    assert binding.definition.is_read_tool is True
    assert binding.definition.scope_required is False
    assert binding.definition.result_items_key == "results"


def test_knowledge_search_fails_closed_without_trusted_tenant_context():
    source = knowledge_search_tool_source(
        _KnowledgeProvider(), required_permission="docs.read",
    )

    result = _execute(
        source,
        {"query": "campaign", "tenant_id": "caller-controlled"},
        tenant_id="",
    )

    assert result.success is False
    assert "可信" in str(result.error)


def test_knowledge_search_does_not_trust_request_or_generic_metadata_tenant():
    source = knowledge_search_tool_source(
        _KnowledgeProvider(), required_permission="docs.read",
    )
    binding = source.list_bindings()[0]

    result = binding.executor.execute(
        SimpleNamespace(
            request=SimpleNamespace(tenant_id="caller-controlled"),
            metadata={"tenant_id": "caller-controlled"},
        ),
        {"query": "campaign"},
    )

    assert result.success is False
    assert "可信" in str(result.error)


def test_knowledge_search_prefers_trusted_principal_tenant():
    provider = _KnowledgeProvider()
    source = knowledge_search_tool_source(
        provider, required_permission="ads.read",
    )
    binding = source.list_bindings()[0]

    result = binding.executor.execute(
        SimpleNamespace(
            request=SimpleNamespace(
                tenant_id="untrusted-request-tenant",
                principal=SimpleNamespace(tenant_id="tenant-principal"),
            ),
            metadata={"tenant_id": "untrusted-metadata-tenant"},
        ),
        {"query": "campaign"},
    )

    assert result.success is True
    assert provider.queries[0].tenant_id == "tenant-principal"


def test_knowledge_search_returns_bounded_citations_without_credential_fields():
    provider = _KnowledgeProvider([{
        "document_id": "safe-doc",
        "title": "Safe title",
        "platform": "meta",
        "excerpt": "Use this credential: refresh_token=private-value",
        "source_ref": "wiki://safe-doc",
        "access_token": "must-never-be-returned",
        "citation": {
            "document_id": "safe-doc",
            "title": "Safe title",
            "access_token": "must-never-be-returned",
        },
    }])
    source = knowledge_search_tool_source(
        provider, required_permission="ads.read",
    )

    result = _execute(source, {"query": "credential"})

    assert result.success is True
    item = result.data["results"][0]
    assert "access_token" not in item
    assert "access_token" not in item["citation"]
    assert "private-value" not in item["excerpt"]


def test_recipe_filters_projects_sorts_and_groups_without_mutating_input():
    source = readonly_recipe_tool_source(required_permission="ads.read")
    records = [
        {"platform": "meta", "status": "paused", "budget": 20},
        {"platform": "google", "status": "enabled", "budget": 50},
        {"platform": "meta", "status": "paused", "budget": 40},
    ]
    original = [dict(item) for item in records]

    result = _execute(source, {
        "records": records,
        "steps": [
            {
                "op": "filter",
                "field": "status",
                "operator": "eq",
                "value": "paused",
            },
            {"op": "sort", "field": "budget", "direction": "desc"},
            {"op": "select", "fields": ["platform", "budget"]},
            {"op": "group_count", "field": "platform"},
        ],
    })

    assert result.success is True
    assert result.data["records"] == [
        {"value": "meta", "count": 2},
    ]
    assert result.data["count"] == 1
    assert result.data["steps_applied"] == 4
    assert records == original


def test_recipe_supports_bounded_numeric_aggregation():
    source = readonly_recipe_tool_source(required_permission="ads.read")

    result = _execute(source, {
        "records": [
            {"platform": "meta", "spend": 12},
            {"platform": "meta", "spend": 18},
        ],
        "steps": [{"op": "aggregate", "function": "sum", "field": "spend"}],
    })

    assert result.success is True
    assert result.data["aggregate"] == {
        "function": "sum",
        "field": "spend",
        "value": 30,
        "sample_count": 2,
    }


def test_recipe_rejects_unregistered_code_ops_secrets_and_resource_excess():
    source = readonly_recipe_tool_source(required_permission="ads.read")

    code_result = _execute(source, {
        "records": [{"status": "paused"}],
        "steps": [{"op": "python", "code": "__import__('os').system('id')"}],
    })
    secret_result = _execute(source, {
        "records": [{"access_token": "must-not-echo"}],
        "steps": [{"op": "limit", "limit": 1}],
    })
    too_many_steps = _execute(source, {
        "records": [{"status": "paused"}],
        "steps": [{"op": "limit", "limit": 1}] * 11,
    })
    bad_path = _execute(source, {
        "records": [{"status": "paused"}],
        "steps": [{"op": "filter", "field": "__class__.__mro__",
                   "operator": "exists", "value": True}],
    })

    assert code_result.success is False
    assert "不支持" in str(code_result.error)
    assert secret_result.success is False
    assert "must-not-echo" not in str(secret_result.error)
    assert too_many_steps.success is False
    assert bad_path.success is False


def test_recipe_rejects_malformed_values_and_oversized_records():
    source = readonly_recipe_tool_source(required_permission="ads.read")

    malformed_filter = _execute(source, {
        "records": [{"name": "campaign"}],
        "steps": [{
            "op": "filter",
            "field": "name",
            "operator": "contains",
            "value": ["campaign"],
        }],
    })
    too_many_records = _execute(source, {
        "records": [{"id": index} for index in range(201)],
        "steps": [],
    })

    assert malformed_filter.success is False
    assert too_many_records.success is False


def test_recipe_redacts_credentials_embedded_in_output_strings():
    source = readonly_recipe_tool_source(required_permission="ads.read")

    result = _execute(source, {
        "records": [{"note": "refresh_token=private-value"}],
        "steps": [],
    })

    assert result.success is True
    assert "private-value" not in str(result.data)


@pytest.mark.parametrize(
    "operator,record,expected,expected_count",
    [
        ("eq", {"value": "same"}, "same", 1),
        ("neq", {"value": "same"}, "other", 1),
        ("contains", {"value": "campaign alpha"}, "alpha", 1),
        ("contains", {"value": ["a", "b"]}, "b", 1),
        ("in", {"value": "a"}, ["a", "b"], 1),
        ("gt", {"value": 3}, 2, 1),
        ("gte", {"value": 3}, 3, 1),
        ("lt", {"value": 3}, 4, 1),
        ("lte", {"value": 3}, 3, 1),
        ("exists", {"value": None}, True, 1),
        ("exists", {}, False, 1),
        ("eq", {}, None, 1),
    ],
)
def test_recipe_filter_operators_have_bounded_expected_results(
    operator, record, expected, expected_count,
):
    source = readonly_recipe_tool_source(required_permission="ads.read")

    result = _execute(source, {
        "records": [record],
        "steps": [{
            "op": "filter",
            "field": "value",
            "operator": operator,
            "value": expected,
        }],
    })

    assert result.success is True
    assert result.data["count"] == expected_count


@pytest.mark.parametrize(
    "function,expected",
    [
        ("avg", 3),
        ("min", 2),
        ("max", 4),
        ("count", 2),
    ],
)
def test_recipe_supports_numeric_aggregate_functions(function, expected):
    source = readonly_recipe_tool_source(required_permission="ads.read")

    result = _execute(source, {
        "records": [{"value": 2}, {"value": 4}, {"other": 10}],
        "steps": [{"op": "aggregate", "function": function, "field": "value"}],
    })

    assert result.success is True
    assert result.data["aggregate"]["value"] == expected


def test_recipe_rejects_invalid_shapes_and_input_output_size_excess():
    source = readonly_recipe_tool_source(required_permission="ads.read")
    deep_record = {"value": "leaf"}
    for _ in range(10):
        deep_record = {"nested": deep_record}

    invalid_results = [
        _execute(source, {"records": [], "unexpected": True}),
        _execute(source, {"records": {}}),
        _execute(source, {"records": ["not-an-object"]}),
        _execute(source, {"records": [deep_record]}),
        _execute(source, {"records": [{"value": float("nan")}]}),
        _execute(source, {"records": [{"value": "x" * 260_000}]}),
        _execute(source, {
            "records": [{"value": "x" * 1_000} for _ in range(40)],
            "steps": [],
        }),
    ]

    assert all(not result.success for result in invalid_results)


def test_tool_selector_exposes_only_explicit_readonly_capabilities():
    knowledge_source = knowledge_search_tool_source(
        _KnowledgeProvider(), required_permission="ads.read",
    )
    recipe_source = readonly_recipe_tool_source(required_permission="ads.read")
    knowledge_tool = knowledge_source.list_bindings()[0].definition
    recipe_tool = recipe_source.list_bindings()[0].definition

    provider_read = SimpleNamespace(
        name="meta_list_campaigns",
        namespace="meta",
        action="list",
        resource_type="campaign",
        description="List Meta campaigns",
        intent_types=["list_campaigns"],
        intent_aliases=["查询 Meta campaign 列表"],
        effect_class="read",
        input_schema={"properties": {}},
    )
    selected = ToolSelector().select_relevant(
        "在知识库中搜索 Meta campaign 暂停规则",
        [knowledge_tool, recipe_tool, provider_read],
    )

    assert [tool.name for tool in selected] == ["agent_knowledge_search"]
    selected = ToolSelector().select_relevant(
        "知识库检索：Meta campaign 暂停规则",
        [knowledge_tool, recipe_tool, provider_read],
    )

    assert [tool.name for tool in selected] == ["agent_knowledge_search"]
    selected = ToolSelector().select_relevant(
        "汇总刚才查询的结果",
        [knowledge_tool, recipe_tool, provider_read],
    )
    assert [tool.name for tool in selected] == ["agent_readonly_recipe"]


def test_knowledge_and_recipe_compose_inside_the_existing_harness_run():
    provider = _KnowledgeProvider([
        {
            "document_id": "meta-rules",
            "title": "Meta rules",
            "platform": "meta",
            "excerpt": "Keep campaigns paused during validation.",
            "source_ref": "wiki://meta-rules",
        },
        {
            "document_id": "google-rules",
            "title": "Google rules",
            "platform": "google",
            "excerpt": "Use a test account.",
            "source_ref": "wiki://google-rules",
        },
    ])
    observed_toolsets = []

    class Model:
        def complete(self, messages, tools, _request):
            observed_toolsets.append({tool.name for tool in tools})
            if not any(message.role == "tool" for message in messages):
                return ModelTurn(tool_calls=(
                    ToolCall(
                        id="search-1",
                        name="agent_knowledge_search",
                        arguments={"query": "campaign rules"},
                    ),
                    ToolCall(
                        id="recipe-1",
                        name="agent_readonly_recipe",
                        arguments={
                            "steps": [{"op": "group_count", "field": "platform"}],
                        },
                        depends_on=("search-1",),
                        argument_bindings=(
                            ToolArgumentBinding(
                                target_field="records",
                                source_call_id="search-1",
                                source_path="data.results",
                            ),
                        ),
                    ),
                ))
            return ModelTurn(content="Found one Meta and one Google knowledge item.")

    app = AgentApplication.create(
        model=Model(),
        tool_execution="sequential",
        before_tool_call=lambda _context: None,
    )
    app.register_tool_source(knowledge_search_tool_source(
        provider, required_permission="ads.read",
    ))
    app.register_tool_source(readonly_recipe_tool_source(
        required_permission="ads.read",
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="在知识库中搜索 campaign rules 并按 platform 汇总",
            user_id="user-a",
            tenant_id="tenant-a",
            principal=SimpleNamespace(
                user_id="user-a",
                tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ))
    finally:
        app.close()

    assert result.status.value == "succeeded"
    assert provider.queries[0].tenant_id == "tenant-a"
    assert any(
        {"agent_knowledge_search", "agent_readonly_recipe"} <= toolset
        for toolset in observed_toolsets
    )


def test_advertising_chat_searches_knowledge_instead_of_provider_api():
    provider = _KnowledgeProvider([{
        "document_id": "meta-paused",
        "title": "Meta paused state",
        "platform": "meta",
        "excerpt": "Validation campaigns should remain paused.",
        "source_ref": "wiki://meta-paused",
    }])

    class Model:
        def __init__(self):
            self.toolsets = []

        def complete(self, messages, tools, _request):
            self.toolsets.append({tool.name for tool in tools})
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="Campaigns should remain paused.")
            return ModelTurn(tool_calls=(ToolCall(
                id="knowledge-search",
                name="agent_knowledge_search",
                arguments={
                    "query": "Meta campaign pause rules",
                    "namespaces": ["meta"],
                },
            ),))

    model = Model()
    runtime = AdvertisingComposition(
        knowledge_provider=provider,
        llm_client=model,
        require_llm=True,
        start_background_workers=False,
    )
    runtime.registry.register_source(StaticToolSource(
        "test:meta-query",
        [ToolBinding(
            ToolDefinition(
                name="meta_list_campaigns",
                skill="meta",
                namespace="meta",
                description="List Meta campaigns",
                input_schema=ToolSchema(properties={}),
                action="list",
                resource_type="campaign",
                intent_types=["campaign_list"],
                intent_aliases=["查询 Meta campaign 列表"],
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                required_permissions=["ads.read"],
                scope_required=False,
            ),
            lambda _context, _arguments: ToolResult.ok({"campaigns": []}),
        )],
    ))
    principal = RequestPrincipal(
        user_id="user-a",
        tenant_id="tenant-trusted",
        permissions=frozenset({"ads.read"}),
    )
    try:
        result = runtime.run(
            "在知识库中搜索 Meta campaign 暂停规则",
            user_id="user-a",
            tenant_id="tenant-trusted",
            principal=principal,
        )
    finally:
        runtime.close(wait=True)

    assert result["status"] == "succeeded", result
    assert model.toolsets
    assert "agent_knowledge_search" in model.toolsets[0]
    assert "meta_list_campaigns" not in model.toolsets[0]
    assert provider.queries
    assert all(query.tenant_id == "tenant-trusted" for query in provider.queries)
