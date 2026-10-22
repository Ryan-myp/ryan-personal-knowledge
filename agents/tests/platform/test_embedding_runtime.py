from threading import Event

import pytest

from agents.agent_platform.data.embedding_runtime import EmbeddingRunner


def test_timed_out_embedding_cannot_create_an_unbounded_backlog():
    entered = Event()
    release = Event()
    runner = EmbeddingRunner(max_workers=1)

    def blocked(_texts):
        entered.set()
        release.wait(2)
        return [[1.0, 0.0]]

    try:
        with pytest.raises(TimeoutError):
            runner.embed(blocked, ["query"], timeout=0.01)
        assert entered.is_set()
        with pytest.raises(TimeoutError, match="capacity"):
            runner.embed(blocked, ["another"], timeout=0.01)
        assert runner.metrics()["in_flight"] == 1
    finally:
        release.set()
        runner.close()
    assert runner.metrics()["in_flight"] == 0


def test_embedding_capacity_is_returned_after_provider_failure():
    runner = EmbeddingRunner(max_workers=1)

    def fail(_texts):
        raise RuntimeError("provider unavailable")

    try:
        with pytest.raises(RuntimeError):
            runner.embed(fail, ["query"], timeout=1)
        assert runner.embed(lambda _: [[1.0]], ["query"], timeout=1) == [[1.0]]
    finally:
        runner.close()


def test_closed_runner_rejects_new_work_and_returns_its_slot():
    runner = EmbeddingRunner(max_workers=1)
    runner.close()
    with pytest.raises(RuntimeError, match="closed"):
        runner.embed(lambda _: [[1.0]], ["query"], timeout=1)
    assert runner.metrics()["in_flight"] == 0


def test_submit_failure_returns_capacity_and_next_request_can_run(monkeypatch):
    runner = EmbeddingRunner(max_workers=1)
    original = runner._executor.submit

    def fail(*args, **kwargs):
        raise RuntimeError("controlled submission failure")

    try:
        monkeypatch.setattr(runner._executor, "submit", fail)
        with pytest.raises(RuntimeError):
            runner.embed(lambda _: [[1.0]], ["query"], timeout=1)
        assert runner.metrics()["in_flight"] == 0
        monkeypatch.setattr(runner._executor, "submit", original)
        assert runner.embed(lambda _: [[1.0]], ["next"], timeout=1) == [[1.0]]
    finally:
        runner.close()


def test_enqueued_job_must_not_execute_if_submit_raises(monkeypatch):
    runner = EmbeddingRunner(max_workers=1)
    queued = []
    called = []
    original = runner._executor.submit

    def enqueue_then_fail(method, *args, **kwargs):
        queued.append((method, args, kwargs))
        raise RuntimeError("thread creation failed after enqueue")

    try:
        monkeypatch.setattr(runner._executor, "submit", enqueue_then_fail)
        with pytest.raises(RuntimeError):
            runner.embed(lambda _: called.append("provider"), ["query"], timeout=1)
        assert runner.metrics()["in_flight"] == 0
        method, args, kwargs = queued[0]
        method(*args, **kwargs)
        assert called == []
        assert runner.metrics()["in_flight"] == 0
        monkeypatch.setattr(runner._executor, "submit", original)
        assert runner.embed(lambda _: [[2.0]], ["next"], timeout=1) == [[2.0]]
    finally:
        runner.close()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_embedding_timeout_must_be_positive_and_finite(timeout):
    runner = EmbeddingRunner(max_workers=1)
    try:
        with pytest.raises(ValueError):
            runner.embed(lambda _: [], ["query"], timeout=timeout)
    finally:
        runner.close()
