"""Issue #56 rulers: closed candidate identity; fake transport only, no live authority.

Specification phase: candidate API assertions intentionally fail until the
checkpoint is approved and implemented. Missing admission is an explicit ruler
failure, not an import/setup exception or an env-only admission workaround.
"""
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import gateway, model, recipe_model
from tools import candidate_registry, fixture


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "tests/fixtures/p310_identity_baseline.json").read_bytes())
CANDIDATE = BASELINE["candidate"]
QUESTION = BASELINE["wire"]["question"]
BASE = "https://candidate.invalid/v1"
KEY = "dummy-candidate-key"
ENV = {"GREPBIT_LITELLM_BASE_URL": BASE, "GREPBIT_LITELLM_API_KEY": KEY}
LEGACY = "gemma-4-31b"
ALTERNATIVE = "gemma-4-12b-it"
ABSENT = object()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def response_document(returned_model=LEGACY, content=None):
    value = {"choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(content or {"outcome": "declined"}),
    }}]}
    if returned_model is not ABSENT:
        value["model"] = returned_model
    return value


class CandidateModelRulers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo",
                       "httpx.AsyncHTTPTransport"):
            guard = patch(target, side_effect=AssertionError("Real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        # Any accidental implicit environment read sees no provider configuration.
        guard = patch("grepbit.gateway.os.environ", {})
        guard.start()
        self.addCleanup(guard.stop)

    def candidate_module(self):
        name = "tools.p3_candidate_model"
        self.assertIsNotNone(
            importlib.util.find_spec(name),
            "Required closed full-candidate admission API is not implemented; "
            "default env-only 12B rejection must NOT be relaxed to satisfy this ruler.",
        )
        module = importlib.import_module(name)
        self.assertTrue(callable(getattr(module, "admit_candidate", None)),
                        "Candidate admission must validate the full closed identity tuple")
        return module

    def admitted(self):
        return self.candidate_module().admit_candidate(dict(CANDIDATE))

    def assert_configuration_rejected(self, function, *args, **kwargs):
        with self.assertRaises(gateway.ModelError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, "invalid_configuration")
        self.assertNotIn(KEY, str(caught.exception))
        self.assertNotIn(BASE, str(caught.exception))

    async def invoke(self, config, *, returned_model=LEGACY, content=None,
                     database=Path("unused-test-db"), scalar=False):
        sent = []

        def handle(request):
            sent.append(bytes(request.content))
            return httpx.Response(200, json=response_document(returned_model, content))

        client = gateway.GatewayClient(config, transport=httpx.MockTransport(handle))
        entry = model.interpret_and_execute if scalar else recipe_model.interpret_recipe_and_execute
        result = await entry(QUESTION, database, client, clock=lambda: 0.0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(client.http_attempts, 1)
        self.assertEqual(result.evidence["client_http_attempts"], 1)
        self.assertNotIn(KEY, str(result.evidence))
        self.assertNotIn(BASE, str(result.evidence))
        return result, sent[0]

    def test_frozen_semantic_identities_and_limits(self):
        # History: the P3.10 fixture is the frozen P3.3 candidate's registry entry, byte for byte.
        frozen = candidate_registry.load_entry(candidate_registry.FROZEN_CANDIDATE_ID)
        for key in ("recipe_context", "structured_output", "p1_context", "limits"):
            self.assertEqual(frozen[key], BASELINE[key])
        # Present: the live runtime is whatever candidate the registry names as current (#87).
        current = candidate_registry.current()
        self.assertEqual(recipe_model.context_identity(), current["recipe_context"])
        self.assertEqual(recipe_model.structured_output_identity(), current["structured_output"])
        self.assertEqual(model.context_identity(), current["p1_context"])
        self.assertEqual({"input": gateway.MAX_INPUT_BYTES, "request": gateway.MAX_REQUEST_BYTES,
                          "response": gateway.MAX_RESPONSE_BYTES,
                          "timeout": gateway.CALL_TIMEOUT_SECONDS}, current["limits"])
        self.assertEqual(gateway.MODEL, LEGACY)

    def test_other_protected_behavior_files_remain_byte_identical(self):
        identity_plumbing = {"grepbit/gateway.py", "grepbit/model.py", "grepbit/recipe_model.py"}
        self.assertEqual(len(BASELINE["protected_files_sha256"]), 24)
        for name, expected in BASELINE["protected_files_sha256"].items():
            if name not in identity_plumbing:
                with self.subTest(path=name):
                    self.assertEqual(digest((ROOT / name).read_bytes()), expected)

    def test_default_config_rejects_12b_and_arbitrary_env_aliases(self):
        for alias in (ALTERNATIVE, "arbitrary-model", "openai/" + ALTERNATIVE, ""):
            with self.subTest(alias=alias):
                self.assert_configuration_rejected(
                    gateway.GatewayConfig.from_env,
                    environ={**ENV, "GREPBIT_LITELLM_MODEL": alias})
                self.assert_configuration_rejected(gateway.GatewayConfig, BASE, KEY, alias)
        self.assertEqual(gateway.GatewayConfig.from_env(environ=ENV).model, LEGACY)

    async def test_default_recipe_wire_matches_the_registered_current_candidate(self):
        result, body = await self.invoke(gateway.GatewayConfig(BASE, KEY))
        witness = candidate_registry.witness(candidate_registry.current(), QUESTION)
        self.assertEqual(digest(body), witness["recipe_body_sha256"])
        self.assertEqual(len(body), witness["recipe_body_bytes"])
        self.assertEqual(result.error.code, "model_declined")
        self.assertEqual(result.evidence["requested_model"], LEGACY)
        self.assertEqual(result.evidence["returned_model"], LEGACY)

    async def test_default_p1_wire_matches_the_registered_current_candidate(self):
        result, body = await self.invoke(gateway.GatewayConfig(BASE, KEY), scalar=True)
        witness = candidate_registry.witness(candidate_registry.current(), QUESTION)
        self.assertEqual(digest(body), witness["p1_body_sha256"])
        self.assertEqual(len(body), witness["p1_body_bytes"])
        self.assertNotIn("response_format", json.loads(body))
        self.assertEqual(result.evidence["requested_model"], LEGACY)

    async def test_default_rejects_returned_12b_before_native_execution(self):
        with patch.object(recipe_model, "execute_overview") as native:
            result, _ = await self.invoke(gateway.GatewayConfig(BASE, KEY), returned_model=ALTERNATIVE)
        self.assertEqual(result.error.code, "unexpected_model")
        self.assertEqual(result.evidence["stages"]["response_validation"], "failed")
        self.assertIsNone(result.evidence["returned_model"])
        native.assert_not_called()

    async def test_legacy_absent_or_null_model_remains_unknown(self):
        for value in (ABSENT, None):
            result, _ = await self.invoke(gateway.GatewayConfig(BASE, KEY), returned_model=value)
            self.assertEqual(result.error.code, "model_declined")
            self.assertEqual(result.evidence["stages"]["response_validation"], "passed")
            self.assertIsNone(result.evidence["returned_model"])

    def test_requested_model_evidence_cannot_change_parser_expectation(self):
        # The expected identity comes from validated config, not provider/evidence fields.
        evidence = {"requested_model": ALTERNATIVE}
        with self.assertRaises(gateway.ModelError) as caught:
            model._content(json.dumps(response_document(ALTERNATIVE)).encode(), evidence)
        self.assertEqual(caught.exception.code, "unexpected_model")

    def test_admission_is_closed_full_identity_and_immutable(self):
        module = self.candidate_module()
        expected = module.admit_candidate(dict(CANDIDATE))
        for name, value in CANDIDATE.items():
            self.assertEqual(getattr(expected, name), value)
        with self.assertRaises(FrozenInstanceError):
            expected.model_alias = LEGACY
        invalid = (
            {**CANDIDATE, "candidate_id": "unreviewed"},
            {**CANDIDATE, "candidate_identity_sha256": "0" * 64},
            {**CANDIDATE, "model_alias": LEGACY},
            {**CANDIDATE, "model_alias": "arbitrary-model"},
            {"model_alias": ALTERNATIVE},
            {**CANDIDATE, "unknown": True},
        )
        for value in invalid:
            with self.subTest(fields=sorted(value)):
                self.assert_configuration_rejected(module.admit_candidate, value)

    def test_explicit_candidate_config_requires_exact_env_model(self):
        expected = self.admitted()
        config = gateway.GatewayConfig.from_env(
            environ={**ENV, "GREPBIT_LITELLM_MODEL": ALTERNATIVE}, expected_model=expected)
        self.assertEqual(config.model, ALTERNATIVE)
        self.assertEqual(config.expected_model, expected)
        for alias in (LEGACY, "arbitrary-model", ""):
            self.assert_configuration_rejected(
                gateway.GatewayConfig.from_env,
                environ={**ENV, "GREPBIT_LITELLM_MODEL": alias}, expected_model=expected)
        # Preserve historical env omission resolution to 31B; do not silently reroute.
        self.assert_configuration_rejected(gateway.GatewayConfig.from_env,
                                           environ=ENV, expected_model=expected)
        self.assert_configuration_rejected(gateway.GatewayConfig, BASE, KEY, LEGACY,
                                           expected_model=expected)

    def test_candidate_admission_failure_precedes_explicit_env_file_read(self):
        self.admitted()  # First assert the proposed guarded API exists.
        with patch.object(Path, "open", side_effect=AssertionError("Env file touched")):
            for invalid in (ALTERNATIVE, dict(CANDIDATE), object()):
                self.assert_configuration_rejected(
                    gateway.GatewayConfig.from_env, env_file=Path("synthetic-unread.env"),
                    environ={}, expected_model=invalid)

    async def test_12b_wire_differs_only_in_model_and_evidence_tracks_it(self):
        expected = self.admitted()
        _, before = await self.invoke(gateway.GatewayConfig(BASE, KEY))
        result, after = await self.invoke(
            gateway.GatewayConfig(BASE, KEY, ALTERNATIVE, expected_model=expected),
            returned_model=ALTERNATIVE)
        self.assertEqual(digest(before), candidate_registry.witness(candidate_registry.current(), QUESTION)["recipe_body_sha256"])
        self.assertEqual(after, before.replace(b'"model": "gemma-4-31b"',
                                              b'"model": "gemma-4-12b-it"', 1))
        left, right = json.loads(before), json.loads(after)
        self.assertEqual(right.pop("model"), ALTERNATIVE)
        left.pop("model")
        self.assertEqual(left, right)
        self.assertEqual(result.error.code, "model_declined")
        self.assertEqual(result.evidence["requested_model"], ALTERNATIVE)
        self.assertEqual(result.evidence["returned_model"], ALTERNATIVE)
        for identifier in CANDIDATE.values():
            if identifier != ALTERNATIVE:
                self.assertNotIn(identifier.encode(), after)

    async def test_requested_12b_returned_31b_stops_without_fallback(self):
        config = gateway.GatewayConfig(BASE, KEY, ALTERNATIVE, expected_model=self.admitted())
        with patch.object(recipe_model, "execute_overview") as native:
            result, body = await self.invoke(config, returned_model=LEGACY)
        self.assertEqual(json.loads(body)["model"], ALTERNATIVE)
        self.assertEqual(result.error.code, "unexpected_model")
        self.assertEqual(result.evidence["requested_model"], ALTERNATIVE)
        self.assertIsNone(result.evidence["returned_model"])
        native.assert_not_called()

    async def test_12b_typed_request_uses_unchanged_native_overview(self):
        config = gateway.GatewayConfig(BASE, KEY, ALTERNATIVE, expected_model=self.admitted())
        proposal = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                    "request": {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00",
                                "end": "2026-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"}}
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "synthetic.sqlite"
            fixture.build(database)
            with patch.object(recipe_model, "execute_overview", wraps=recipe_model.execute_overview) as native:
                result, _ = await self.invoke(config, returned_model=ALTERNATIVE,
                                              content=proposal, database=database)
        self.assertIsNone(result.error)
        self.assertEqual(result.analysis_pack.status, "complete")
        self.assertEqual(result.proposal.to_dict(), proposal)
        native.assert_called_once()


if __name__ == "__main__":
    unittest.main()
