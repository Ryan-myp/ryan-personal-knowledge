"""Only verified live write outcomes enter advertising runtime memory."""

from types import SimpleNamespace

from agents.applications.advertising.run.ad_run_memory import (
    AdvertisingRunMemoryRecorder,
)


class _Memory:
    def __init__(self):
        self.events = []

    def remember_runtime_event(self, summary, **kwargs):
        self.events.append((summary, kwargs))


class _Registry:
    def __init__(self):
        self.definitions = {
            "meta_create_campaign": SimpleNamespace(
                name="meta_create_campaign", namespace="meta", is_write_tool=True,
            ),
            "meta_list_campaigns": SimpleNamespace(
                name="meta_list_campaigns", namespace="meta", is_write_tool=False,
            ),
        }

    def get(self, name):
        return self.definitions[name], None


def _setup():
    memory = _Memory()
    runtime = SimpleNamespace(_memory_manager=memory, registry=_Registry())
    return AdvertisingRunMemoryRecorder(runtime), memory


def _request(mode="live"):
    return SimpleNamespace(
        execution_mode=mode,
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        run_id="run-42",
    )


def _capture(recorder, request, results):
    recorder.capture(
        results,
        execution_mode=request.execution_mode,
        run_id=request.run_id,
        session_id=request.session_id,
        user_id=request.user_id,
        tenant_id=request.tenant_id,
    )


def test_only_non_simulated_live_write_success_is_remembered():
    recorder, memory = _setup()
    _capture(
        recorder,
        _request(),
        [
            {
                "tool": "meta_create_campaign",
                "platform": "meta",
                "success": True,
                "simulated": False,
                "data": {"resource_id": "campaign-private"},
            },
            {
                "tool": "meta_list_campaigns",
                "platform": "meta",
                "success": True,
                "simulated": False,
                "data": {},
            },
        ],
    )

    assert len(memory.events) == 1
    summary, event = memory.events[0]
    assert "meta_create_campaign" in summary
    assert "campaign-private" not in summary
    assert event["event_type"] == "operation_succeeded"
    assert event["dedupe_key"] == "run-42:meta_create_campaign:0"


def test_dry_run_and_simulated_writes_never_become_success_memories():
    recorder, memory = _setup()
    result = [{
        "tool": "meta_create_campaign",
        "platform": "meta",
        "success": True,
        "simulated": True,
        "data": {"mode": "dry_run"},
    }]

    _capture(recorder, _request("dry_run"), result)
    _capture(recorder, _request("live"), result)

    assert memory.events == []


def test_live_provider_failure_remembers_only_allowlisted_error_code():
    recorder, memory = _setup()
    _capture(
        recorder,
        _request(),
        [
            {
                "tool": "meta_create_campaign",
                "platform": "meta",
                "success": False,
                "simulated": False,
                "error": "access_token=private-token provider payload",
                "error_detail": {"code": "AUTH_EXPIRED"},
            },
            {
                "tool": "meta_create_campaign",
                "platform": "meta",
                "success": False,
                "simulated": False,
                "error_detail": {"code": "UNRECOGNIZED_PROVIDER_ERROR"},
            },
        ],
    )

    assert len(memory.events) == 1
    summary, event = memory.events[0]
    assert "AUTH_EXPIRED" in summary
    assert "private-token" not in summary
    assert event["event_type"] == "operation_failed"
    assert event["dedupe_key"] == "run-42:meta_create_campaign:0"


def test_advertising_run_service_records_live_write_outcomes():
    from agents.agent_harness import RunResult
    from agents.applications.advertising.run.ad_run_service import (
        AdvertisingRunService,
    )

    class PlatformApplication:
        @staticmethod
        def run(_request):
            return RunResult(
                run_id="run-42",
                turn_id="turn-42",
                reply="Campaign created.",
                data={"tool_results": [{
                    "name": "meta_create_campaign",
                    "content": {
                        "success": True,
                        "simulated": False,
                        "data": {"campaign_id": "private-id"},
                    },
                }]},
            )

    memory = _Memory()
    runtime = SimpleNamespace(
        platform_application=PlatformApplication(),
        registry=_Registry(),
        _memory_manager=memory,
        _sessions={},
        sessions={},
        execution_mode="dry_run",
    )

    result = AdvertisingRunService(runtime).run(
        "Create a campaign",
        session_id="session-a",
        user_id="user-a",
        tenant_id="tenant-a",
        execution_mode="live",
    )

    assert result["status"] == "succeeded"
    assert result["results"][0]["success"] is True
    assert len(memory.events) == 1
    assert "private-id" not in memory.events[0][0]
