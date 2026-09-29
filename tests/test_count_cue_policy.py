"""v11 count-cue ruler (#120, docs/count-cue-policy.md): typed cues, one kernel policy, b2 absent cues.

Offline and fake-transport only. Readings are ruler data from the owner-designated
semantic reviewer, never runtime context; nothing here is live model evidence.
"""
import asyncio
import copy
from contextlib import ExitStack
import hashlib
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import bedrock, gateway, model as protocol, provider, recipe_model
from grepbit.clarification import COUNT_BASES
from grepbit.gateway import GatewayClient, GatewayConfig, ModelError
from tools import candidate_registry as registry, fixture, p3_assets, p3_eval, p3_live_evidence as live
from test_recipe_model import envelope, period

try:
    from grepbit import count_policy
except ImportError:  # the ruler is committed before the implementation
    count_policy = None

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://count-cue-private.invalid/v1"
KEY = "dummy-count-cue-key"
QUESTION = "Give me a booking overview for CTR-A01 in March 2026 with the headcount."
SCOPE = dict(center_code="CTR-A01", **period())
READINGS_FIXTURE = ROOT / "tests/fixtures/count-cue-readings-v1.json"
PACKET_SHA256 = "b7ba170775d4431e34b6db14a6c34708323f275c3d7716b4d63b9ed649ab1334"
RULES = ("other_unsupported", "bound_seats", "bound_unsupported", "contrast_unexecutable", "contrast",
         "generic_booking", "generic_unframed")
CUE_REASONS = ("count_cue_shape", "count_cue_values", "count_cue_binding")
V10_REASONS = ("root_shape", "unknown_recipe", "request_fields", "request_values", "clarification_shape",
               "choice_count", "choice_shape", "choice_values", "choice_consistency", "question_binding",
               "export_drift")
BOOKING_MEANINGS = ("booked_seats", "known_booking_accounts", "distinct_people")
CANDIDATE, V10 = "p3-count-cue-policy-v11", "p3-v7-context-restoration-v10"
V10_ENTRY_SHA256 = "72124fe322213dd77977f90d386f49ed2c67bc5e6593a88fc5fd7aef8ed388e2"
# v10 bytes around the one replaced instruction sentence, and the unchanged context parts.
V10_COUNT_SENTENCE = (
    "count_basis and metric_meaning require a complete explicit Overview scope. "
    "Count choices include booked_seats and reviewed alternative count meanings; amount choices include "
    "confirmed_booked_amount and reviewed alternative amount meanings. Alternatives do not add executable metrics. ")
V10_INSTRUCTION_PREFIX = "1225debf1398b1e980840de7bbab8974ce8e30e52d9b368f5cd024029dbc73db"
V10_INSTRUCTION_SUFFIX = "788182a470fa472ff0f0f4610b09573dd8a191a4a987fb7e9c2b5fe4a13bc208"
V10_CONTEXT_REST = "3a68b54b09ed45a56c9e7241ae1c54678b9a9561d90e6f18369f4d465e9d34cc"
V10_CLARIFICATION_REST = "4e823eca432fcb7510184e159b1fa1eaa9019eeba3743e7020a56b994ad670e8"
V10_RECIPES_WITHOUT_PEOPLE_COUNTS = "afabcaf62744a5b4e6e76ec7751540a5feab706e2b1ece84b0e00822bd62400a"
# (v1 file, sha256, cued sibling, cases, panel, cued case IDs)
FAKES = (
    ("evals/dev/dev-responses-v1.json", "48c2b4381eddae0a9f5e2ed278ef896d574c3f678a0eb5afec10150058aba0d3",
     "evals/dev/dev-cued-responses-v1.json", "evals/dev/dev-cases-v1.json",
     "evals/dev/dev-panel-v1.json", [f"dev-C1.{lang}" for lang in ("zh-TW", "en", "ja")]),
    ("evals/dev/bound-meaning-responses-v1.json",
     "4ef96ac5616851f8045d2fe5a007f3fb29cbcdbec420090e883f2e9cc7835c1f",
     "evals/dev/bound-meaning-cued-responses-v1.json", "evals/dev/bound-meaning-cases-v1.json",
     "evals/dev/bound-meaning-panel-v1.json",
     [f"{family}.{lang}" for family in ("dev-BM6", "dev-BM7") for lang in ("zh-TW", "en", "ja")]),
    ("evals/dev/mechanism-probe-responses-v1.json",
     "81dc5a19511991db7fac4a77d866ca7657872e7b5729d58a2e9fcb834867e70d",
     "evals/dev/mechanism-probe-cued-responses-v1.json", "evals/dev/mechanism-probe-cases-v1.json",
     "evals/dev/mechanism-probe-panel-v1.json",
     [f"{family}.{lang}" for family in ("dev-BM6", "dev-MN1", "dev-MN2", "dev-MN3")
      for lang in ("zh-TW", "en", "ja")]),
    ("evals/p3/development-responses-v1.json", "9a35ab8abfd4797befe0b96dffa954153c2184a0727a34130be4b87024091aef",
     "evals/p3/development-cued-responses-v1.json", "evals/p3/development-cases-v1.json",
     "evals/p3/development-panel-v1.json", ["C01_count_basis.en"]),
)
# The reviewed packet: the unique questions of the three current dev panels.
READING_PANELS = ("evals/dev/dev-panel-compare-first-v2.json", "evals/dev/bound-meaning-panel-v1.json",
                  "evals/dev/mechanism-probe-panel-v1.json")
