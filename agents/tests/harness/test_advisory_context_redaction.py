from agents.agent_harness import AgentApplication, ModelTurn, SkillBinding, StaticSkillSource
from agents.agent_harness.redaction import redact_for_persistence
from agents.agent_harness.skills import InMemorySkillCatalog


def test_skill_context_cache_never_retains_labelled_credentials():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("source", [SkillBinding(
        name="review", description="Review",
        instructions="Use api_key=PRIVATE_API_VALUE and app_secret=PRIVATE_APP_VALUE",
        metadata={"always_on": True},
        reference_documents={"references/setup.md": "Review client_secret=PRIVATE_CLIENT_VALUE"},
    )]))
    first = catalog.build_context("review")
    assert first == catalog.build_context("review")
    for value in ("PRIVATE_API_VALUE", "PRIVATE_APP_VALUE", "PRIVATE_CLIENT_VALUE"):
        assert value not in first
        assert value.lower() not in str(catalog._reference_index)


def test_context_provider_prompt_is_redacted_at_the_model_message_boundary():
    seen = []

    class Context:
        def build_context(self, *_args):
            return {"prompt": "api_key=PRIVATE_PROVIDER_VALUE"}

    class Model:
        def complete(self, messages, _tools, request):
            seen.append((str(messages), str(request.context)))
            return ModelTurn(content="ready")

    app = AgentApplication.create(model=Model(), context_provider=Context())
    try:
        assert app.prompt("hello").reply == "ready"
    finally:
        app.close()
    assert seen
    assert "PRIVATE_PROVIDER_VALUE" not in str(seen)


def test_equivalent_credential_names_are_redacted_without_hiding_token_budgets():
    text = (
        'apiKey="PRIVATE_A" app_secret=PRIVATE_B api-key=PRIVATE_C '
        "input_tokens=1200 max_output_tokens=300"
    )
    safe = redact_for_persistence(text)
    assert "PRIVATE_" not in safe
    assert "input_tokens=1200" in safe
    assert "max_output_tokens=300" in safe


def test_numeric_token_budgets_and_usage_are_not_mistaken_for_credentials():
    seen, events = {}, []

    class Model:
        def complete(self, _messages, _tools, request):
            seen["budget"] = request.context["max_output_tokens"]
            return ModelTurn(content="ready", usage={"input_tokens": 2, "output_tokens": 1})

    app = AgentApplication.create(
        model=Model(), max_output_tokens=10, event_callback=events.append,
    )
    try:
        assert app.prompt("hello").reply == "ready"
    finally:
        app.close()
    assert seen["budget"] == 10
    usage = next(event["usage"] for event in events if event["type"] == "model_usage")
    assert usage["input_tokens"] == 2
    assert usage["output_tokens"] == 1


def test_counter_exception_is_numeric_only_and_never_applies_to_access_tokens():
    value = redact_for_persistence({
        "input_tokens": 12, "max_output_tokens": 100,
        "total_tokens": "PRIVATE_VALUE", "access_token": 12345,
    })
    assert value["input_tokens"] == 12
    assert value["max_output_tokens"] == 100
    assert value["total_tokens"] == "<redacted>"
    assert value["access_token"] == "<redacted>"


def test_readonly_mappings_and_tuples_are_redacted_without_changing_tuple_scope():
    from types import MappingProxyType

    value = redact_for_persistence({
        "metadata": MappingProxyType({"api_key": "PRIVATE_MAPPING"}),
        "rows": ({"client_secret": "PRIVATE_TUPLE"},),
        "scope": ("one", "two"),
    })
    assert "PRIVATE_" not in str(value)
    assert value["scope"] == ("one", "two")


def test_authorization_scheme_does_not_leave_the_credential_after_redacting_its_name():
    for scheme in ("Bearer", "Basic"):
        safe = redact_for_persistence(f'curl -H "Authorization: {scheme} PRIVATE_AUTH_VALUE"')
        assert "PRIVATE_AUTH_VALUE" not in safe
