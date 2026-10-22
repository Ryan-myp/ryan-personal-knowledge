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


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_embedding_timeout_must_be_positive_and_finite(timeout):
    runner = EmbeddingRunner(max_workers=1)
    try:
        with pytest.raises(ValueError):
            runner.embed(lambda _: [], ["query"], timeout=timeout)
    finally:
        runner.close()
