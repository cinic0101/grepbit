"""Bounded structural observations, unchanged strict rejection, and mock-only export."""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch

import httpx

from grepbit import json_diagnostics, model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError
from tools import fixture, recipe_smoke


BASE = "https://json-diagnostics-private.invalid/v1"
KEY = "dummy-json-diagnostics-api-key"
KEY_CANARY = "DIAGNOSTIC_KEY_CANARY"
VALUE_CANARY = "DIAGNOSTIC_VALUE_CANARY"
REASONING_CANARY = "DIAGNOSTIC_REASONING_CANARY"
QUESTION = "How were bookings at CTR-A01 in March 2026?"
MOCK_HTTP_ATTEMPTS = 0
RECIPES = ("overview", "compare", "breakdown")
DIAGNOSTIC = "invalid_json_fingerprint"
FIELDS = {
    "version", "analysis_limited", "byte_length", "char_length", "has_ascii", "has_non_ascii",
    "leading_whitespace_bytes", "trailing_whitespace_bytes", "first_non_whitespace_class",
    "last_non_whitespace_class", "starts_with_object", "starts_with_array",
    "starts_with_markdown_fence", "contains_markdown_fence", "starts_with_think_tag",
    "contains_think_tag", "newline_count", "decoder_error_category", "decoder_line",
    "decoder_column", "decoder_offset", "raw_decode_one_value", "parsed_root_type",
    "trailing_non_whitespace_bytes", "duplicate_key", "nonfinite", "invalid_unicode",
}
CATEGORIES = {
    "malformed_json", "trailing_content", "duplicate_key", "nonfinite", "invalid_unicode",
    "depth_limit", "decoder_limit", "size_limit", "none",
}
CLASSES = {"object", "array", "backtick", "angle", "quote", "alpha", "other", "empty", "unavailable"}
ROOT_TYPES = {"object", "array", "string", "number", "boolean", "null"}
P2_IDENTITY = {
    "context_version": "learningops-recipe-context-v1", "output_contract": "recipe-request-json-v1",
    "instruction_version": "recipe-selection-instruction-v1",
    "catalog_sha256": "9027e2af35e49a790fd4c3e985ccff12e92868946f9398506ccfa7e623c897c5",
    "context_sha256": "7de6ed524fa5ddaeb530038c3a7b127461a7edb557749b61ef28558d359d6b87",
    "output_contract_sha256": "ac6ca4d71fbe6a69c978231458bc6d4be7fca3f5ebbee732d4cdedad0dec9a02",
    "instruction_sha256": "cbf9e613e6b2a8e42ff758f9b0ceed1d2b4227be1a4d5d17cea1aee62b1cb270",
    "system_message_sha256": "5893fb44fbad47c3e5b2f970e0165d0caaf062e75ac9af88dc80e6dcd4a2ffab",
}


def proposal(recipe="overview"):
    def month(number):
        return {"start": f"2026-{number:02}-01T00:00:00+08:00",
                "end": f"2026-{number + 1:02}-01T00:00:00+08:00", "timezone": "Asia/Taipei"}
    requests = {
        "overview": {**month(3), "center_code": "CTR-A01"},
        "compare": {role: {**month(number), "metrics": ["confirmed_booked_amount"]}
                    for role, number in (("current", 3), ("baseline", 2))},
        "breakdown": {**month(3), "top_k": 2},
    }
    return {"outcome": "request", "recipe_id": recipe, "recipe_version": "0.1", "request": requests[recipe]}


