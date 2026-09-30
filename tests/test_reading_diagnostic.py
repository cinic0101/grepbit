"""Reading diagnostic rulers (reading-diagnostic-v1, #79): synthetic panels and mock transports only; no live call."""
import hashlib
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate as runner, p3_assets
from tools import reading_diagnostic as reading
from test_evaluate import BASE, GRANT, KEY, SHA, EvaluateHarness, envelope


def _reading(decision="answer", reason="all_supported", **fields):
    base = {"analysis": "overview", "count_request": "none", "count_event": "not_applicable",
            "orientation": "not_applicable", "unsupported": "none"}
    return {"reading": {**base, **fields}, "verdict": {"decision": decision, "reason": reason}}


_REASONS = {"count_basis": "count_basis_unresolved", "comparison_roles": "orientation_unresolved",
            "center": "center_unresolved", "metric_meaning": "metric_meaning_unresolved"}


class ReadingDiagnosticTests(EvaluateHarness):
    def setUp(self):
        super().setUp()
        self.inputs = p3_assets.load_panel(self.root / "development-panel-v1.json").cases
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        self.recorded = 0
        self.diagnostic_sent = []

    # ----------------------------------------------------------------- helpers
    def production_client(self, declined=()):
        cases = self.inputs

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            action = {"outcome": "declined"} if case.case_id in declined else self.by_oracle[case.oracle_id]
            return httpx.Response(200, json=envelope(json.dumps(action)))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def source_run(self, grant=901, *, declined=()):
        packet = self.prepare()
        output = self.output()
        authorization = self.root / f"authorization-{output.name}.json"
        runner.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
        await self.run_mock(packet, output, authorization, client=self.production_client(declined))
        self.recorded += 1
        return runner.record(output / "report.json", runs_path=self.runs,
                             now=f"2026-09-30T00:{self.recorded:02d}:00Z")

    def diagnostic_prepare(self, variant, source_run_id, *, panel="synthetic-dev", route="litellm-31b"):
        self.serial += 1
        directory = self.root / f"diagnostic-{self.serial}"
        directory.mkdir()
        reading.prepare(self.database, directory / "packet.json", variant=variant, panel_id=panel, route_id=route,
                        source_run_id=source_run_id, accepted_commit=SHA, **self.registries)
        return directory / "packet.json"

    def diagnostic_bind(self, packet_path, grant=950):
        self.serial += 1
        slot = self.root / f"diagnostic-run-{self.serial}"
        authorization = packet_path.parent / f"authorization-{self.serial}.json"
        reading.bind_authorization(packet_path, f"{GRANT}{grant}", authorization, slot)
        return authorization, slot

    def reading_client(self, answer):
        """``answer(case, request_json)`` returns an httpx.Response or raises a transport exception."""
        cases = self.inputs

        def respond(request):
            self.diagnostic_sent.append(request)
            body = json.loads(request.content)
            question = next(case for case in cases if case.question in body["messages"][1]["content"])
            return answer(question, body)

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def diagnostic_live(self, packet_path, authorization, slot, client):
        with patch.object(runner, "_admitted_client", return_value=client):
            return await reading.run_live(self.database, slot, packet_path=packet_path,
                                          authorization_path=authorization, accepted_commit=SHA,
                                          env_file=self.root / "unused.env", **self.registries)

    def expected_reading(self, case):
        oracle = self.panel.oracle_for(case)
        if case.expected_branch == "clarify":
            return _reading("clarify", _REASONS[oracle.clarification.kind])
        if case.expected_branch == "decline":
            return _reading("decline", "unsupported_requirement", unsupported="metric", analysis="none")
        return _reading()

    # ----------------------------------------------------------------- packet
    async def test_prepare_pins_the_production_system_message_the_template_and_the_closed_schema(self):
        source = await self.source_run()
        index = runner.load_runs(self.runs)
        for variant in reading.VARIANTS:
            with self.subTest(variant=variant):
                path = self.diagnostic_prepare(variant, source["run_id"])
                packet = json.loads(path.read_text())
                self.assertEqual((packet["version"], packet["variant"], packet["prompt_version"]),
                                 ("reading-diagnostic-v1", variant, "reading-prompt-v1"))
                self.assertEqual((packet["evidence_class"], packet["promotion_eligible"]),
                                 ("diagnostic_observation", False))
                canonical, _ = runner.build_packet(
                    self.database, candidate_id=registry.current()["candidate_id"], panel_id="synthetic-dev",
                    route_id="litellm-31b", accepted_commit=SHA, gateway_policies=dict(runner.ROUTE_POLICY),
                    **self.registries)
                self.assertEqual(packet["canonical_packet"], canonical)
                self.assertEqual(packet["source_run"], {"run_id": source["run_id"],
                                                        "report_sha256": index[-1]["report_sha256"],
                                                        "slot": source["slot"]})
                self.assertEqual((packet["schema_name"], packet["schema"]),
                                 ("grepbit_reading_diagnostic", reading.SCHEMA))
                self.assertEqual(packet["schema_sha256"],
                                 hashlib.sha256(model.canonical_json(reading.SCHEMA).encode()).hexdigest())
                # The reading is asked before the verdict, whether or not a route sorts the schema keys.
                self.assertEqual(list(reading.SCHEMA["properties"]), ["reading", "verdict"])
                self.assertEqual(sorted(reading.SCHEMA["properties"]), ["reading", "verdict"])
                self.assertEqual((packet["max_calls"], packet["call_timeout_seconds"], packet["run_seconds"]),
                                 (len(self.inputs), 60.0, len(self.inputs) * 60.0 + 120))
                self.assertEqual([row["case_id"] for row in packet["inputs"]], [c.case_id for c in self.inputs])
                report = runner._read_archived(runner._location(source["slot"] + "/report.json"))
                for row, case, recorded in zip(packet["inputs"], self.inputs, report["results"]):
                    action = recorded["validated_action"] if variant == "replayed" else None
                    messages = reading.messages(variant, case.question, action)
                    self.assertEqual(row["messages_sha256"],
                                     hashlib.sha256(model.canonical_json(messages).encode()).hexdigest())
                    self.assertEqual(messages[0], recipe_model.messages_for(case.question)[0])
                    user = messages[1]["content"]
                    self.assertIn(case.question, user)
                    self.assertEqual(recorded["validated_action"] in user, variant == "replayed")
                    for leaked in (case.case_id, case.oracle_id, case.semantic_signature):
                        self.assertNotIn(leaked, user)

    def test_the_schema_and_both_templates_are_the_contract_text(self):
        text = (runner.ROOT / "docs/reading-diagnostic.md").read_text()

        def block(heading, fence):
            start = text.index(fence, text.index(heading)) + len(fence)
            return text[start:text.index("\n```", start)]

        self.assertEqual(json.loads(block("### `grepbit_reading_diagnostic`", "```json\n")), reading.SCHEMA)
        question, action = "QUESTION-TEXT", '{"outcome":"declined"}'
        fresh = block("`fresh`:", "```\n").replace("{question}", question)
        replayed = block("`replayed`:", "```\n").replace("{question}", question).replace("{action}", action)
        self.assertEqual(reading.messages("fresh", question, None)[1], {"role": "user", "content": fresh})
        self.assertEqual(reading.messages("replayed", question, action)[1], {"role": "user", "content": replayed})
        for variant, recorded in (("fresh", action), ("replayed", None)):
            with self.subTest(variant=variant), self.assertRaises(p3_assets.P3Error):
                reading.messages(variant, question, recorded)

    async def test_prepare_refuses_by_identity_with_one_closed_reason(self):
        source = await self.source_run()

        def refused(reason, variant="replayed", run_id=source["run_id"], **kwargs):
            with self.assertRaises(reading.DiagnosticRefused) as refusal:
                self.diagnostic_prepare(variant, run_id, **kwargs)
            self.assertEqual((refusal.exception.code, refusal.exception.reason), ("invalid_manifest", reason))

        refused("not_dev_panel", panel="synthetic-regression")
        refused("source_run", run_id="no-such-run")
        refused("source_run", route="litellm-12b")
        with self.assertRaises(p3_assets.P3Error) as invalid:
            self.diagnostic_prepare("counterfactual", source["run_id"])
        self.assertEqual(invalid.exception.code, "invalid_arguments")
        # A replay needs every recorded action; a fresh reading needs none.
        original = runner._read_archived

        def without_one_action(path):
            report = original(path)
            report["results"][3]["validated_action"] = None
            return report

        with patch.object(runner, "_read_archived", side_effect=without_one_action):
            refused("source_actions")
            self.assertEqual(json.loads(self.diagnostic_prepare("fresh", source["run_id"]).read_text())["variant"],
                             "fresh")
        self.assertEqual(reading.REFUSALS, ("not_dev_panel", "source_run", "source_actions", "message_size"))

    # ----------------------------------------------------------------- live
    async def test_live_sends_one_call_per_input_and_keeps_only_the_closed_reading(self):
        source = await self.source_run(declined={self.inputs[0].case_id})
        packet = self.diagnostic_prepare("replayed", source["run_id"])
        authorization, slot = self.diagnostic_bind(packet)
        odd = self.inputs[1]

        def answer(case, body):
            value = _reading("clarify", "orientation_unresolved") if case is odd else self.expected_reading(case)
            return httpx.Response(200, json=envelope(json.dumps(value)))

        result = await self.diagnostic_live(packet, authorization, slot, self.reading_client(answer))
        self.assertEqual(len(self.diagnostic_sent), len(self.inputs))
        for request, case in zip(self.diagnostic_sent, self.inputs):
            body = json.loads(request.content)
            self.assertEqual(body["messages"][0], recipe_model.messages_for(case.question)[0])
            self.assertEqual(body["response_format"]["json_schema"],
                             {"name": "grepbit_reading_diagnostic", "schema": reading.SCHEMA})
            self.assertEqual((body["temperature"], body["max_tokens"], body["stream"]), (0, 2048, False))
        self.assertEqual((result["status"], result["stop_reason"], result["client_http_attempts"],
                          result["possible_in_flight_attempts"]), ("complete", "complete", len(self.inputs), 0))
        self.assertEqual((result["evidence_class"], result["promotion_eligible"]),
                         ("diagnostic_observation", False))
        self.assertEqual(result["owner_authorization_reference"], f"{GRANT}950")
        rows = {row["case_id"]: row for row in result["results"]}
        for case in self.inputs:
            row = rows[case.case_id]
            self.assertEqual(set(row), {"case_id", "family_id", "question_sha256", "state", "attempt",
                                        "http_attempts", "elapsed_seconds", "error_code", "reading"})
            self.assertEqual((row["state"], row["error_code"]), ("returned", None))
            expected = _reading("clarify", "orientation_unresolved") if case is odd else self.expected_reading(case)
            self.assertEqual(row["reading"], expected)
        # Comparisons are derived at readback from the panel, its oracles and the source run; none is sent.
        comparisons = {row["case_id"]: row for row in result["comparisons"]}
        first, clarify = self.inputs[0], next(case for case in self.inputs if case.expected_branch == "clarify")
        self.assertEqual((comparisons[first.case_id]["recorded_action"],
                          comparisons[first.case_id]["decision_matches_expected"],
                          comparisons[first.case_id]["decision_matches_recorded"]), ("decline", True, False))
        self.assertEqual((comparisons[odd.case_id]["expected_branch"],
                          comparisons[odd.case_id]["decision_matches_expected"],
                          comparisons[odd.case_id]["reason_matches_expected_kind"]), ("answer", False, None))
        self.assertEqual((comparisons[clarify.case_id]["expected_kind"],
                          comparisons[clarify.case_id]["recorded_kind"],
                          comparisons[clarify.case_id]["reason_matches_expected_kind"]),
                         ("count_basis", "count_basis", True))
        self.assertEqual(result["reading_summary"]["matches"]["decision_matches_expected"],
                         {"true": len(self.inputs) - 1, "false": 1, "null": 0})
        self.assertEqual(result["reading_summary"]["matches"]["decision_matches_recorded"],
                         {"true": len(self.inputs) - 2, "false": 2, "null": 0})
        self.assertEqual(sum(result["reading_summary"]["fields"]["decision"].values()), len(self.inputs))
        self.assertEqual(reading.read_report(slot / "report.json", **self.registries), result)

    async def test_model_content_errors_continue_and_route_failures_stop(self):
        source = await self.source_run()
        packet = self.diagnostic_prepare("fresh", source["run_id"])
        broken, off_enum, page = self.inputs[1], self.inputs[2], self.inputs[3]

        def answer(case, body):
            if case is broken:
                return httpx.Response(200, json=envelope("{not json"))
            if case is off_enum:
                value = _reading()
                value["reading"]["count_request"] = "headcount"
                return httpx.Response(200, json=envelope(json.dumps(value)))
            if case is page:
                return httpx.Response(200, text="<html>gateway error</html>", headers={"content-type": "text/html"})
            return httpx.Response(200, json=envelope(json.dumps(self.expected_reading(case))))

        authorization, slot = self.diagnostic_bind(packet)
        result = await self.diagnostic_live(packet, authorization, slot, self.reading_client(answer))
        states = [(row["state"], row["error_code"], row["reading"]) for row in result["results"]]
        self.assertEqual(states[1], ("failed", "invalid_json", None))
        self.assertEqual(states[2], ("failed", "invalid_reading", None))
        self.assertEqual(states[3][:2], ("failed", "unsupported_output"))
        self.assertEqual({state for state, _, _ in states[4:]}, {"not_started"})
        self.assertEqual((result["status"], result["stop_reason"], result["client_http_attempts"]),
                         ("incomplete", "anomaly", 4))

        def slow(case, body):
            raise httpx.ReadTimeout("synthetic timeout")

        authorization, slot = self.diagnostic_bind(self.diagnostic_prepare("fresh", source["run_id"]))
        result = await self.diagnostic_live(authorization.parent / "packet.json", authorization, slot,
                                            self.reading_client(slow))
        self.assertEqual((result["stop_reason"], [row["error_code"] for row in result["results"][:2]],
                          result["results"][2]["state"]), ("timeout_streak", ["timeout", "timeout"], "not_started"))

    async def test_live_refuses_a_mismatched_envelope_or_a_changed_source_before_any_send(self):
        source = await self.source_run()
        packet = self.diagnostic_prepare("replayed", source["run_id"])
        other = self.diagnostic_prepare("fresh", source["run_id"])
        authorization, slot = self.diagnostic_bind(packet)
        never = self.reading_client(lambda case, body: self.fail("sent"))
        with self.assertRaises(p3_assets.P3Error):
            await self.diagnostic_live(other, authorization, slot, never)
        with self.assertRaises(p3_assets.P3Error):
            await self.diagnostic_live(packet, authorization, self.root / "diagnostic-run-elsewhere", never)
        with self.assertRaises(p3_assets.P3Error):
            reading.bind_authorization(packet, "not-a-grant", packet.parent / "authorization-x.json", slot)
        # Any index change after preparation changes the canonical packet: drift, before any send.
        await self.source_run(grant=902)
        with self.assertRaises(p3_assets.P3Error) as drift:
            await self.diagnostic_live(packet, authorization, slot, never)
        self.assertEqual(drift.exception.code, "manifest_drift")
        self.assertEqual(self.diagnostic_sent, [])

    async def test_readback_rejects_free_text_and_tampering(self):
        source = await self.source_run()
        packet = self.diagnostic_prepare("fresh", source["run_id"])
        authorization, slot = self.diagnostic_bind(packet)
        await self.diagnostic_live(packet, authorization, slot, self.reading_client(
            lambda case, body: httpx.Response(200, json=envelope(json.dumps(self.expected_reading(case))))))
        path = slot / "report.json"
        original = json.loads(path.read_text())
        tampered = []
        free_text = json.loads(json.dumps(original))
        free_text["results"][0]["reading"]["verdict"]["note"] = "because"
        tampered.append(free_text)
        off_enum = json.loads(json.dumps(original))
        off_enum["results"][0]["reading"]["reading"]["orientation"] = "maybe"
        tampered.append(off_enum)
        raw = json.loads(json.dumps(original))
        raw["results"][0]["completion_text"] = "{}"
        tampered.append(raw)
        miscounted = json.loads(json.dumps(original))
        miscounted["client_http_attempts"] += 1
        tampered.append(miscounted)
        for number, value in enumerate(tampered):
            with self.subTest(case=number):
                copy = self.root / f"tampered-{number}" / "report.json"
                copy.parent.mkdir()
                copy.write_text(json.dumps(value))
                with self.assertRaises(p3_assets.P3Error):
                    reading.read_report(copy, **self.registries)

    # ----------------------------------------------------------------- CLI
    async def test_cli_dispatches_through_the_runner_and_its_arguments_are_closed(self):
        source = await self.source_run()
        directory = self.root / "cli"
        directory.mkdir()
        argv = ["--reading-diagnostic", "--prepare", "--variant", "fresh", "--panel", "synthetic-dev",
                "--route", "litellm-31b", "--source-run", source["run_id"], "--db", str(self.database),
                "--accepted-commit", SHA, "--output", str(directory / "packet.json")]
        stdout = io.StringIO()
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                patch.object(runner, "ROUTES", self.routes), redirect_stdout(stdout):
            self.assertEqual(runner.main(argv), 0)
        self.assertEqual(json.loads(stdout.getvalue())["state"], "prepared_not_authorized")
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                patch.object(runner, "ROUTES", self.routes), patch("sys.stdout"), patch("sys.stderr"):
            for bad in (argv[:-2], argv + ["--candidate", self.candidate],
                        [a if a != "--variant" else "--mode" for a in argv],
                        ["--reading-diagnostic", "--report"],
                        ["--reading-diagnostic", "--gate", "--panels", "synthetic-dev"]):
                with self.subTest(argv=bad):
                    self.assertEqual(runner.main(bad), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
