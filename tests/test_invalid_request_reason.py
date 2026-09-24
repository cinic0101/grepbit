"""Closed request-validation reasons in evidence; fake outputs are not model-quality evidence."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import clarification, recipe_model
from grepbit.bedrock import converse_schema
from grepbit.contracts import KernelError
from grepbit.gateway import GatewayClient, GatewayConfig
from tools import fixture, p3_assets, p3_live_evidence
from test_recipe_clarification import clarify
from test_recipe_model import envelope, period, proposal


BASE = "https://reason-private.invalid/v1"
KEY = "dummy-reason-private-key"
QUESTION = "CTR-A01 or CTR-B01, March 2026 versus February 2026; the stated ambiguity is intentional."
REASONS = recipe_model.INVALID_REQUEST_REASONS


def _request_cases():
    """(payload, reason) pairs for the request branch; nested failures stay ``request_values``."""
    extra_root = {**proposal(), "sql": "SELECT 1"}
    old_version = {**proposal(), "recipe_version": "0.2"}
    unknown = {**proposal(), "recipe_id": "unknown"}
    unhashable = {**proposal(), "recipe_id": ["overview"]}
    mismatched = {**proposal(), "recipe_id": "breakdown"}
    listed = {**proposal(), "request": []}
    extra_field = proposal()
    extra_field["request"]["center_id"] = None
    bad_month = proposal()
    bad_month["request"]["start"] = "2026-03-02T00:00:00+08:00"
    nested = proposal("compare")
    nested["request"]["current"]["filters"] = {"center_id": "CA"}
    big_k = proposal("breakdown")
    big_k["request"]["top_k"] = 4
    return (
        ("not an object", "root_shape"), (extra_root, "root_shape"), (old_version, "root_shape"),
        ({"outcome": "request"}, "root_shape"),
        (unknown, "unknown_recipe"), (unhashable, "unknown_recipe"),
        (mismatched, "request_fields"), (listed, "request_fields"), (extra_field, "request_fields"),
        (bad_month, "request_values"), (nested, "request_values"), (big_k, "request_values"),
    )


def _clarify_cases():
    """(payload, reason) pairs for the clarify branch, one violated rule each."""
    extra_root = {**clarify(), "recipe_id": "overview"}
    missing_kind = clarify()
    del missing_kind["clarification"]["kind"]
    unknown_kind = clarify()
    unknown_kind["clarification"]["kind"] = "unknown"
    single = clarify("center")
    single["clarification"]["choices"] = single["clarification"]["choices"][:1]
    single_roles = clarify("comparison_roles")
    single_roles["clarification"]["choices"] = single_roles["clarification"]["choices"][:1]
    many = clarify()
    many["clarification"]["choices"] = [
        {**copy.deepcopy(many["clarification"]["choices"][0]), "id": f"c{i}"} for i in range(5)]
    not_list = clarify()
    not_list["clarification"]["choices"] = {"c1": {}}
    missing_id = clarify()
    del missing_id["clarification"]["choices"][0]["id"]
    unknown_type = clarify()
    unknown_type["clarification"]["choices"][0]["semantic_value"]["type"] = "free_text"
    extra_value_key = clarify()
    extra_value_key["clarification"]["choices"][0]["semantic_value"]["label"] = "Seats"
    bad_id = clarify()
    bad_id["clarification"]["choices"][0]["id"] = "1bad"
    bad_value = clarify()
    bad_value["clarification"]["choices"][1]["semantic_value"]["value"] = "profit_after_tax"
    bad_scope = clarify()
    bad_scope["clarification"]["choices"][0]["semantic_value"]["scope"]["start"] = "2026-03-02T00:00:00+08:00"
    duplicate_ids = clarify()
    duplicate_ids["clarification"]["choices"][1]["id"] = duplicate_ids["clarification"]["choices"][0]["id"]
    not_reversed = clarify("comparison_roles")
    not_reversed["clarification"]["choices"][1]["semantic_value"]["request"] = copy.deepcopy(
        not_reversed["clarification"]["choices"][0]["semantic_value"]["request"])
    different_months = clarify("center")
    different_months["clarification"]["choices"][1]["semantic_value"]["request"].update(period(2))
    without_required = clarify()
    without_required["clarification"]["choices"][0]["semantic_value"]["value"] = "attendance_visits"
    kind_mismatch = clarify()
    kind_mismatch["clarification"]["kind"] = "metric_meaning"
    unbound = clarify("center")
    unbound["clarification"]["choices"][1]["semantic_value"]["request"]["center_code"] = "CTR-C01"
    drift = clarify("center")
    drift["clarification"]["choices"][0]["id"] = KEY
    return (
        (extra_root, "clarification_shape"), (missing_kind, "clarification_shape"),
        (unknown_kind, "clarification_shape"),
        (single, "choice_count"), (single_roles, "choice_count"), (many, "choice_count"),
        (not_list, "choice_count"),
        (missing_id, "choice_shape"), (unknown_type, "choice_shape"), (extra_value_key, "choice_shape"),
        (bad_id, "choice_values"), (bad_value, "choice_values"), (bad_scope, "choice_values"),
        (duplicate_ids, "choice_consistency"), (not_reversed, "choice_consistency"),
        (different_months, "choice_consistency"), (without_required, "choice_consistency"),
        (kind_mismatch, "choice_consistency"),
        (unbound, "question_binding"), (drift, "export_drift"),
    )


class InvalidRequestReasonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "grepbit.gateway.GatewayConfig.from_env"):
            guard = patch(target, side_effect=AssertionError("No network or config access"))
            guard.start()
            self.addCleanup(guard.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "reason.sqlite"
        fixture.build(self.database)

    async def invoke(self, payload, *, content=None, question=QUESTION):
        if content is None:
            content = json.dumps(payload)

        def respond(request):
            doc = envelope(content)
            doc["choices"][0]["message"]["reasoning_content"] = "PROVIDER_ONLY_CANARY"
            return httpx.Response(200, json=doc)

        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        with ExitStack() as stack:
            complete = stack.enter_context(patch.object(client, "complete", wraps=client.complete))
            result = await recipe_model.interpret_recipe_and_execute(question, self.database, client)
        self.assertEqual((client.http_attempts, complete.call_count), (1, 1))
        self.assertFalse(any(secret in json.dumps(result.evidence) for secret in (BASE, KEY, "PROVIDER_ONLY_CANARY")))
        return result

    def assert_reason(self, result, reason):
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "invalid_request")
        self.assertEqual(result.evidence["error_code"], "invalid_request")
        self.assertEqual(result.evidence["invalid_request_reason"], reason)
        self.assertIn(reason, REASONS)
        self.assertEqual(result.evidence["stages"]["json_parse"], "passed")
        self.assertEqual(result.evidence["stages"]["request_validation"], "failed")
        self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.clarification)
        self.assertIsNone(result.analysis_pack)
        self.assertIsNone(result.error.__cause__)
        self.assertIsNone(result.error.__context__)

    async def test_request_branch_reasons_name_the_violated_structure_only(self):
        for index, (payload, reason) in enumerate(_request_cases()):
            with self.subTest(case=index, reason=reason):
                self.assert_reason(await self.invoke(payload), reason)

    async def test_clarify_branch_reasons_name_the_violated_rule_only(self):
        for index, (payload, reason) in enumerate(_clarify_cases()):
            with self.subTest(case=index, reason=reason):
                self.assert_reason(await self.invoke(payload), reason)

    async def test_every_reason_is_reachable_and_the_enum_is_closed(self):
        observed = {reason for _, reason in _request_cases()} | {reason for _, reason in _clarify_cases()}
        self.assertEqual(observed, set(REASONS))
        self.assertEqual(len(set(REASONS)), len(REASONS))
        self.assertTrue(set(recipe_model._CLARIFICATION_REASONS) < set(REASONS))
        for reason in ("", "Invalid bounded clarification contract.", "unknown"):
            with self.assertRaises(ValueError):
                recipe_model._InvalidRequest(reason)

    def test_reason_naming_never_changes_the_frozen_validators_decision(self):
        """Every clarify payload the validators accept has no reason; the frozen file is untouched."""
        for kind in ("count_basis", "comparison_roles", "center", "metric_meaning"):
            raw = clarify(kind)["clarification"]
            accepted = clarification.Clarification.from_mapping(raw)
            accepted.validate_question(QUESTION)
            self.assertIn(recipe_model._clarification_reason(raw, QUESTION), REASONS)
        for payload, reason in _clarify_cases():
            if reason == "export_drift" or set(payload) != {"outcome", "clarification"}:
                continue
            raw = payload["clarification"]
            with self.subTest(reason=reason):
                with self.assertRaises(KernelError):
                    clarification.Clarification.from_mapping(raw).validate_question(QUESTION)
                self.assertEqual(recipe_model._clarification_reason(raw, QUESTION), reason)

    async def test_other_outcomes_carry_no_reason(self):
        accepted = await self.invoke(proposal())
        self.assertIsNone(accepted.error)
        self.assertIsNone(accepted.evidence["invalid_request_reason"])
        self.assertIsNotNone(accepted.analysis_pack)
        clarified = await self.invoke(clarify("center"))
        self.assertIsNone(clarified.error)
        self.assertIsNone(clarified.evidence["invalid_request_reason"])
        declined = await self.invoke({"outcome": "declined"})
        self.assertEqual(declined.error.code, "model_declined")
        self.assertIsNone(declined.evidence["invalid_request_reason"])
        malformed = await self.invoke(None, content="{not json")
        self.assertEqual(malformed.error.code, "invalid_json")
        self.assertIsNone(malformed.evidence["invalid_request_reason"])
        self.assertIn("invalid_json_fingerprint", malformed.evidence)

    def test_bedrock_wire_permits_one_choice_that_native_rejects_as_choice_count(self):
        """The compact wire keeps ``minItems: 1``; only native validation enforces two choices."""
        constraint = recipe_model._structured_output(recipe_model.output_schema())[0]
        wire_format, _ = converse_schema(constraint)
        wire = json.loads(wire_format["structure"]["jsonSchema"]["schema"])
        self.assertEqual(wire["properties"]["clarification"]["properties"]["choices"]["minItems"], 1)
        canonical = recipe_model.output_schema()["oneOf"][4]["properties"]["clarification"]["oneOf"]
        self.assertEqual({branch["properties"]["choices"]["minItems"] for branch in canonical}, {2})
        single = clarify("center")["clarification"]
        single["choices"] = single["choices"][:1]
        with self.assertRaises(KernelError) as caught:
            clarification.Clarification.from_mapping(single)
        self.assertEqual(caught.exception.code, "invalid_request")
        self.assertEqual(recipe_model._clarification_reason(single, QUESTION), "choice_count")


class LiveEvidenceReasonProjectionTests(unittest.TestCase):
    def evidence(self, **changes):
        return {"client_http_attempts": 1, "elapsed_seconds": 1.5, "requested_model": "jp.example.profile",
                "returned_model": None, "http_status": 200, "transport_security": "tls_verification_enabled",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "stages": {**dict.fromkeys(recipe_model.protocol.STAGES, "passed"),
                           "request_validation": "failed", "kernel_execution": "not_run"},
                "error_code": "invalid_request", "stop_reason": None, **changes}

    def test_closed_reason_is_projected_only_with_its_failure(self):
        self.assertIn("invalid_request_reason", p3_live_evidence._EVIDENCE_FIELDS)
        value = self.evidence(invalid_request_reason="choice_count")
        self.assertEqual(p3_live_evidence._evidence(value, requested_profile="jp.example.profile"), value)
        historical = self.evidence()
        self.assertEqual(p3_live_evidence._evidence(historical, requested_profile="jp.example.profile"), historical)
        for mutation in ({"invalid_request_reason": "Supply exactly current and baseline scopes."},
                         {"invalid_request_reason": ""}, {"invalid_request_reason": 1},
                         {"invalid_request_reason": "choice_count", "error_code": None},
                         {"invalid_request_reason": "choice_count", "error_code": "invalid_json"}):
            with self.subTest(mutation=mutation), self.assertRaises(p3_assets.P3Error) as caught:
                p3_live_evidence._evidence(self.evidence(**mutation), requested_profile="jp.example.profile")
            self.assertEqual(caught.exception.code, "invalid_asset")

    def test_reason_requires_the_stage_record_its_failure_implies(self):
        """A reason with passed request validation, run execution or missing stages is contradictory."""
        good = self.evidence(invalid_request_reason="choice_count")
        self.assertEqual(p3_live_evidence._evidence(good, requested_profile="jp.example.profile"), good)
        contradictions = (
            {"request_validation": "passed"}, {"request_validation": "not_run"},
            {"kernel_execution": "passed"}, {"kernel_execution": "failed"},
            {"json_parse": "failed"}, {"json_parse": "not_run"},
        )
        for change in contradictions:
            value = self.evidence(invalid_request_reason="choice_count")
            value["stages"] = {**value["stages"], **change}
            with self.subTest(stages=change), self.assertRaises(p3_assets.P3Error) as caught:
                p3_live_evidence._evidence(value, requested_profile="jp.example.profile")
            self.assertEqual(caught.exception.code, "invalid_asset")
        missing = self.evidence(invalid_request_reason="choice_count")
        del missing["stages"]
        with self.assertRaises(p3_assets.P3Error) as caught:
            p3_live_evidence._evidence(missing, requested_profile="jp.example.profile")
        self.assertEqual(caught.exception.code, "invalid_asset")
        # Without a reason, the same stage records stay acceptable historical evidence.
        for change in contradictions:
            value = self.evidence()
            value["stages"] = {**value["stages"], **change}
            self.assertEqual(p3_live_evidence._evidence(value, requested_profile="jp.example.profile"), value)

    def test_projection_drops_unlisted_runtime_fields_but_keeps_the_reason(self):
        value = self.evidence(invalid_request_reason="request_fields", proposal={"private": True},
                              clarification={"choices": []}, kernel_error_code=None)
        projected = p3_live_evidence._evidence(value, requested_profile="jp.example.profile")
        self.assertEqual(projected["invalid_request_reason"], "request_fields")
        self.assertTrue(set(projected) <= p3_live_evidence._EVIDENCE_FIELDS)
        self.assertNotIn("proposal", projected)
        self.assertNotIn("clarification", projected)


if __name__ == "__main__":
    unittest.main()
