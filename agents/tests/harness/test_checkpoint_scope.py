"""A checkpoint is bound to the same trusted tenant/user/session as its Run."""

import pytest

from agents.agent_harness import AgentApplication, ModelTurn, RunStatus


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other-tenant"),
        ("user_id", "other-user"),
        ("session_id", "other-session"),
    ],
)
def test_resume_rejects_a_checkpoint_from_another_principal_or_session(field, value):
    calls = []
    checkpoint = {
        "tenant_id": "tenant",
        "user_id": "user",
        "session_id": "session",
        "messages": [{"role": "user", "content": "private checkpoint text"}],
    }
    checkpoint[field] = value

    class Checkpoints:
        def load_checkpoint(self, _run_id):
            return checkpoint

    def model(messages, _tools, _request):
        calls.append(messages)
        return ModelTurn(content="done")

    app = AgentApplication.create(model=model, checkpoint_store=Checkpoints())
    result = app.prompt(
        "resume",
        tenant_id="tenant",
        user_id="user",
        session_id="session",
        context={"resume_from_checkpoint": True, "resume_run_id": "foreign-run"},
    )
    assert result.status == RunStatus.FAILED
    assert not calls
    assert "private checkpoint text" not in str(result.to_dict())


@pytest.mark.parametrize("failure", ["missing", "malformed", "unavailable"])
def test_explicit_resume_does_not_start_fresh_when_restore_fails(failure):
    calls = []

    class Checkpoints:
        def load_checkpoint(self, _run_id):
            if failure == "unavailable":
                raise OSError("private storage diagnostic")
            return [] if failure == "malformed" else None

    app = AgentApplication.create(
        model=lambda *_: calls.append("model") or ModelTurn(content="done"),
        checkpoint_store=Checkpoints(),
    )
    result = app.prompt(
        "resume",
        session_id="session",
        context={"resume_from_checkpoint": True, "resume_run_id": "lost-run"},
    )
    assert result.status == RunStatus.RECOVERY_REQUIRED
    assert not calls
    assert "private storage diagnostic" not in str(result.to_dict())
