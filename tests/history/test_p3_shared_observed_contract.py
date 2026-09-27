"""Specification ruler for provider-bound observed regression execution (#70)."""
import unittest
from unittest.mock import patch

from tools import p3_assets, p3_eval


class _OneCasePanel:
    def __init__(self, case, oracle):
        self.cases = (case,)
        self.oracle = oracle

    def oracle_for(self, case):
        if case != self.cases[0]:
            raise AssertionError("unexpected case")
        return self.oracle


class _OneCasePolicy:
    origin = "live"

    @staticmethod
    def invocation_client(client):
        return client

    @staticmethod
    def check_report(report):
        pass

    @staticmethod
    def summarize(report):
        pass


class SharedObservedCallBudgetRuler(unittest.IsolatedAsyncioTestCase):
    async def _observed_timeout(self, call_budget):
        original = p3_assets.load_panel(p3_eval.DEFAULT_PANEL)
        case = original.cases[0]
        panel = _OneCasePanel(case, original.oracle_for(case))
        entry = p3_eval._ExecutionEntry(case, panel.oracle, {})
        manifest = {"settings": {"panel_timeout_seconds": 1000.0,
                                  "call_timeout_seconds": call_budget,
                                  "max_client_http_attempts": 1},
                    "inputs": [{}]}
        report = {"results": [{"status": "pending", "phase": "not_started",
                               "client_http_attempts": 0, "runtime_invoked": False,
                               "attempt_may_be_in_flight": False,
                               "attempt_evidence_status": "not_started"}],
                  "client_http_attempts": 0, "possible_in_flight_attempts": 0,
                  "attempt_budget_used": 0, "status": "incomplete", "stop_reason": None,
                  "error_code": None, "elapsed_seconds": 0.0}
        client = type("SyntheticClient", (), {"http_attempts": 0})()
        observed = []

        async def interrupt_before_send(question, database, invocation_client, *, timeout_seconds, clock):
            observed.append(timeout_seconds)
            raise KeyboardInterrupt

        with patch.object(p3_eval, "interpret_recipe_and_execute",
                          side_effect=interrupt_before_send), \
             patch.object(p3_eval, "_persist"):
            result = await p3_eval._execute_panel(
                None, panel, manifest, object(), report, client, validate=lambda: None,
                policy=_OneCasePolicy(), started=0.0, clock=lambda: 0.0, entries=(entry,))
        self.assertEqual(result["stop_reason"], "interrupted")
        return observed

    async def test_shared_loop_uses_pinned_provider_call_budget(self):
        self.assertEqual(await self._observed_timeout(60.0), [60.0])
        self.assertEqual(await self._observed_timeout(300.0), [300.0])


if __name__ == "__main__":
    unittest.main()