def invalid_cases():
    valid = json.dumps(proposal(), separators=(",", ":"))
    duplicate = f'"{KEY_CANARY}":0,"{KEY_CANARY}":"{VALUE_CANARY}"'
    cases = [
        ("fence", "```json\n" + valid + "\n```", "malformed_json", None,
         {"starts_with_markdown_fence": True, "contains_markdown_fence": True,
          "first_non_whitespace_class": "backtick", "last_non_whitespace_class": "backtick"}),
        ("leading_prose", "Answer: " + valid, "malformed_json", None,
         {"first_non_whitespace_class": "alpha"}),
        ("think", "<think>" + VALUE_CANARY + "</think>" + valid, "malformed_json", None,
         {"starts_with_think_tag": True, "contains_think_tag": True, "first_non_whitespace_class": "angle"}),
        ("closing_think", "</think>" + valid, "malformed_json", None,
         {"starts_with_think_tag": True, "contains_think_tag": True}),
        ("trailing_prose", valid + " " + VALUE_CANARY, "trailing_content", "object",
         {"trailing_non_whitespace_bytes": len(VALUE_CANARY), "last_non_whitespace_class": "alpha"}),
        ("concatenated", valid + valid, "trailing_content", "object",
         {"trailing_non_whitespace_bytes": len(valid.encode())}),
        ("duplicate", "{" + duplicate + "}", "duplicate_key", "object", {"duplicate_key": True}),
        ("nested_duplicate", '{"outer":[{' + duplicate + "}]}", "duplicate_key", "object",
         {"duplicate_key": True}),
        ("nan", "NaN", "nonfinite", "number", {"nonfinite": True}),
        ("infinity", "Infinity", "nonfinite", "number", {"nonfinite": True}),
        ("negative_infinity", "-Infinity", "nonfinite", "number", {"nonfinite": True}),
        ("overflow", '{"value":1e999}', "nonfinite", "object", {"nonfinite": True}),
        ("escaped_surrogate_value", '{"' + KEY_CANARY + '":"\\ud800"}', "invalid_unicode", "object",
         {"invalid_unicode": True, "has_non_ascii": False}),
        ("escaped_surrogate_key", '{"\\ud800":"' + VALUE_CANARY + '"}', "invalid_unicode", "object",
         {"invalid_unicode": True}),
        ("truncated", '{"' + KEY_CANARY + '":"' + VALUE_CANARY, "malformed_json", None, {}),
        ("non_json_leading_space", "\u00a0" + valid, "malformed_json", None,
         {"leading_whitespace_bytes": 0, "first_non_whitespace_class": "other"}),
        ("bom", "\ufeff" + valid, "malformed_json", None,
         {"leading_whitespace_bytes": 0, "first_non_whitespace_class": "other"}),
        ("non_json_trailing_space", valid + "\u00a0", "trailing_content", "object",
         {"trailing_whitespace_bytes": 0, "trailing_non_whitespace_bytes": 2}),
        ("empty", "", "malformed_json", None, {"first_non_whitespace_class": "empty"}),
        ("only_whitespace", " \t\r\n", "malformed_json", None,
         {"first_non_whitespace_class": "empty", "last_non_whitespace_class": "empty"}),
        ("multiple_observations", '{"' + KEY_CANARY + '":NaN,"' + KEY_CANARY + '":"\\ud800"}',
         "invalid_unicode", "object", {"duplicate_key": True, "nonfinite": True, "invalid_unicode": True}),
    ]
    return [(name, content, {"decoder_error_category": category, "raw_decode_one_value": root is not None,
                            "parsed_root_type": root, **extra})
            for name, content, category, root, extra in cases]


class JsonDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport"):
            guard = patch(target, side_effect=AssertionError("Real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(GatewayConfig, "from_env", side_effect=AssertionError("Real configuration forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        temporary = tempfile.TemporaryDirectory(dir=recipe_smoke.ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / "diagnostics.sqlite"
        self.sent = []

    def assert_private(self, value):
        canaries = (BASE, KEY, KEY_CANARY, VALUE_CANARY, REASONING_CANARY, "json-diagnostics-private.invalid")
        self.assertFalse(any(secret in str(value) for secret in canaries), "Input or configuration escaped")

    def assert_fingerprint(self, observed, **expected):
        self.assert_private(observed)
        self.assertIs(type(observed), dict)
        self.assertTrue(set(observed) == FIELDS, "Fingerprint fields are not the closed contract")
        self.assertTrue(all(type(value) in (str, int, bool, type(None)) for value in observed.values()),
                        "Fingerprint must be flat primitive metadata")
        vocabulary = CLASSES | ROOT_TYPES | CATEGORIES | {"invalid-json-structure-v1"}
        self.assertTrue(all(not isinstance(value, str) or value in vocabulary for value in observed.values()),
                        "Fingerprint contains an open-ended string")
        self.assertEqual(observed["version"], "invalid-json-structure-v1")
        self.assertTrue(observed["decoder_error_category"] in CATEGORIES)
        for key in ("first_non_whitespace_class", "last_non_whitespace_class"):
            self.assertTrue(observed[key] in CLASSES, "Invalid character class")
        self.assertTrue(observed["parsed_root_type"] is None or observed["parsed_root_type"] in ROOT_TYPES)
        numeric = {"byte_length", "char_length", "leading_whitespace_bytes", "trailing_whitespace_bytes",
                   "newline_count", "decoder_line", "decoder_column", "decoder_offset", "trailing_non_whitespace_bytes"}
        textual = {"version", "first_non_whitespace_class", "last_non_whitespace_class",
                   "decoder_error_category", "parsed_root_type"}
        for key, value in observed.items():
            if key in numeric:
                self.assertIn(type(value), (int, type(None)))
            elif key not in textual:
                self.assertIn(type(value), (bool, type(None)))
            if key in numeric and value is not None:
                self.assertGreaterEqual(value, 1 if key in ("decoder_line", "decoder_column") else 0)
        if observed["char_length"] is not None:
            self.assertLessEqual(observed["char_length"], 131072)
            if observed["decoder_offset"] is not None:
                self.assertLessEqual(observed["decoder_offset"], observed["char_length"])
        self.assertEqual(json.loads(json.dumps(observed, allow_nan=False)), observed)
        for key, value in expected.items():
            self.assertEqual(observed[key], value, key)

    def assert_strict_rejection(self, content):
        with self.assertRaises(ModelError) as caught:
            model.strict_json(content)
        self.assertEqual(caught.exception.code, "invalid_json")
        self.assert_private(str(caught.exception))

    def client(self, content, *, on_response=None):
        self.sent = []
        document = {
            "model": MODEL, "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": content, "reasoning_content": json.dumps(proposal()),
                "reasoning": REASONING_CANARY, KEY_CANARY: VALUE_CANARY,
            }}], "provider_extension": {KEY_CANARY: VALUE_CANARY},
        }
        body = json.dumps(document, ensure_ascii=True, allow_nan=False).encode()

        def respond(request):
            global MOCK_HTTP_ATTEMPTS
            MOCK_HTTP_ATTEMPTS += 1
            self.sent.append(request)
            if on_response:
                on_response()
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})

        return GatewayClient(GatewayConfig(BASE, KEY), transport=httpx.MockTransport(respond))

    async def invoke(self, content, *, execute=False):
        client = self.client(content)
        with ExitStack() as stack:
            diagnostic = stack.enter_context(patch.object(
                recipe_model, DIAGNOSTIC, wraps=recipe_model.invalid_json_fingerprint))
            executions = {name: stack.enter_context(patch.object(
                recipe_model, "execute_" + name, wraps=getattr(recipe_model, "execute_" + name)))
                for name in RECIPES}
            if not execute:
                stack.enter_context(patch.object(
                    sqlite3, "connect", side_effect=AssertionError("Rejected content opened a database")))
            result = await recipe_model.interpret_recipe_and_execute(QUESTION, self.database, client)
        self.assertEqual((len(self.sent), client.http_attempts, result.evidence["client_http_attempts"]), (1, 1, 1))
        self.assertEqual(sum(call.call_count for call in executions.values()), int(execute))
        for value in (result.evidence, repr(result), repr(result.proposal), repr(result.analysis_pack),
                      repr(result.error), str(result.error), client.safe_export(result.evidence)):
            self.assert_private(value)
        if result.error:
            self.assert_private("".join(traceback.format_exception(result.error)))
            self.assertIsNone(result.error.__traceback__)
            self.assertIsNone(result.error.__cause__)
            self.assertIsNone(result.error.__context__)
            self.assertIsNone(result.analysis_pack)
            self.assertEqual(result.evidence["stages"]["kernel_execution"], "not_run")
        return result, diagnostic

    def test_valid_root_types_preserve_strict_acceptance(self):
        cases = [("{}", {}, "object"), ("[]", [], "array"), ('"text"', "text", "string"),
                 ('"\u6e2c"', "\u6e2c", "string"), ("42", 42, "number"), ("1.5", 1.5, "number"),
                 ("true", True, "boolean"), ("false", False, "boolean"), ("null", None, "null")]
        for index, (content, value, root) in enumerate(cases):
            with self.subTest(case=index, root=root):
                decoded = model.strict_json(content)
                self.assertIs(type(decoded), type(value))
                self.assertTrue(decoded == value, "Strict JSON changed a valid value")
                self.assert_fingerprint(
                    json_diagnostics.invalid_json_fingerprint(content),
                    analysis_limited=False, decoder_error_category="none", raw_decode_one_value=True,
                    parsed_root_type=root, trailing_non_whitespace_bytes=0, duplicate_key=False,
                    nonfinite=False, invalid_unicode=False, char_length=len(content), byte_length=len(content.encode()),
                    starts_with_object=root == "object", starts_with_array=root == "array", has_ascii=True)

    def test_invalid_matrix_preserves_strict_rejection_and_distinguishes_structure(self):
        for name, content, expected in invalid_cases():
            with self.subTest(case=name):
                self.assert_strict_rejection(content)
                self.assert_fingerprint(json_diagnostics.invalid_json_fingerprint(content), **expected)
                self.assert_strict_rejection(content)

    def test_ascii_whitespace_counts_and_decoder_coordinates(self):
        cases = [
            (' \t\r\n"\u6e2c"\n \t', {"char_length": 10, "byte_length": 12, "newline_count": 2,
                                    "leading_whitespace_bytes": 4, "trailing_whitespace_bytes": 3,
                                    "trailing_non_whitespace_bytes": 0, "decoder_error_category": "none"}),
            (' \n{"x":\n}', {"decoder_error_category": "malformed_json", "decoder_line": 3,
                            "decoder_column": 1, "decoder_offset": 8, "newline_count": 2}),
            ('{"x":"\u6e2c"}\n \tTAIL', {"char_length": 16, "byte_length": 18, "decoder_line": 2,
                                       "decoder_column": 3, "decoder_offset": 12,
                                       "trailing_non_whitespace_bytes": 4, "decoder_error_category": "trailing_content"}),
            (" \t\r\n", {"leading_whitespace_bytes": 4, "trailing_whitespace_bytes": 4,
                        "decoder_line": 2, "decoder_column": 1, "decoder_offset": 4,
                        "first_non_whitespace_class": "empty", "last_non_whitespace_class": "empty"}),
        ]
        for index, (content, expected) in enumerate(cases):
            with self.subTest(case=index):
                self.assert_fingerprint(json_diagnostics.invalid_json_fingerprint(content), **expected)

    def test_marker_flags_are_exact_observations_even_inside_valid_strings(self):
        for index, (content, fence, think, valid) in enumerate((
            ('"```<think>text</think>"', True, True, True),
            ('{"text":"``` </think>"}', True, True, True),
            ('"\\u003cthink\\u003e"', False, False, True),
            ("<THINK>{}", False, False, False),
            ("<thinker>{}", False, False, False),
            ('<think mode="on">{}', False, False, False),
        )):
            with self.subTest(case=index):
                self.assert_fingerprint(
                    json_diagnostics.invalid_json_fingerprint(content),
                    contains_markdown_fence=fence, contains_think_tag=think,
                    starts_with_markdown_fence=False, starts_with_think_tag=False,
                    raw_decode_one_value=valid, decoder_error_category="none" if valid else "malformed_json")
                if valid:
                    model.strict_json(content)
                else:
                    self.assert_strict_rejection(content)

    def test_character_limit_is_exact_and_oversize_input_is_not_examined(self):
        for character in ("x", "\u6e2c"):
            with self.subTest(utf8_width=len(character.encode())):
                content = '"' + character * 131070 + '"'
                self.assert_fingerprint(
                    json_diagnostics.invalid_json_fingerprint(content), analysis_limited=False,
                    char_length=131072, byte_length=len(content.encode()), raw_decode_one_value=True,
                    parsed_root_type="string", decoder_error_category="none")

        class Unexamined(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("Oversize input was examined")

        with patch.object(json_diagnostics.json, "JSONDecoder", side_effect=AssertionError("Oversize decoding")):
            observed = json_diagnostics.invalid_json_fingerprint(Unexamined("x" * 131073))
        self.assert_fingerprint(observed, analysis_limited=True, decoder_error_category="size_limit",
                                raw_decode_one_value=False, first_non_whitespace_class="unavailable",
                                last_non_whitespace_class="unavailable")
        known = {"version", "analysis_limited", "decoder_error_category", "raw_decode_one_value",
                 "first_non_whitespace_class", "last_non_whitespace_class"}
        self.assertTrue(all(observed[key] is None for key in FIELDS - known), "Unexamined fields must stay unknown")

    def test_literal_surrogates_and_valid_escaped_pairs_are_distinct(self):
        for index, content in enumerate(('"' + chr(0xD800) + '"', chr(0xD800))):
            with self.subTest(case=index):
                self.assert_strict_rejection(content)
                self.assert_fingerprint(json_diagnostics.invalid_json_fingerprint(content),
                                        byte_length=None, invalid_unicode=True, has_non_ascii=True, has_ascii=index == 0,
                                        decoder_error_category="invalid_unicode",
                                        decoder_line=None, decoder_column=None, decoder_offset=None)
        content = '"\\ud83d\\ude00"'
        self.assertTrue(model.strict_json(content) == "\U0001f600")
        self.assert_fingerprint(json_diagnostics.invalid_json_fingerprint(content), invalid_unicode=False,
                                has_non_ascii=False, raw_decode_one_value=True, decoder_error_category="none")

    def test_depth_and_numeric_decoder_limits_keep_fixed_categories(self):
        previous = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, previous)
        sys.set_int_max_str_digits(640)
        depth = sys.getrecursionlimit() + 50
        for category, content in (("depth_limit", "[" * depth + "0" + "]" * depth),
                                  ("decoder_limit", "9" * 641)):
            with self.subTest(category=category):
                self.assert_strict_rejection(content)
                self.assert_fingerprint(json_diagnostics.invalid_json_fingerprint(content),
                                        decoder_error_category=category, raw_decode_one_value=False,
                                        parsed_root_type=None, decoder_offset=None, decoder_line=None, decoder_column=None)

    async def test_invalid_content_matrix_has_one_attempt_and_no_repair_or_execution(self):
        for name, content, expected in invalid_cases():
            with self.subTest(case=name):
                result, diagnostic = await self.invoke(content)
                self.assertEqual(result.error.code, "invalid_json")
                self.assertEqual(result.error.stage, "json_parse")
                self.assertEqual(result.evidence["stages"]["response_validation"], "passed")
                self.assertEqual(result.evidence["stages"]["json_parse"], "failed")
                self.assertEqual(result.evidence["stages"]["request_validation"], "not_run")
                self.assertIsNone(result.proposal)
                self.assertEqual(diagnostic.call_count, 1)
                self.assertTrue(diagnostic.call_args.args == (content,), "Diagnostic input was normalized or replaced")
                self.assert_fingerprint(result.evidence[DIAGNOSTIC], **expected)

    async def test_valid_native_recipes_preserve_context_and_have_no_diagnostic(self):
        fixture.build(self.database)
        for recipe in RECIPES:
            with self.subTest(recipe=recipe):
                result, diagnostic = await self.invoke(json.dumps(proposal(recipe)), execute=True)
                self.assertIsNone(result.error)
                self.assertEqual(result.proposal.recipe_id, recipe)
                self.assertEqual(result.analysis_pack.status, "complete")
                self.assertEqual(result.evidence["context_identity"], P2_IDENTITY)
                self.assertEqual(set(result.evidence["stages"].values()), {"passed"})
                self.assertNotIn(DIAGNOSTIC, result.evidence)
                self.assertEqual(diagnostic.call_count, 0)
                messages = json.loads(self.sent[0].content)["messages"]
                self.assertTrue(messages == recipe_model.messages_for(QUESTION), "Shared messages changed")
                if recipe == "overview":
                    self.assertEqual([fact.value for fact in result.analysis_pack.facts], [68000, 4, 6])

    async def test_valid_wrong_schema_and_decline_never_get_parse_diagnostics(self):
        wrong_recipe = {**proposal(), "recipe_id": "unknown"}
        wrong_native = proposal()
        wrong_native["request"]["center_code"] = 123
        for index, candidate in enumerate(({}, [], wrong_recipe, wrong_native,
                                           {KEY_CANARY: VALUE_CANARY}, {"outcome": "declined"})):
            with self.subTest(case=index):
                content = json.dumps(candidate)
                self.assertTrue(model.strict_json(content) == candidate, "Valid JSON was rejected")
                result, diagnostic = await self.invoke(content)
                self.assertEqual(result.error.code, "model_declined" if index == 5 else "invalid_request")
                self.assertEqual(result.evidence["stages"]["json_parse"], "passed")
                self.assertNotIn(DIAGNOSTIC, result.evidence)
                self.assertEqual(diagnostic.call_count, 0)

    async def test_literal_outer_surrogate_fails_envelope_validation_not_json_parse(self):
        result, diagnostic = await self.invoke(chr(0xD800))
        self.assertEqual(result.error.code, "invalid_response")
        self.assertEqual(result.error.stage, "response_validation")
        self.assertEqual(result.evidence["stages"]["json_parse"], "not_run")
        self.assertNotIn(DIAGNOSTIC, result.evidence)
        self.assertEqual(diagnostic.call_count, 0)

    async def test_resource_failures_are_diagnostic_not_fallback_or_retry(self):
        previous = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, previous)
        sys.set_int_max_str_digits(640)
        depth = sys.getrecursionlimit() + 50
        for category, content in (("depth_limit", "[" * depth + "0" + "]" * depth),
                                  ("decoder_limit", "9" * 641)):
            with self.subTest(category=category):
                result, diagnostic = await self.invoke(content)
                self.assertEqual(result.error.code, "invalid_json")
                self.assertEqual(diagnostic.call_count, 1)
                self.assert_fingerprint(result.evidence[DIAGNOSTIC], decoder_error_category=category,
                                        raw_decode_one_value=False)

    async def test_diagnostic_runs_only_after_unchanged_content_strict_rejection(self):
        strict, events = model.strict_json, []

        def checked(content, **kwargs):
            try:
                value = strict(content, **kwargs)
            except ModelError:
                events.append("content_rejected")
                raise
            events.append("envelope_accepted")
            return value

        def diagnosed(content):
            self.assertEqual(events, ["envelope_accepted", "content_rejected"])
            events.append("diagnostic")
            return json_diagnostics.invalid_json_fingerprint(content)

        with (patch.object(model, "strict_json", side_effect=checked) as parser,
              patch.object(recipe_model, DIAGNOSTIC, side_effect=diagnosed)):
            result, diagnostic = await self.invoke("```json\n" + json.dumps(proposal()) + "\n```")
        self.assertEqual((parser.call_count, diagnostic.call_count), (2, 1))
        self.assertEqual(events, ["envelope_accepted", "content_rejected", "diagnostic"])
        self.assertEqual(result.error.code, "invalid_json")

    async def test_runner_persists_one_invalid_input_diagnostic_without_raw_payload(self):
        fixture.build(self.database)
        prepared, output = self.root / "prepared", self.root / "panel"
        recipe_smoke.prepare(self.database, prepared)
        content = '{"' + KEY_CANARY + '":"' + VALUE_CANARY + '","' + KEY_CANARY + '":0}'
        clock = [0.0]

        def expire():
            clock[0] = 720.0

        client = self.client(content, on_response=expire)
        report = await recipe_smoke.run_panel(
            self.database, output, manifest_path=prepared / "manifest.json", client=client, clock=lambda: clock[0])
        self.assertEqual((report["status"], report["stop_reason"]), ("stopped", "panel_budget"))
        self.assertEqual((len(self.sent), client.http_attempts, report["client_http_attempts"],
                          report["possible_in_flight_attempts"], report["live_model_attempts"]), (1, 1, 1, 0, 0))
        first = report["results"][0]
        self.assertEqual((first["status"], first["outcome"], first["error_code"]),
                         ("completed", "invalid_output", "invalid_json"))
        self.assertEqual(set(first["grading"].values()), {"not_run"})
        self.assertTrue(all(row["status"] == "not_run" for row in report["results"][1:]))
        self.assert_fingerprint(first["evidence"][DIAGNOSTIC], decoder_error_category="duplicate_key", duplicate_key=True)
        durable = json.loads((output / "report.json").read_text())
        self.assertTrue(durable == report, "Writer changed diagnostic evidence")
        self.assertTrue(client.safe_export(report) == report, "Export required evidence redaction")
        for directory in (prepared, output):
            for path in directory.iterdir():
                self.assert_private(path.read_text())


if __name__ == "__main__":
    unittest.main()