C01_CUE = {"overview_count": "contrast", "meanings": ["booked_seats", "known_booking_accounts"],
           "other_unsupported": False}
BEDROCK_ENV = {"GREPBIT_LLM_PROVIDER": "bedrock_converse", "GREPBIT_BEDROCK_REGION": "us-east-1",
               "GREPBIT_BEDROCK_MODEL_ID": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
               "GREPBIT_BEDROCK_API_KEY": "dummy-bedrock-count-cue-key"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def cue(reading, value=None, *, other=False, scope=None):
    data = {"overview_count": reading}
    data[{"bound": "meaning", "contrast": "meanings", "generic": "event"}[reading]] = (
        list(value) if reading == "contrast" else value)
    data["other_unsupported"] = other
    data["scope"] = copy.deepcopy(SCOPE if scope is None else scope)
    return data


def reference(reading, value, other):
    """The policy table of docs/count-cue-policy.md, independent of the implementation."""
    if other:
        return "other_unsupported", "declined", None
    if reading == "bound":
        return ("bound_seats", "request", None) if value == "booked_seats" else ("bound_unsupported", "declined", None)
    if reading == "contrast":
        if "booked_seats" not in value:
            return "contrast_unexecutable", "declined", None
        return "contrast", "clarify", tuple(basis for basis in COUNT_BASES if basis in value)
    return (("generic_booking", "clarify", BOOKING_MEANINGS) if value == "booking"
            else ("generic_unframed", "clarify", COUNT_BASES))


def table():
    rows = [("bound", meaning) for meaning in COUNT_BASES]
    rows += [("contrast", subset) for size in (2, 3, 4) for subset in combinations(COUNT_BASES, size)]
    rows += [("generic", event) for event in ("booking", "none")]
    return [(reading, value, other) for reading, value in rows for other in (False, True)]


def reading_key(reading):
    return {key: value for key, value in reading.items() if key != "note"}


def panel_rows(panel_path):
    panel = json.loads((ROOT / panel_path).read_text())
    folder = (ROOT / panel_path).parent
    cases = {c["case_id"]: c for c in json.loads((folder / panel["cases"]).read_text())["cases"]}
    oracles = {o["oracle_id"]: o for o in json.loads((folder / panel["oracles"]).read_text())["oracles"]}
    return [(cases[case_id], oracles[cases[case_id]["oracle_id"]]) for case_id in panel["order"]]


class _Offline:
    def guard(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            guard = patch(target, side_effect=AssertionError("Network or config access forbidden"))
            guard.start()
            self.addCleanup(guard.stop)


class CountCueRuntimeRulers(_Offline, unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="count-cue-", dir=ROOT / ".artifacts")
        cls.database = Path(cls.directory.name) / "fixture.sqlite"
        fixture.build(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.guard()

    async def invoke(self, data, *, question=QUESTION, content=None):
        sent = []

        def respond(request):
            sent.append(request)
            return httpx.Response(200, json=envelope(json.dumps(data) if content is None else content))

        client = GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))
        result = await recipe_model.interpret_recipe_and_execute(question, self.database, client)
        self.assertEqual(len(sent), 1)
        self.sent = sent
        return result

    def assert_rejected(self, result, reason, reading):
        evidence = result.evidence
        self.assertEqual(result.error.code, "invalid_request")
        self.assertEqual(evidence["invalid_request_reason"], reason)
        self.assertEqual((evidence["stages"]["json_parse"], evidence["stages"]["request_validation"],
                          evidence["stages"]["kernel_execution"]), ("passed", "failed", "not_run"))
        self.assertEqual((evidence["model_outcome"], evidence["action_source"], evidence["count_policy_rule"],
                          evidence["count_cue"], evidence["count_reading"]), (None, None, None, None, reading))
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.clarification)

    async def test_policy_table_end_to_end(self):
        declined = await self.invoke({"overview_count": "none", "outcome": "declined"})
        self.assertEqual(declined.error.code, "model_declined")
        for reading, value, other in table():
            with self.subTest(reading=reading, value=value, other=other):
                data = cue(reading, value, other=other)
                result = await self.invoke(data)
                rule, action, choices = reference(reading, value, other)
                evidence = result.evidence
                self.assertEqual((evidence["action_source"], evidence["count_policy_rule"],
                                  evidence["count_reading"], evidence["model_outcome"]),
                                 ("count_policy", rule, reading, action))
                self.assertEqual(evidence["count_cue"], data)
                self.assertIsNone(evidence["invalid_request_reason"])
                if action == "declined":
                    self.assertEqual(result.error.code, "model_declined")
                    self.assertEqual(evidence["stages"], declined.evidence["stages"])
                    self.assertIsNone(result.proposal)
                    self.assertIsNone(result.clarification)
                elif action == "request":
                    self.assertIsNone(result.error)
                    self.assertEqual(result.proposal.to_dict(), {"outcome": "request", "recipe_id": "overview",
                                                                 "recipe_version": "0.1", "request": SCOPE})
                    self.assertEqual(result.analysis_pack.status, "complete")
                else:
                    self.assertIsNone(result.error)
                    clarification = result.clarification.to_dict()
                    self.assertEqual(clarification["kind"], "count_basis")
                    self.assertEqual([c["id"] for c in clarification["choices"]], list(choices))
                    self.assertEqual([c["semantic_value"] for c in clarification["choices"]],
                                     [{"type": "count_basis", "scope": SCOPE, "value": v} for v in choices])
                    self.assertIn("booked_seats", choices)
                    self.assertTrue(2 <= len(choices) <= 4)
                    self.assertIsNotNone(result.presentation)
                    self.assertEqual(evidence["presentation"], result.presentation.to_dict())

    async def test_none_and_absent_cues_pass_v10_actions_but_never_model_count_basis(self):
        request = {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1", "request": SCOPE}
        center = {"outcome": "clarify", "clarification": {"kind": "center", "choices": [
            {"id": "a", "semantic_value": {"type": "center", "request": SCOPE}},
            {"id": "b", "semantic_value": {"type": "center", "request": dict(SCOPE, center_code="CTR-B01")}}]}}
        count = {"outcome": "clarify", "clarification": {"kind": "count_basis", "choices": [
            {"id": value, "semantic_value": {"type": "count_basis", "scope": SCOPE, "value": value}}
            for value in ("booked_seats", "known_booking_accounts")]}}
        question = QUESTION + " CTR-B01 is the other code."
        for reading in ("none", "absent"):
            def cued(action, reading=reading):
                return action if reading == "absent" else {"overview_count": "none", **action}

            with self.subTest(reading=reading, action="request"):
                result = await self.invoke(cued(request))
                self.assertIsNone(result.error)
                self.assertEqual(result.analysis_pack.status, "complete")
                self.assertEqual((result.evidence["action_source"], result.evidence["count_policy_rule"],
                                  result.evidence["count_reading"], result.evidence["count_cue"]),
                                 ("model", None, reading, None))
            with self.subTest(reading=reading, action="declined"):
                result = await self.invoke(cued({"outcome": "declined"}))
                self.assertEqual(result.error.code, "model_declined")
                self.assertEqual((result.evidence["action_source"], result.evidence["count_reading"]),
                                 ("model", reading))
            with self.subTest(reading=reading, action="center"):
                result = await self.invoke(cued(center), question=question)
                self.assertIsNone(result.error)
                self.assertEqual(result.clarification.kind, "center")
                self.assertEqual(result.evidence["action_source"], "model")
            with self.subTest(reading=reading, action="count_basis"):
                self.assert_rejected(await self.invoke(cued(count)), "clarification_shape", reading)
        with self.subTest("none with cue fields is a v10 root shape"):
            self.assert_rejected(await self.invoke({"overview_count": "none", "meaning": "booked_seats",
                                                    "outcome": "declined"}), "root_shape", "none")
        with self.subTest("a parsed non-object has no reading"):
            self.assert_rejected(await self.invoke(["bound"]), "root_shape", None)

    async def test_every_rejected_cue_reason(self):
        def edit(reading, value, **changes):
            data = cue(reading, value)
            for key, change in changes.items():
                if change is KeyError:
                    del data[key]
                else:
                    data[key] = change
            return data

        other = QUESTION.replace("CTR-A01", "CTR-A011")
        cases = [
            ("count_cue_shape", None, {"overview_count": "maybe", "outcome": "declined"}, QUESTION),
            ("count_cue_shape", None, {"overview_count": None, "outcome": "declined"}, QUESTION),
            ("count_cue_shape", None, {"overview_count": ["bound"], "outcome": "declined"}, QUESTION),
            ("count_cue_shape", "bound", edit("bound", "booked_seats", extra=1), QUESTION),
            ("count_cue_shape", "bound", edit("bound", "booked_seats", other_unsupported=KeyError), QUESTION),
            ("count_cue_shape", "bound", edit("bound", "booked_seats", other_unsupported="false"), QUESTION),
            ("count_cue_shape", "bound", edit("bound", "booked_seats", other_unsupported=0), QUESTION),
            ("count_cue_shape", "bound", edit("bound", 1), QUESTION),
            ("count_cue_shape", "bound", {**edit("bound", "booked_seats", meaning=KeyError),
                                          "meanings": ["booked_seats"]}, QUESTION),
            ("count_cue_shape", "contrast", edit("contrast", ["booked_seats"], meanings="booked_seats"), QUESTION),
            ("count_cue_shape", "contrast", edit("contrast", ["booked_seats", 1]), QUESTION),
            ("count_cue_shape", "generic", edit("generic", "booking", scope=[SCOPE]), QUESTION),
            ("count_cue_shape", "generic", edit("generic", "booking",
                                                scope={k: v for k, v in SCOPE.items() if k != "timezone"}), QUESTION),
            ("count_cue_shape", "generic", {"overview_count": "generic", "event": "booking",
                                            "other_unsupported": False}, QUESTION),
            ("count_cue_values", "bound", edit("bound", "people"), QUESTION),
            ("count_cue_values", "contrast", edit("contrast", ["booked_seats"]), QUESTION),
            ("count_cue_values", "contrast", edit("contrast", ["booked_seats", "booked_seats"]), QUESTION),
            ("count_cue_values", "contrast", edit("contrast", [*COUNT_BASES, "booked_seats"]), QUESTION),
            ("count_cue_values", "contrast", edit("contrast", ["booked_seats", "headcount"]), QUESTION),
            ("count_cue_values", "generic", edit("generic", "attendance"), QUESTION),
            ("count_cue_values", "generic", edit("generic", "booking",
                                                 scope=dict(SCOPE, start="2026-03-15T00:00:00+08:00")), QUESTION),
            ("count_cue_values", "generic", edit("generic", "booking", scope=dict(SCOPE, timezone="UTC")), QUESTION),
            ("count_cue_binding", "bound", edit("bound", "booked_seats",
                                                scope=dict(SCOPE, center_code="CTR-B01")), QUESTION),
            ("count_cue_binding", "generic", edit("generic", "none"), other),
            ("count_cue_binding", "bound", cue("bound", "distinct_people", other=True,
                                               scope=dict(SCOPE, center_code="CTR-B01")), QUESTION),
        ]
        for reason, reading, data, question in cases:
            with self.subTest(reason=reason, data=data):
                self.assert_rejected(await self.invoke(data, question=question), reason, reading)

    async def test_request_cap_admits_a_maximal_question(self):
        """Owner decision A (#120 #issuecomment-5886754433): only the complete-request cap is raised."""
        self.assertEqual((gateway.MAX_INPUT_BYTES, gateway.MAX_REQUEST_BYTES, gateway.MAX_RESPONSE_BYTES),
                         (4096, 40960, 131072))
        settings = p3_eval.settings(1)
        self.assertEqual((settings["max_input_bytes"], settings["max_request_bytes"], settings["max_response_bytes"]),
                         (4096, 40960, 131072))
        result = await self.invoke({"overview_count": "none", "outcome": "declined"}, question="x" * 4096)
        self.assertLessEqual(len(self.sent[0].content), gateway.MAX_REQUEST_BYTES)
        self.assertEqual(result.error.code, "model_declined")

    async def test_schema_order_is_published_and_on_the_wire(self):
        await self.invoke({"overview_count": "none", "outcome": "declined"})
        body = json.loads(self.sent[0].content)
        wire = body["response_format"]["json_schema"]["schema"]
        schema = recipe_model.output_schema()
        self.assertEqual(wire, schema)
        branches = wire["oneOf"]
        self.assertEqual(len(branches), 8)
        overview = branches[0]["properties"]["request"]
        for branch in branches:
            self.assertEqual(list(branch["properties"])[0], "overview_count")
            self.assertEqual(branch["required"][0], "overview_count")
            self.assertFalse(branch["additionalProperties"])
            self.assertEqual(set(branch["required"]), set(branch["properties"]))
        nones = [b for b in branches if b["properties"]["overview_count"] == {"const": "none"}]
        self.assertEqual(len(nones), 5)
        clarify = next(b for b in nones if "clarification" in b["properties"])
        kinds = [k["properties"]["kind"]["const"] for k in clarify["properties"]["clarification"]["oneOf"]]
        self.assertEqual(kinds, ["comparison_roles", "center", "metric_meaning"])
        cues = {b["properties"]["overview_count"]["const"]: b for b in branches if b not in nones}
        self.assertEqual(list(cues), ["bound", "contrast", "generic"])
        for reading, field, value in (("bound", "meaning", {"enum": list(COUNT_BASES)}),
                                      ("contrast", "meanings", {"type": "array", "minItems": 2, "maxItems": 4,
                                                                "items": {"enum": list(COUNT_BASES)}}),
                                      ("generic", "event", {"enum": ["booking", "none"]})):
            properties = cues[reading]["properties"]
            self.assertEqual(list(properties), ["overview_count", field, "other_unsupported", "scope"])
            self.assertEqual(properties[field], value)
            self.assertEqual(properties["other_unsupported"], {"type": "boolean"})
            self.assertEqual(properties["scope"], overview)
        self.assertEqual(recipe_model.INVALID_REQUEST_REASONS, (*V10_REASONS, *CUE_REASONS))

    async def test_live_projection_keeps_closed_enumerations_only(self):
        result = await self.invoke(cue("contrast", ["known_booking_accounts", "booked_seats"]))
        projected = live._evidence(result.evidence)
        self.assertEqual((projected["count_reading"], projected["action_source"], projected["count_policy_rule"]),
                         ("contrast", "count_policy", "contrast"))
        self.assertNotIn("count_cue", projected)
        self.assertEqual(live._evidence(projected), projected)
        model_run = live._evidence((await self.invoke({"outcome": "declined"})).evidence)
        self.assertEqual((model_run["count_reading"], model_run["action_source"], model_run["count_policy_rule"]),
                         ("absent", "model", None))
        historical = {key: value for key, value in projected.items()
                      if key not in ("count_reading", "action_source", "count_policy_rule")}
        self.assertEqual(live._evidence(historical), historical)
        for changes in ({"count_policy_rule": None}, {"action_source": "model"}, {"count_policy_rule": "unknown"},
                        {"action_source": "kernel"}, {"count_reading": "absent"}, {"count_reading": "none"},
                        {"count_reading": "maybe"}):
            with self.subTest(changes=changes), self.assertRaises(p3_assets.P3Error):
                live._evidence({**projected, **changes})
        with self.assertRaises(p3_assets.P3Error):
            live._evidence({**model_run, "count_policy_rule": "contrast"})

    async def test_bedrock_fails_closed_before_transport(self):
        frozen = json.loads((ROOT / "tests/fixtures/recipe-output-schema-v2.json").read_text())
        canonical = json.dumps(frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        self.assertEqual(sha(canonical), bedrock.RECIPE_SCHEMA_SHA256)
        bedrock.converse_schema({"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME, "schema": frozen})
        with self.assertRaises(ModelError) as caught:
            bedrock.converse_schema({"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME,
                                     "schema": recipe_model.output_schema()})
        self.assertEqual(caught.exception.code, "invalid_input")
        sent = []
        client = provider.client_from_env(environ=BEDROCK_ENV, transport=httpx.MockTransport(
            lambda request: sent.append(request) or httpx.Response(500)))
        result = await recipe_model.interpret_recipe_and_execute(QUESTION, self.database, client)
        self.assertEqual((result.error.code, sent, result.evidence["stages"]["transport"]),
                         ("invalid_input", [], "not_run"))
        self.assertEqual((result.evidence["model_outcome"], result.evidence["action_source"]), (None, None))


class CountCueContractRulers(_Offline, unittest.TestCase):
    def setUp(self):
        self.guard()

    def test_policy_module_names_the_closed_rules(self):
        self.assertIsNotNone(count_policy, "grepbit/count_policy.py is not implemented")
        self.assertEqual(count_policy.RULES, RULES)
        self.assertEqual(count_policy.READINGS, ("none", "bound", "contrast", "generic"))

    def test_versions_context_and_instruction(self):
        self.assertEqual((recipe_model.CONTEXT_VERSION, recipe_model.INSTRUCTION_VERSION,
                          recipe_model.OUTPUT_CONTRACT, recipe_model.STRUCTURED_OUTPUT_VERSION),
                         ("learningops-recipe-context-v6", "recipe-selection-instruction-v7",
                          "recipe-request-json-v3", "recipe-structured-output-v3"))
        context = recipe_model.runtime_context()
        canonical = protocol.canonical_json
        rest = {k: v for k, v in context.items()
                if k not in ("version", "clarification", "recipes", "output_contract", "output_schema", "count_cues")}
        self.assertEqual(sha(canonical(rest)), V10_CONTEXT_REST)
        self.assertNotIn("count_basis", context["clarification"])
        self.assertEqual(sha(canonical(context["clarification"])), V10_CLARIFICATION_REST)
        self.assertEqual(sha(canonical(context["recipes"])), V10_RECIPES_WITHOUT_PEOPLE_COUNTS)
        self.assertIsInstance(context["count_cues"], str)
        for term in ("booked_seats", "known_booking_accounts", "attendance_visits", "distinct_people",
                     "overview_count", "other_unsupported"):
            self.assertIn(term, context["count_cues"])
        instruction = recipe_model.SYSTEM_INSTRUCTION
        self.assertNotIn(V10_COUNT_SENTENCE, instruction)
        prefix = next(i for i in range(len(instruction)) if sha(instruction[:i]) == V10_INSTRUCTION_PREFIX)
        suffix = next(i for i in range(len(instruction)) if sha(instruction[i:]) == V10_INSTRUCTION_SUFFIX)
        replacement = instruction[prefix:suffix]
        for required in ("overview_count", "metric_meaning requires a complete explicit Overview scope",
                         "amount choices include confirmed_booked_amount and reviewed alternative amount meanings",
                         "Alternatives do not add executable metrics"):
            self.assertIn(required, replacement)

    def test_readings_fixture_and_policy_match_accepted_oracles(self):
        document = json.loads(READINGS_FIXTURE.read_text())
        self.assertEqual(document["version"], "count-cue-readings-v1")
        self.assertEqual(document["provenance"]["packet_sha256"], PACKET_SHA256)
        readings = document["readings"]
        self.assertEqual(len(readings), 93)
        rows = [row for panel in READING_PANELS for row in panel_rows(panel)]
        self.assertEqual({sha(case["question"]) for case, _ in rows}, set(readings))
        compared = 0
        for case, oracle in rows:
            reading = reading_key(readings[sha(case["question"])])
            count_oracle = oracle["branch"] == "clarify" and oracle["clarification"]["kind"] == "count_basis"
            with self.subTest(case=case["case_id"]):
                if reading["overview_count"] == "none":
                    self.assertEqual(reading, {"overview_count": "none"})
                    self.assertFalse(count_oracle)
                    continue
                kind = reading["overview_count"]
                value = reading.get("meaning", reading.get("event", tuple(reading.get("meanings", ()))))
                self.assertEqual(set(reading), {"overview_count", "other_unsupported",
                                                {"bound": "meaning", "contrast": "meanings", "generic": "event"}[kind]})
                _, action, choices = reference(kind, value, reading["other_unsupported"])
                if action == "request":
                    self.assertEqual((oracle["branch"], oracle["recipe_id"]), ("answer", "overview"))
                elif action == "declined":
                    self.assertEqual(oracle["branch"], "decline")
                else:
                    self.assertTrue(count_oracle)
                    self.assertEqual({c["semantic_value"]["value"] for c in oracle["clarification"]["choices"]},
                                     set(choices))
                compared += 1
        self.assertEqual(compared, 33)

    def test_cued_fake_responses_differ_only_in_count_basis_actions(self):
        readings = json.loads(READINGS_FIXTURE.read_text())["readings"]
        for v1, digest, cued, cases_path, _, ids in FAKES:
            with self.subTest(file=cued):
                self.assertEqual(hashlib.sha256((ROOT / v1).read_bytes()).hexdigest(), digest)
                old, new = (json.loads((ROOT / path).read_text()) for path in (v1, cued))
                self.assertEqual(new["version"], old["version"])
                self.assertEqual([r["case_id"] for r in new["responses"]], [r["case_id"] for r in old["responses"]])
                changed = [n["case_id"] for o, n in zip(old["responses"], new["responses"]) if o != n]
                self.assertEqual(changed, ids)
                questions = {c["case_id"]: c["question"] for c in json.loads((ROOT / cases_path).read_text())["cases"]}
                for before, after in zip(old["responses"], new["responses"]):
                    if after["case_id"] not in ids:
                        continue
                    action = after["action"]
                    self.assertEqual(before["action"]["clarification"]["kind"], "count_basis")
                    scope = before["action"]["clarification"]["choices"][0]["semantic_value"]["scope"]
                    self.assertEqual(action["scope"], scope)
                    expected = (C01_CUE if cued.startswith("evals/p3/")
                                else reading_key(readings[sha(questions[after["case_id"]])]))
                    self.assertEqual({k: v for k, v in action.items() if k != "scope"}, expected)
                    self.assertEqual(list(action)[0], "overview_count")
                    self.assertEqual(list(action)[-2:], ["other_unsupported", "scope"])

    def test_fake_panels_grade_through_the_real_runtime(self):
        with tempfile.TemporaryDirectory(prefix="count-cue-fakes-", dir=ROOT / ".artifacts") as tmp:
            root = Path(tmp)
            database = root / "fixture.sqlite"
            fixture.build(database)
            for index, (v1, _, cued, _, panel, ids) in enumerate(FAKES):
                for label, responses in (("cued", cued), ("v1", v1)):
                    with self.subTest(panel=panel, responses=label):
                        run = root / f"{index}-{label}"
                        run.mkdir()
                        p3_eval.prepare(database, run / "prep", panel_path=ROOT / panel,
                                        responses_path=ROOT / responses)
                        report = asyncio.run(p3_eval.run_panel(
                            database, run / "out", manifest_path=run / "prep/manifest.json",
                            panel_path=ROOT / panel, responses_path=ROOT / responses))
                        self.assertEqual(report["status"], "complete")
                        wrong = [row for row in report["results"]
                                 if row["outcome"] not in ("complete_correct", "correct_clarification",
                                                           "correct_decline")]
                        if label == "cued":
                            self.assertEqual(wrong, [])
                            policy = [row["case_id"] for row in report["results"]
                                      if row["evidence"]["action_source"] == "count_policy"]
                            self.assertEqual(policy, ids)
                        else:
                            self.assertEqual([row["case_id"] for row in wrong], ids)
                            self.assertEqual({row["evidence"]["invalid_request_reason"] for row in wrong},
                                             {"clarification_shape"})

    def test_v11_registration_preserves_v10(self):
        index = registry.load_index()
        ids = [row["candidate_id"] for row in index["entries"]]
        self.assertIn(CANDIDATE, ids, "Register p3-count-cue-policy-v11 after the implementation")
        self.assertEqual((index["current"], ids.index(CANDIDATE)), (CANDIDATE, ids.index(V10) + 1))
        self.assertEqual(hashlib.sha256((registry.DIRECTORY / f"{V10}.json").read_bytes()).hexdigest(),
                         V10_ENTRY_SHA256)
        new, old = registry.load_entry(CANDIDATE), registry.load_entry(V10)
        self.assertEqual(new["ancestor"], V10)
        self.assertNotEqual(new["semantic_identity_sha256"], old["semantic_identity_sha256"])
        self.assertIn("grepbit/count_policy.py", new["runtime_files_sha256"])
        self.assertEqual(registry.check()["candidate_id"], CANDIDATE)


if __name__ == "__main__":
    unittest.main()
