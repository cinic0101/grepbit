"""Deadline/cancel rulers; clocks and blocking resources are controlled locally."""

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
import test_ask_contract as h

from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import ChatCompletionsPlanClient
from grepbit.adapters.mcp_server import run_request
from grepbit.application.ask import AskSettings, ask
from grepbit.application.request_lifecycle import RequestControl, RequestStopped
from grepbit.ports.grounding import GroundingModelError


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan")])
def test_budget_is_finite_and_positive(seconds):
    with pytest.raises(ValueError, match="finite_positive"):
        RequestControl(seconds)


def test_budget_decreases_and_first_stop_reason_wins():
    now = [0.0]
    control = RequestControl(10, clock=lambda: now[0])
    assert control.remaining(5) == 5
    now[0] = 8
    assert control.remaining(5) == 2
    control.stop("request_cancelled")
    now[0] = 20
    with pytest.raises(RequestStopped, match="request_cancelled"):
        control.check()


def test_cancel_before_registration_does_not_start_resource():
    control = RequestControl(5)
    control.stop("request_cancelled")
    with pytest.raises(RequestStopped):
        with control.cancellable(lambda: None):
            pytest.fail("resource started after cancellation")


def test_cancel_is_idempotent_and_old_resource_is_not_reused():
    control = RequestControl(5)
    calls = []
    with pytest.raises(RequestStopped):
        with control.cancellable(lambda: calls.append("active")):
            cb = control.stop("request_cancelled")
            assert control.stop("request_cancelled") is None
            cb()
    assert calls == ["active"]


def test_normal_resource_release_and_completed_request_ignore_late_cancel():
    control = RequestControl(5)
    with control.cancellable(lambda: pytest.fail("completed resource cancelled")):
        pass
    control.finish()
    assert control.stop("request_cancelled") is None


def test_deadline_beats_late_completion():
    now = [0.0]
    control = RequestControl(1, clock=lambda: now[0])
    now[0] = 1
    with pytest.raises(RequestStopped, match="request_timeout"):
        control.finish()


@pytest.mark.parametrize("transport_error", [False, True])
def test_no_database_or_transport_retry_after_expired_model(transport_error):
    now = [0.0]
    control = RequestControl(1, clock=lambda: now[0])

    class Planner(h._Planner):
        def propose(self, *args, **kwargs):
            now[0] = 2
            if transport_error:
                self.calls.append({})
                raise GroundingModelError("model_call_failed", 1)
            return super().propose(*args, **kwargs)

    planner = Planner(h.COUNT_OFFLINE)
    executor = h._Executor([])
    result = ask(
        "Count offline devices",
        h.services(planner, executor),
        AskSettings(as_of=h.AS_OF),
        control=control,
    )
    assert result.status == "failed" and result.reason == "request_timeout"
    assert len(planner.calls) == 1 and executor.executed == []


def test_repair_has_remaining_budget_not_a_fresh_timeout():
    now = [0.0]
    control = RequestControl(10, clock=lambda: now[0])
    calls = []

    def create(**kw):
        calls.append(kw)
        now[0] += 4
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="bad"
                        if len(calls) == 1
                        else json.dumps(h.COUNT_OFFLINE)
                    )
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fake"),
        client=client,
        control=control,
    )
    planner.propose("Count", h.SCHEMA, as_of=h.AS_OF.isoformat())
    assert [c["timeout"] for c in calls] == [10, 6]
    assert planner.last_model_repair_turns == 1


def test_no_repair_after_first_call_expires_and_owned_client_closes(monkeypatch):
    now = [0.0]
    control = RequestControl(1, clock=lambda: now[0])
    calls, closed = [], []

    def create(**kw):
        calls.append(kw)
        now[0] = 2
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="bad"))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=lambda: closed.append(True),
    )
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused", model="fake"), control=control
    )
    monkeypatch.setattr(planner._transport, "_create_client", lambda: client)
    with pytest.raises(RequestStopped, match="request_timeout"):
        planner.propose("Count", h.SCHEMA, as_of=h.AS_OF.isoformat())
    assert len(calls) == 1 and closed == [True]


async def wait_event(event):
    async with asyncio.timeout(2):
        while not event.is_set():
            await asyncio.sleep(0.001)


def test_cancelling_a_does_not_cancel_b_and_workers_exit():
    async def scenario():
        started = [threading.Event(), threading.Event()]
        release = [threading.Event(), threading.Event()]
        done = [threading.Event(), threading.Event()]
        cancelled = []

        def work(i, control):
            def cancel():
                cancelled.append(i)
                release[i].set()

            try:
                with control.cancellable(cancel):
                    started[i].set()
                    assert release[i].wait(2)
                return {"status": "answered", "owner": i}
            finally:
                done[i].set()

        a = asyncio.create_task(
            run_request("a", lambda c: work(0, c), timeout_seconds=5)
        )
        b = asyncio.create_task(
            run_request("b", lambda c: work(1, c), timeout_seconds=5)
        )
        try:
            await wait_event(started[0])
            await wait_event(started[1])
            a.cancel()
            with pytest.raises(asyncio.CancelledError):
                await a
            await wait_event(done[0])
            assert cancelled == [0] and not b.done()
            release[1].set()
            result = await b
            assert result["status"] == "answered" and result["owner"] == 1
        finally:
            for event in release:
                event.set()
            await asyncio.gather(a, b, return_exceptions=True)

    asyncio.run(scenario())


def test_timeout_returns_failed_and_cancels_active_resource():
    async def scenario():
        release, done = threading.Event(), threading.Event()

        def work(control):
            try:
                with control.cancellable(release.set):
                    assert release.wait(2)
                pytest.fail("late success after timeout")
            finally:
                done.set()

        result = await run_request("q", work, timeout_seconds=0.05)
        await wait_event(done)
        assert result["status"] == "failed" and result["reason"] == "request_timeout"
        assert result["rows"] == [] and result["request_id"]

    asyncio.run(scenario())


def test_waiting_request_cancellation_prevents_worker_start():
    async def scenario():
        task = asyncio.create_task(
            run_request(
                "q",
                lambda c: pytest.fail("cancelled before dispatch"),
                timeout_seconds=1,
            )
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
