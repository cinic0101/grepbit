"""Exposed/design-seen fake actions, not fresh cases or model-quality evidence."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MAX_REQUEST_BYTES
from tools import fixture, recipe_smoke
from test_recipe_model import envelope, period, proposal
from test_json_diagnostics import P2_IDENTITY
from test_structured_output import P2_GENERATION


BASE = "https://clarification-private.invalid/v1"
KEY = "dummy-clarification-key"
QUESTION = "CTR-A01 or CTR-B01, March 2026 and February 2026; clarify the stated ambiguity."
KINDS = ("count_basis", "comparison_roles", "center", "metric_meaning")


def clarify(kind="count_basis"):
    scope = dict(period(), center_code="CTR-A01")
    if kind in ("count_basis", "metric_meaning"):
        values = ("booked_seats", "known_booking_accounts") if kind == "count_basis" else (
            "confirmed_booked_amount", "cash_received")
        alternatives = [{"type": kind, "scope": copy.deepcopy(scope), "value": value} for value in values]
    elif kind == "center":
        alternatives = [{"type": "center", "request": dict(scope, center_code=code)}
                        for code in ("CTR-A01", "CTR-B01")]
    else:
        request = proposal("compare")["request"]
        alternatives = [{"type": "comparison_roles", "request": request},
                        {"type": "comparison_roles", "request": {
                            "current": copy.deepcopy(request["baseline"]),
                            "baseline": copy.deepcopy(request["current"])}}]
    return {"outcome": "clarify", "clarification": {
        "kind": kind, "choices": [{"id": f"c{i}", "semantic_value": value}
                                for i, value in enumerate(alternatives, 1)]}}


class RecipeClarificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "grepbit.gateway.GatewayConfig.from_env"):
            guard = patch(target, side_effect=AssertionError("No network or config access"))
            guard.start()
            self.addCleanup(guard.stop)
        self.sent = []

    async def invoke(self, data=None, *, content=None, question=QUESTION, status=200,
                     clock=None, client_patch=None):
        if content is None:
            content = json.dumps(clarify() if data is None else data)

        def respond(request):
            self.sent.append(request)
            doc = envelope(content)
            doc["choices"][0]["message"]["reasoning_content"] = "PROVIDER_ONLY_CANARY"
            return httpx.Response(status, json=doc)

        self.sent = []
        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        forbidden = (
            "sqlite3.connect", "grepbit.execute_facts", "grepbit.kernel.execute_facts",
            "grepbit.kernel._read_transaction", "grepbit.grouped.execute_grouped_amount",
            "grepbit.composition._read_composition_transaction", "grepbit.model.interpret_and_execute",
            *(f"grepbit.recipe_model.execute_{name}" for name in ("overview", "compare", "breakdown")),
            *(f"grepbit.{name}.execute_{name}" for name in ("overview", "compare", "breakdown")),
        )
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(target, side_effect=AssertionError("Analytical execution forbidden")))
                     for target in forbidden]
            complete = stack.enter_context(patch.object(client, "complete", wraps=client.complete))
            if client_patch:
                client_patch(stack, client)
            result = await recipe_model.interpret_recipe_and_execute(
                question, Path("must-not-open.sqlite"), client, **({} if clock is None else {"clock": clock}))
        self.assertEqual(sum(spy.call_count for spy in spies), 0)
        self.assertEqual((len(self.sent), client.http_attempts, complete.call_count), (1, 1, 1))
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.analysis_pack)
        self.assertIsNone(result.evidence["analysis_pack"])
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        self.assertFalse(any(secret in str(result.evidence) for secret in (BASE, KEY, "PROVIDER_ONLY_CANARY")))
        if result.error:
            self.assertIsNone(result.clarification)
            self.assertIsNone(result.presentation)
            self.assertIsNone(result.error.__cause__)
            self.assertIsNone(result.error.__context__)
            self.assertIsNone(result.error.__traceback__)
        return result

    async def test_all_kinds_are_distinct_successful_nonexecuting_actions(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                result = await self.invoke(clarify(kind))
                self.assertIsNone(result.error)
                self.assertEqual(result.clarification.kind, kind)
                self.assertEqual(result.evidence["model_outcome"], "clarify")
                self.assertEqual(result.evidence["clarification"], result.clarification.to_dict())
                self.assertEqual(result.evidence["presentation"], result.presentation.to_dict())
                self.assertEqual(result.evidence["presentation_version"], "clarification-presentation-v1")
                self.assertEqual(result.evidence["stages"],
                                 {**dict.fromkeys(model.STAGES, "passed"), "kernel_execution": "not_run"})
                wire = json.loads(self.sent[0].content)
                self.assertEqual(wire["response_format"]["json_schema"]["schema"], recipe_model.output_schema())
                self.assertEqual(set(wire), {"model", "messages", "temperature", "max_tokens", "stream", "response_format"})

    async def test_languages_share_one_message_and_do_not_use_presentation_as_input(self):
        messages = []
        for question in (QUESTION, "CTR-A01及CTR-B01，2026年3月。", "CTR-A01とCTR-B01、2026年3月。"):
            result = await self.invoke(clarify("center"), question=question)
            self.assertIsNone(result.error)
            wire = json.loads(self.sent[0].content)
            self.assertEqual(wire["messages"][1], {"role": "user", "content": question})
            messages.append(wire["messages"][0])
        self.assertEqual(messages[0], messages[1])
        self.assertEqual(messages[1], messages[2])
        for forbidden in ("P13", "E05", "CTR-A01", "CTR-B01", "2026-03", "expected_behavior",
                          "frozen_fresh", "reference_sql", '"blocks"'):
            self.assertNotIn(forbidden, messages[0]["content"])

    async def test_decline_stays_separate_with_original_error_and_no_execution(self):
        result = await self.invoke({"outcome": "declined"})
        self.assertEqual(result.error.code, "model_declined")
        self.assertEqual(result.evidence["model_outcome"], "declined")
        self.assertEqual(result.evidence["stages"]["request_validation"], "failed")

    async def test_invalid_clarify_shapes_are_not_repaired_or_declined(self):
        valid = clarify()
        cases = [
            {**valid, "presentation": {}}, {**valid, "request": {}},
            {"outcome": "clarify"}, {"outcome": "clarify", "clarification": []},
            {"outcome": "clarify", "clarification": {"kind": "time_scope", "choices": []}},
        ]
        for extra in ("sql", "formula", "rank", "recommended", "label", "selection", "data", "blocks"):
            altered = copy.deepcopy(valid)
            altered["clarification"]["choices"][0][extra] = "untrusted"
            cases.append(altered)
        altered = clarify("comparison_roles")
        altered["clarification"]["choices"][0]["semantic_value"]["request"]["current"]["end"] = (
            "2026-06-01T00:00:00+08:00")
        cases.append(altered)
        for candidate in cases:
            with self.subTest(candidate=candidate):
                result = await self.invoke(candidate)
                self.assertEqual(result.error.code, "invalid_request")
                self.assertNotIn("invalid_json_fingerprint", result.evidence)

    async def test_codes_must_be_supplied_not_prefixes_or_casefolded_guesses(self):
        for question in ("CTR-A01 only", "ctr-a01 ctr-b01", "CTR-A010 CTR-B010",
                         "Neither supplied code exists here"):
            with self.subTest(question=question):
                result = await self.invoke(clarify("center"), question=question)
                self.assertEqual(result.error.code, "invalid_request")

    async def test_strict_json_and_diagnostics_remain_authoritative(self):
        valid = json.dumps(clarify())
        malformed = ["```json\n" + valid + "\n```", "<think>no</think>" + valid, valid + valid,
                     '{"outcome":"clarify","outcome":"declined"}', '{"x":NaN}',
                     '{"x":"\\ud800"}', '{"clarification":{"kind":"center","kind":"count_basis"}}']
        for content in malformed:
            with self.subTest(content=content):
                result = await self.invoke(content=content)
                self.assertEqual(result.error.code, "invalid_json")
                self.assertIn("invalid_json_fingerprint", result.evidence)

    async def test_provider_rejection_does_not_remove_constraint_or_retry(self):
        result = await self.invoke(status=400)
        self.assertEqual(result.error.code, "http_configuration")
        self.assertIn("response_format", json.loads(self.sent[0].content))

    async def test_private_choice_ids_never_escape_as_actionable_objects(self):
        candidate = clarify()
        candidate["clarification"]["choices"][0]["id"] = KEY
        result = await self.invoke(candidate)
        self.assertEqual(result.error.code, "invalid_request")
        self.assertIsNone(result.evidence["clarification"])
        self.assertIsNone(result.evidence["presentation"])

    async def test_late_validation_and_export_discard_actions_without_fake_execution(self):
        for phase in ("render", "export"):
            with self.subTest(phase=phase):
                now = [0.0]

                def install(stack, client):
                    if phase == "render":
                        render = recipe_model.render_clarification

                        def late_render(value):
                            result = render(value)
                            now[0] = 61.0
                            return result

                        stack.enter_context(patch.object(recipe_model, "render_clarification", side_effect=late_render))
                    else:
                        export = client.safe_export

                        def late_export(value):
                            result = export(value)
                            if "model_outcome" in value:
                                now[0] = 61.0
                            return result

                        stack.enter_context(patch.object(client, "safe_export", side_effect=late_export))

                result = await self.invoke(clock=lambda: now[0], client_patch=install)
                self.assertEqual(result.error.code, "timeout")
                self.assertIsNone(result.evidence["clarification"])
                self.assertIsNone(result.evidence["presentation"])

    async def test_final_redaction_cannot_leave_an_actionable_clarification(self):
        def install(stack, client):
            export = client.safe_export

            def redact(value):
                result = export(value)
                if value.get("model_outcome") == "clarify":
                    result["clarification"] = "[redacted]"
                return result

            stack.enter_context(patch.object(client, "safe_export", side_effect=redact))

        result = await self.invoke(client_patch=install)
        self.assertEqual(result.error.code, "invalid_request")
        self.assertIsNone(result.evidence["clarification"])
        self.assertEqual(result.evidence["stages"]["request_validation"], "failed")

    async def test_answer_only_p2_grader_does_not_collapse_clarify_into_refusal_or_operational_failure(self):
        result = await self.invoke()
        _, oracles = recipe_smoke.panel_inputs()
        for oracle in oracles.values():
            outcome, stages = recipe_smoke.grade(result, oracle)
            self.assertEqual(outcome, "wrong_request")
            self.assertEqual(stages, {**dict.fromkeys(recipe_smoke.GRADING_STAGES, "not_run"), "request": "failed"})

    async def test_all_frozen_p2_meanings_still_execute_and_grade_correct(self):
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "fixture.sqlite"
            fixture.build(db)
            inputs, oracles = recipe_smoke.panel_inputs()
            for entry in inputs:
                family = entry["family"]
                recipe = oracles[family]["recipe_id"]
                with self.subTest(family=family, language=entry["language"]):
                    calls = []

                    def respond(request):
                        calls.append(request)
                        return httpx.Response(200, json=envelope(json.dumps(proposal(recipe))))

                    client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
                    result = await recipe_model.interpret_recipe_and_execute(entry["question"], db, client)
                    self.assertEqual(recipe_smoke.grade(result, oracles[family])[0], "correct")
                    self.assertIsNone(result.clarification)
                    self.assertIsNone(result.presentation)
                    self.assertEqual(len(calls), 1)
                    self.assertLessEqual(len(calls[0].content), MAX_REQUEST_BYTES)

    def test_original_request_decline_schema_is_exact_and_new_sources_are_pinned(self):
        schema = recipe_model.output_schema()
        old = {"oneOf": schema["oneOf"][:4]}
        self.assertEqual(hashlib.sha256(model.canonical_json(old).encode()).hexdigest(),
                         P2_IDENTITY["output_contract_sha256"])
        old_wrapper = {"type": "json_schema", "json_schema": {"name": "grepbit_recipe_request", "schema": old}}
        self.assertEqual(hashlib.sha256(model.canonical_json(old_wrapper).encode()).hexdigest(),
                         P2_GENERATION["response_format_sha256"])
        self.assertEqual(len(schema["oneOf"]), 5)
        identity = recipe_smoke._source_identity()
        for name in ("grepbit/clarification.py", "grepbit/presentation.py"):
            self.assertEqual(identity["files_sha256"][name], hashlib.sha256(Path(name).read_bytes()).hexdigest())

    async def test_expanded_request_budget_is_enforced_including_schema(self):
        for size, character, should_send in ((4096, "x", True), (4096, '"', False), (4097, "x", False)):
            with self.subTest(size=size, character=character):
                calls = []

                def respond(request):
                    calls.append(request)
                    return httpx.Response(200, json=envelope('{"outcome":"declined"}'))

                client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
                result = await recipe_model.interpret_recipe_and_execute(
                    character * size, Path("unused.sqlite"), client)
                self.assertEqual(len(calls), int(should_send))
                self.assertEqual(result.error.code, "model_declined" if should_send else "input_too_large")
                if calls:
                    self.assertLessEqual(len(calls[0].content), MAX_REQUEST_BYTES)
