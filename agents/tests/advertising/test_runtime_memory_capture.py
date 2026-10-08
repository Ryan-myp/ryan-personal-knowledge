"""Runtime event memory captures only verified live write outcomes."""

from types import SimpleNamespace

from agents.tools.advertising.application.integration_result_assembler import AdvertisingResultAssembler


class _Memory:
    def __init__(self):
        self.events = []

    def remember_runtime_event(self, summary, **kwargs):
        self.events.append((summary, kwargs))


class _Registry:
    def __init__(self):
        self.definitions = {
            "meta.create_campaign": SimpleNamespace(
                name="meta.create_campaign", namespace="meta", is_write_tool=True,
            ),
            "meta.list_campaigns": SimpleNamespace(
                name="meta.list_campaigns", namespace="meta", is_write_tool=False,
            ),
        }

    def get(self, name):
        return self.definitions[name], None


def _setup():
    memory = _Memory()
    owner = SimpleNamespace(_memory_manager=memory, registry=_Registry())
    return AdvertisingResultAssembler(owner), memory


def _request(mode="live"):
    return SimpleNamespace(
        execution_mode=mode,
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        run_id="run-42",
    )


def test_only_non_simulated_live_write_success_is_remembered():
    assembler, memory = _setup()
    assembler._remember_runtime_events(
        _request(),
        [
            {
                "tool": "meta.create_campaign",
                "platform": "meta",
                "success": True,
                "simulated": False,
                "data": {"resource_id": "campaign-private"},
            },
            {
                "tool": "meta.list_campaigns",
                "platform": "meta",
                "success": True,
                "simulated": False,
                "data": {},
            },
        ],
    )

    assert len(memory.events) == 1
    summary, event = memory.events[0]
    assert "meta.create_campaign" in summary
    assert "campaign-private" not in summary
    assert event["event_type"] == "operation_succeeded"
    assert event["dedupe_key"] == "run-42:meta.create_campaign:0"


def test_dry_run_and_simulated_writes_never_become_success_memories():
    assembler, memory = _setup()
    result = [{
        "tool": "meta.create_campaign",
        "platform": "meta",
        "success": True,
        "simulated": True,
        "data": {"mode": "dry_run"},
    }]

    assembler._remember_runtime_events(_request("dry_run"), result)
    assembler._remember_runtime_events(_request("live"), result)

    assert memory.events == []


def test_live_provider_failure_remembers_only_allowlisted_error_code():
    assembler, memory = _setup()
    assembler._remember_runtime_events(
        _request(),
        [{
            "tool": "meta.create_campaign",
            "platform": "meta",
            "success": False,
            "simulated": False,
            "error": "access_token=private-token provider payload",
            "error_detail": {
                "code": "AUTH_EXPIRED",
                "classification": "non_retriable",
            },
        }],
    )

    assert len(memory.events) == 1
    summary, event = memory.events[0]
    assert "AUTH_EXPIRED" in summary
    assert "private-token" not in summary
    assert event["event_type"] == "operation_failed"
