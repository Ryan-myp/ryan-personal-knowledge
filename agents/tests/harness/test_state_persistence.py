def test_agent_has_one_state_persistence_owner():
    from agents.agent_harness import AgentApplication, ModelTurn
    from agents.agent_harness.state_persistence import AgentStatePersistence

    app = AgentApplication.create(model=lambda *_: ModelTurn(content="done"))
    assert isinstance(app.agent._state_io, AgentStatePersistence)
    assert app.prompt("hello").reply == "done"
