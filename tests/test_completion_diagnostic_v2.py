"""Offline v2 diagnostic lifecycle, profile isolation, and structural privacy."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import MODEL
from tools import candidate_registry, evaluate, fixture, p3_completion_diagnostic as diagnostic, recipe_smoke


class CompletionDiagnosticV2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Only synthetic lifecycle fixtures follow the current registered
        # checkout. The consumed diagnostic's production identity stays v3.
        self.enterContext(patch.object(diagnostic, "CANDIDATE", candidate_registry.current()["candidate_id"]))
        (evaluate.ROOT / ".artifacts").mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="compare-v2-offline-", dir=evaluate.ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.profile = replace(diagnostic.V2, slot=(self.root / "run").relative_to(evaluate.ROOT).as_posix())
        self.db = self.root / "fixture.sqlite"
        fixture.build(self.db)
        self.commit = "1" * 40
        source = {"git_commit": self.commit, "branch": "dev", "worktree_dirty": False,
                  "files_sha256": {}, "context": recipe_model.context_identity(),
                  "structured_output": recipe_model.structured_output_identity()}
        self.enterContext(patch.object(recipe_smoke, "_source_identity", side_effect=lambda: deepcopy(source)))
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "socket.getaddrinfo", "httpx.AsyncHTTPTransport",
                       "grepbit.gateway.GatewayConfig.from_env"):
            self.enterContext(patch(target, side_effect=AssertionError("external access forbidden")))
        self.packet = self.root / "packet.json"
        self.authorization = self.root / "authorization.json"

    def prepare(self):
        diagnostic.prepare(self.db, self.packet, accepted_commit=self.commit, profile=self.profile)
        diagnostic.bind_authorization(self.packet, self.authorization, self.profile.grant, profile=self.profile)

    @staticmethod
    def envelope(content, *, reasoning="PRIVATE_REASONING_CANARY", model=MODEL):
        return {"model": model, "choices": [{"index": 0, "finish_reason": "length",
                "message": {"role": "assistant", "content": content, "reasoning_content": reasoning}}]}

    async def run_synthetic(self, content, *, clock=None):
        self.prepare()
        sent = []
        def factory(_env, expected_sha):
            def respond(request):
                sent.append(request)
                self.assertEqual(hashlib.sha256(request.content).hexdigest(), expected_sha)
                return httpx.Response(200, json=self.envelope(content))
            config = diagnostic.DiagnosticGatewayConfig("http://v2-synthetic.invalid/v1", "PRIVATE_KEY_CANARY")
            return diagnostic.DiagnosticGatewayClient(config, expected_sha, transport=httpx.MockTransport(respond))
        kwargs = {} if clock is None else {"clock": clock}
        result = await diagnostic.run_live(self.db, self.packet, self.authorization,
                                           accepted_commit=self.commit, env_file=self.root / "unused.env",
                                           client_factory=factory, profile=self.profile, **kwargs)
        return result, sent

    async def test_one_call_exact_wire_structural_counts_privacy_and_readback(self):
        content = " \t\n\r" * 16 + "éx" * 32
        result, sent = await self.run_synthetic(content)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["client_http_attempts"], 1)
        self.assertEqual([row["case_id"] for row in result["results"]], ["dev-C2.en"])
        self.assertEqual(len(sent), 1)
        packet = json.loads(self.packet.read_text())
        self.assertEqual(hashlib.sha256(sent[0].content).hexdigest(), packet["selected"][0]["request_sha256"])
        self.assertEqual(json.loads(sent[0].content)["max_tokens"], 2048)
        self.assertEqual(len(packet["selected"]), 1)
        self.assertEqual(set(packet["source_pins"]), {"tools/evaluate.py", "tools/candidate_registry.py",
                                                      "tools/p3_completion_diagnostic.py"})
        observation = result["results"][0]["observation"]
        self.assertEqual(observation["json_parse"], "error")
        self.assertEqual(observation["content_bytes"], len(content.encode()))
        self.assertEqual(observation["json_whitespace_char_count"], 64)
        self.assertEqual(observation["non_whitespace_char_count"], 64)
        self.assertEqual(observation["longest_json_whitespace_run"], 64)
        self.assertEqual(observation["max_repeated_32_char_whitespace_block_count"], 2)
        self.assertEqual(observation["max_repeated_32_char_nonwhitespace_block_count"], 2)
        self.assertEqual(observation["max_repeated_32_char_block_count"], 2)
        self.assertEqual(diagnostic.read_report(self.root / "run/report.json", self.profile), result)
        for path in (self.root / "run").iterdir():
            if path.is_file():
                raw = path.read_bytes()
                for canary in ("PRIVATE_REASONING_CANARY", "PRIVATE_KEY_CANARY", "éx"):
                    self.assertNotIn(canary.encode(), raw)

    async def test_reasoning_only_archive_keeps_content_counts_unknown(self):
        result, _ = await self.run_synthetic(None)
        observation = result["results"][0]["observation"]
        self.assertEqual(observation["json_parse"], "absent")
        self.assertIsNone(observation["content_bytes"])
        for field in diagnostic.V2_OBS_FIELDS - diagnostic.OBS_FIELDS:
            self.assertIsNone(observation[field])
        self.assertEqual(diagnostic.read_report(self.root / "run/report.json", self.profile), result)

    def test_empty_and_malformed_content_counts_and_v1_keyset(self):
        for content, whitespace, other, longest in (("", 0, 0, 0), ("{bad", 0, 4, 0),
                                                     ("\t\n", 2, 0, 2), ("é", 0, 1, 0)):
            with self.subTest(content=content):
                raw = json.dumps(self.envelope(content), ensure_ascii=False).encode()
                observed = diagnostic.observe(raw, 200, self.profile)
                self.assertEqual((observed["json_whitespace_char_count"],
                                  observed["non_whitespace_char_count"],
                                  observed["longest_json_whitespace_run"]),
                                 (whitespace, other, longest))
                diagnostic._observation(observed, self.profile)
                self.assertEqual(set(diagnostic.observe(raw, 200)), diagnostic.OBS_FIELDS)

    def test_cross_field_tamper_rejected(self):
        content = " " * 64 + "éx" * 32
        observation = diagnostic.observe(json.dumps(self.envelope(content), ensure_ascii=False).encode(),
                                         200, self.profile)
        changes = (
            {"non_whitespace_char_count": observation["content_bytes"] + 1},
            {"content_bytes": 1},
            {"content_bytes": 1000},
            {"longest_json_whitespace_run": 0},
            {"max_repeated_32_char_whitespace_block_count": 3},
            {"max_repeated_32_char_nonwhitespace_block_count": 100},
            {"max_repeated_32_char_block_count": 0},
            {"json_whitespace_char_count": True},
        )
        for change in changes:
            with self.subTest(change=change):
                tampered = {**observation, **change}
                with self.assertRaises(diagnostic.DiagnosticError):
                    diagnostic._observation(tampered, self.profile)
        absent = diagnostic.observe(json.dumps(self.envelope(None)).encode(), 200, self.profile)
        absent["json_whitespace_char_count"] = 0
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic._observation(absent, self.profile)

    def test_whitespace_run_count_requires_separators(self):
        uninterrupted = diagnostic.observe(
            json.dumps(self.envelope(" " * 64)).encode(), 200, self.profile)
        impossible = {**uninterrupted, "longest_json_whitespace_run": 32}
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic._observation(impossible, self.profile)

        separated = diagnostic.observe(
            json.dumps(self.envelope(" " * 32 + "x" + " " * 32)).encode(), 200, self.profile)
        self.assertEqual((separated["json_whitespace_char_count"],
                          separated["non_whitespace_char_count"],
                          separated["longest_json_whitespace_run"]), (64, 1, 32))
        diagnostic._observation(separated, self.profile)

    def test_wrong_grant_version_case_and_slot_fail_before_binding(self):
        diagnostic.prepare(self.db, self.packet, accepted_commit=self.commit, profile=self.profile)
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic.bind_authorization(self.packet, self.authorization, diagnostic.GRANT,
                                          profile=self.profile)
        self.assertFalse(self.authorization.exists())
        with self.assertRaises(diagnostic.DiagnosticError):
            diagnostic._packet_file(self.packet)  # v1 reader cannot consume v2.
        packet = json.loads(self.packet.read_text())
        for key, value in (("version", diagnostic.VERSION), ("case_ids", ["dev-A3.en"]),
                           ("run_slot", diagnostic.SLOT)):
            broken = deepcopy(packet)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(diagnostic.DiagnosticError):
                diagnostic._packet(broken, self.profile)

    async def test_replay_rejected_before_credentials_and_deadline_is_180(self):
        result, sent = await self.run_synthetic('{"outcome":"declined"}')
        self.assertEqual(len(sent), 1)
        with self.assertRaises(Exception):
            await diagnostic.run_live(self.db, self.packet, self.authorization,
                accepted_commit=self.commit, env_file=self.root / "unused.env",
                client_factory=lambda *_: self.fail("credential access on replay"), profile=self.profile)
        self.assertEqual(result["status"], "complete")

    async def test_pre_send_budget_stops_without_model_call(self):
        self.prepare()
        samples = 0
        def clock():
            nonlocal samples
            samples += 1
            return 0.0 if samples == 1 else 181.0
        result = await diagnostic.run_live(self.db, self.packet, self.authorization,
            accepted_commit=self.commit, env_file=self.root / "unused.env",
            client_factory=lambda *_: self.fail("client construction after deadline"),
            profile=self.profile, clock=clock)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["stop_reason"], "budget")
        self.assertEqual(result["client_http_attempts"], 0)
        self.assertEqual(result["elapsed_seconds"], 181.0)


if __name__ == "__main__":
    unittest.main()
