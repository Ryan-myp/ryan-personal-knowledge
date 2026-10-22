from agents.evals.advertising.offline_sources import offline_web_search_source


def test_eval_web_search_uses_canonical_contract_but_never_claims_live_results():
    binding, = offline_web_search_source().list_bindings()
    assert binding.definition.name == "agent_web_search"
    assert binding.definition.effect_class.value == "read"
    result = binding.executor(None, {"query": "external project"})
    assert result.success is True
    assert result.simulated is True
    assert result.data["data_status"] == "simulated"
    assert result.data["results"] == []
