"""Count ablation rulers (count-ablation-v1, #152): synthetic panels and mock transports only; no live call."""
import hashlib
import io
import json
from contextlib import redirect_stderr
import unittest
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import count_ablation as ablation, evaluate as runner, p3_assets
from test_evaluate import BASE, GRANT, KEY, SHA, EvaluateHarness, envelope

_SYNTHETIC = {"synthetic-dev": ("E01_overview", "C01_count_basis")}


def _overview(count_request):
    return {"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
            "request": {"center_code": "CTR-A01", "start": "2026-03-01T00:00:00+08:00",
                        "end": "2026-04-01T00:00:00+08:00", "timezone": "Asia/Taipei"},
            "count_request": count_request}


class VariantTests(unittest.TestCase):
    """Pure checks against the production instruction, context and schema; no run."""

    def test_each_edit_applies_exactly_once_to_the_current_candidate_and_nothing_else_changes(self):
        base = recipe_model.SYSTEM_INSTRUCTION
        for variant, edits in (("labels", ablation.LABEL_EDITS), ("rules", ablation.RULE_EDITS)):
            text, undone = ablation.variant_instruction(variant), ablation.variant_instruction(variant)
            for old, new in edits:
                self.assertEqual((base.count(old), text.count(new)), (1, 1))
                undone = undone.replace(new, old, 1)
            self.assertEqual(undone, base)
        labels = ablation.variant_instruction("labels")
        # Compare's orientation keeps its production label; no quoted production count label is left.
        self.assertEqual(labels.count('orientation:"unresolved"'), base.count('orientation:"unresolved"'))
        self.assertNotIn('count_request "unresolved"', labels)
        self.assertNotIn('"none"', labels)
        production, renamed = recipe_model.output_schema(), ablation.variant_schema("labels")
        self.assertEqual(ablation.variant_schema("rules"), production)
        self.assertEqual(model.canonical_json(renamed), model.canonical_json(production).replace(
            '"enum":["none","booked_seats","unresolved"',
            '"enum":["no_people_count","booked_seats","generic_people_count"', 1))
        self.assertNotEqual(renamed, production)
        context = recipe_model.runtime_context()
        labelled, ruled = ablation.variant_context("labels"), ablation.variant_context("rules")
        self.assertEqual(labelled, {**context, "output_schema": renamed})
        old, new = ablation.COUNT_BASIS_EDIT
        self.assertEqual(context["clarification"]["count_basis"].count(old), 1)
        self.assertEqual(ruled, {**context, "clarification": {
            **context["clarification"], "count_basis": context["clarification"]["count_basis"].replace(old, new, 1)}})
        wire = ablation.messages("rules", "q")
        self.assertEqual(wire, [{"role": "system", "content": ablation.variant_instruction("rules") + "\n"
                                 + model.canonical_json(ruled)}, {"role": "user", "content": "q"}])
        self.assertEqual(ablation.VARIANTS, ("labels", "rules"))
        self.assertEqual(ablation.REFUSALS, ("not_dev_panel", "route", "selection", "variant_text"))

    def test_undoing_each_variant_gives_the_production_system_message(self):
        production = recipe_model.messages_for("q")
        for variant, edits in (("labels", ablation.LABEL_EDITS),
                               ("rules", ablation.RULE_EDITS + (ablation.COUNT_BASIS_EDIT,))):
            wire = ablation.messages(variant, "q")
            content = wire[0]["content"]
            for old, new in edits:
                self.assertEqual(content.count(new), 1)
                content = content.replace(new, old, 1)
            if variant == "labels":
                renamed = '"enum":["no_people_count","booked_seats","generic_people_count"'
                self.assertEqual(content.count(renamed), 1)
                content = content.replace(renamed, '"enum":["none","booked_seats","unresolved"', 1)
            self.assertEqual([{"role": "system", "content": content}, wire[1]], production)

    def test_map_back_never_repairs_a_reply_production_rejects_and_never_raises(self):
        request = ('{"center_code":"CTR-A01","start":"2026-03-01T00:00:00+08:00",'
                   '"end":"2026-04-01T00:00:00+08:00","timezone":"Asia/Taipei"}')
        rejected = (
            '{"outcome":"request","recipe_id":"overview","recipe_version":"0.1","request":' + request
            + ',"count_request":"none","count_request":"generic_people_count"}',
            '{"outcome":"declined","outcome":"request","recipe_id":"overview","recipe_version":"0.1","request":'
            + request + ',"count_request":"generic_people_count"}',
            '{"outcome":"request","recipe_id":"overview","recipe_version":"0.1","request":{"center_code":"\\ud800"},'
            '"count_request":"generic_people_count"}',
            "[" * 100000 + "]" * 100000)
        for content in rejected:
            body = json.dumps(envelope(content)).encode()
            self.assertEqual(ablation.map_back("labels", body), body)
        duplicated = (b'{"model":"m","model":"m","choices":[{"index":0,"message":{"role":"assistant","content":'
                      + json.dumps(json.dumps(_overview("generic_people_count"))).encode() + b'}}]}')
        self.assertEqual(ablation.map_back("labels", duplicated), duplicated)

    def test_a_changed_base_text_is_refused_rather_than_edited_differently(self):
        doubled = recipe_model.SYSTEM_INSTRUCTION + " " + ablation.RULE_EDITS[0][0]
        missing = recipe_model.SYSTEM_INSTRUCTION.replace(ablation.LABEL_EDITS[2][0], "so it is zero")
        for text, variant in ((doubled, "rules"), (missing, "labels")):
            with patch.object(recipe_model, "SYSTEM_INSTRUCTION", text), \
                    self.assertRaises(ablation.ExperimentRefused) as refusal:
                ablation.variant_instruction(variant)
            self.assertEqual(refusal.exception.reason, "variant_text")
        with self.assertRaises(p3_assets.P3Error):
            ablation.variant_instruction("prose")

    def test_the_pre_registered_selection_is_21_inputs_on_the_real_dev_panels(self):
        registered = {row["panel_id"]: row for row in runner.load_panels()["panels"]}
        total = 0
        for panel_id, families in ablation.SELECTION.items():
            entry = registered[panel_id]
            self.assertEqual(entry["tier"], "dev")
            cases = [case for case in p3_assets.load_panel(runner.ROOT / entry["path"]).cases
                     if case.family_id in families]
            self.assertEqual({case.family_id for case in cases}, set(families))
            total += len(cases)
        self.assertEqual((total, total * len(ablation.VARIANTS)), (21, 42))

    def test_map_back_renames_only_an_overview_count_request_label(self):
        def body(content):
            return json.dumps(envelope(content)).encode()

        def content(raw):
            return json.loads(json.loads(raw)["choices"][0]["message"]["content"])

        for label, production in (("generic_people_count", "unresolved"), ("no_people_count", "none")):
            mapped = ablation.map_back("labels", body(json.dumps(_overview(label))))
            self.assertEqual(content(mapped), _overview(production))
        for unchanged in (body(json.dumps(_overview("booked_seats"))), body(json.dumps(_overview("none"))),
                          body('{"outcome":"declined"}'), body("{not json"), b"<html>"):
            self.assertEqual(ablation.map_back("labels", unchanged), unchanged)
        labelled = body(json.dumps(_overview("generic_people_count")))
        self.assertEqual(ablation.map_back("rules", labelled), labelled)
        # Only an Overview request's count_request is a label: other actions and non-object content pass through.
        for unchanged in (body(json.dumps({**_overview("generic_people_count"), "recipe_id": "compare"})),
                          body(json.dumps({**_overview("generic_people_count"), "outcome": "clarify"})),
                          body('["generic_people_count"]'), body('"generic_people_count"')):
            self.assertEqual(ablation.map_back("labels", unchanged), unchanged)


class AblationRunTests(EvaluateHarness):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(ablation, "SELECTION", _SYNTHETIC))
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        self.selected = [case for case in self.panel.cases if case.family_id in _SYNTHETIC["synthetic-dev"]]
        self.recorded, self.experiment_sent = 0, []

    def scripted(self, *, page=(), failing=(), sink=None):
        cases = self.panel.cases

        def respond(request):
            if sink is not None:
                sink.append(request)
            payload = json.loads(request.content)
            question = payload["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            if case.case_id in failing:
                raise httpx.ConnectError("synthetic transport failure", request=request)
            if case.case_id in page:
                return httpx.Response(200, text="<html>gateway error</html>", headers={"content-type": "text/html"})
            action = dict(self.by_oracle[case.oracle_id])
            # Under the labels variant the model can only answer with the renamed labels.
            if "generic_people_count" in payload["messages"][0]["content"] and action.get("count_request"):
                action["count_request"] = ablation.LABELS.get(action["count_request"], action["count_request"])
            return httpx.Response(200, json=envelope(json.dumps(action)))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def baseline(self, grant):
        self.recorded += 1
        packet = self.prepare(repetition=self.recorded)
        output = self.output()
        authorization = self.root / f"authorization-{output.name}.json"
        runner.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
        await self.run_mock(packet, output, authorization, client=self.litellm_client(scripted=True,
                                                                                      cases=self.panel.cases))
        return runner.record(output / "report.json", runs_path=self.runs, now=f"2026-10-01T01:{self.recorded:02d}:00Z")

    def experiment_prepare(self, *, panel="synthetic-dev", route="litellm-31b"):
        self.serial += 1
        directory = self.root / f"ablation-{self.serial}"
        directory.mkdir()
        ablation.prepare(self.database, directory / "packet.json", panel_id=panel, route_id=route,
                         accepted_commit=SHA, **self.registries)
        return directory / "packet.json"

    async def experiment(self, grant, **answers):
        packet = self.experiment_prepare()
        self.serial += 1
        slot = self.root / f"ablation-run-{self.serial}"
        authorization = packet.parent / "authorization.json"
        ablation.bind_authorization(packet, f"{GRANT}{grant}", authorization, slot)
        with patch.object(runner, "_admitted_client", return_value=self.scripted(sink=self.experiment_sent,
                                                                                 **answers)):
            return await ablation.run_live(self.database, slot, packet_path=packet, authorization_path=authorization,
                                           accepted_commit=SHA, env_file=self.root / "unused.env",
                                           **self.registries), slot

    # ----------------------------------------------------------------- packet
    async def test_prepare_pins_the_variants_the_selection_and_each_message(self):
        packet = json.loads(self.experiment_prepare().read_text())
        self.assertEqual((packet["version"], packet["evidence_class"], packet["promotion_eligible"]),
                         ("count-ablation-v1", "diagnostic_observation", False))
        canonical, _ = runner.build_packet(
            self.database, candidate_id=self.candidate, panel_id="synthetic-dev", route_id="litellm-31b",
            accepted_commit=SHA, gateway_policies=dict(runner.ROUTE_POLICY), **self.registries)
        self.assertEqual(packet["canonical_packet"], canonical)
        expected = [(case.case_id, variant) for case in self.selected for variant in ablation.VARIANTS]
        self.assertEqual([(row["case_id"], row["variant"]) for row in packet["inputs"]], expected)
        cases = {case.case_id: case for case in self.selected}
        for row in packet["inputs"]:
            self.assertEqual(row["messages_sha256"],
                             ablation._sha(ablation.messages(row["variant"], cases[row["case_id"]].question)))
        self.assertEqual(packet["variants"], {variant: ablation._variant_pins(variant) for variant in ablation.VARIANTS})
        self.assertEqual((packet["max_calls"], packet["run_seconds"]), (len(expected), len(expected) * 60.0 + 120))

    async def test_prepare_refuses_with_one_closed_reason(self):
        def refused(reason, **kwargs):
            with self.assertRaises(ablation.ExperimentRefused) as refusal:
                self.experiment_prepare(**kwargs)
            self.assertEqual((refusal.exception.code, refusal.exception.reason), ("invalid_manifest", reason))

        refused("not_dev_panel", panel="synthetic-regression")
        refused("route", route="bedrock-sonnet")
        refused("route", route="litellm-12b")
        with patch.object(ablation, "SELECTION", {}):
            refused("selection")
        with patch.object(ablation, "SELECTION", {"synthetic-dev": ("E01_overview", "dev-NOPE")}):
            refused("selection")
        with patch.object(recipe_model, "SYSTEM_INSTRUCTION", recipe_model.SYSTEM_INSTRUCTION + " "
                          + ablation.RULE_EDITS[0][0]):
            refused("variant_text")

    # ----------------------------------------------------------------- live and comparison
    async def test_live_sends_each_variant_once_and_grades_through_the_production_pipeline(self):
        # Without a recorded run of the current candidate, the report reads back but is not compared.
        result, _ = await self.experiment(940)
        self.assertEqual((result["status"], result["comparison"]["refusal"]), ("complete", "no_baseline"))
        self.experiment_sent.clear()
        baseline = await self.baseline(941)
        result, slot = await self.experiment(942)
        packet = json.loads((slot / "packet.json").read_text())
        self.assertEqual(len(self.experiment_sent), len(packet["inputs"]))
        cases = {case.case_id: case for case in self.selected}
        for request, item in zip(self.experiment_sent, packet["inputs"]):
            body = json.loads(request.content)
            self.assertEqual(body["messages"], ablation.messages(item["variant"], cases[item["case_id"]].question))
            self.assertEqual(body["response_format"]["json_schema"],
                             {"name": recipe_model.STRUCTURED_OUTPUT_SCHEMA_NAME,
                              "schema": ablation.variant_schema(item["variant"])})
        self.assertEqual((result["status"], result["stop_reason"], result["client_http_attempts"]),
                         ("complete", "complete", len(packet["inputs"])))
        for row in result["results"]:
            case = cases[row["case_id"]]
            expected = self.by_oracle[case.oracle_id]
            self.assertEqual(row["state"], "returned")
            self.assertIn(row["graded"]["outcome"], ("complete_correct", "correct_clarification"))
            # The labels reply was mapped back, so the persisted action is the production action.
            self.assertEqual(model.strict_json(row["validated_action"]).get("count_request"),
                             expected.get("count_request"))
            self.assertEqual(row["reading"]["outcome"], expected["outcome"])
            self.assertIsNone(row["annex"])
        self.assertEqual(result["summary"]["by_variant"]["labels"]["returned"], len(self.selected))
        comparison = result["comparison"]
        self.assertEqual((comparison["baseline_runs"], comparison["refusal"]), ([baseline["run_id"]], None))
        self.assertTrue(all(item["variant_verdict"] == "correct" and item["baseline_correct"] == 1
                            for item in comparison["inputs"]))
        self.assertEqual(ablation.read_report(slot / "report.json", **self.registries), result)

    async def test_route_failures_stop_unassessed_and_tampering_is_rejected(self):
        await self.baseline(950)
        first = self.selected[0].case_id
        result, slot = await self.experiment(951, page={first})
        self.assertEqual((result["status"], result["stop_reason"]), ("incomplete", "anomaly"))
        self.assertEqual((result["results"][0]["state"], result["results"][0]["error_code"]),
                         ("failed", "unsupported_output"))
        self.assertEqual({row["state"] for row in result["results"][1:]}, {"not_started"})
        result, slot = await self.experiment(952)
        report_path = slot / "report.json"
        original = report_path.read_text()
        # results[0] is a labels row and results[1] its rules row; a rules row can never have been mapped.
        for position, key, value in ((0, "annex", "correct"),
                                     (0, "reading", {"outcome": "declined", "count_request": None,
                                                     "clarification_kind": None, "choices": None}),
                                     (1, "mapped", True), (0, "mapped", None), (0, "mapped", "yes")):
            tampered = json.loads(original)
            self.assertEqual(tampered["results"][1]["variant"], "rules")
            tampered["results"][position][key] = value
            report_path.write_text(json.dumps(tampered))
            with self.subTest(key=key, value=value), self.assertRaises(p3_assets.P3Error) as refusal:
                ablation.read_report(report_path, **self.registries)
            self.assertEqual(refusal.exception.code, "invalid_asset")
        report_path.write_text(original)
        packet = json.loads((slot / "packet.json").read_text())
        packet["variants"]["rules"]["edits"] = []
        with self.assertRaises(p3_assets.P3Error):
            ablation._packet_contract(packet)
        fresh = self.experiment_prepare()
        authorization = fresh.parent / "authorization.json"
        target = self.root / "ablation-drift"
        ablation.bind_authorization(fresh, f"{GRANT}953", authorization, target)
        with self.assertRaises(p3_assets.P3Error):
            await ablation.run_live(self.database, target, packet_path=fresh, authorization_path=authorization,
                                    accepted_commit="2" * 40, env_file=self.root / "unused.env", **self.registries)

    async def test_the_packet_contract_enforces_the_pre_registered_selection(self):
        packet = json.loads(self.experiment_prepare().read_text())
        self.assertEqual(ablation._packet_contract(json.loads(json.dumps(packet)))["inputs"], packet["inputs"])
        other = next(item for item in packet["canonical_packet"]["inputs"]
                     if item["family_id"] not in _SYNTHETIC["synthetic-dev"])

        def resized(rows):
            changed = json.loads(json.dumps(packet))
            changed.update(inputs=rows, max_calls=len(rows), run_seconds=len(rows) * changed["call_timeout_seconds"] + 120)
            return changed

        relabelled = {**packet["inputs"][0], "case_id": other["case_id"], "question_sha256": other["question_sha256"]}
        for rows in (packet["inputs"][1:], packet["inputs"][:2], [relabelled] + packet["inputs"][1:],
                     [{**packet["inputs"][0], "question_sha256": "0" * 64}] + packet["inputs"][1:]):
            with self.assertRaises(p3_assets.P3Error):
                ablation._packet_contract(resized(rows))

    async def test_an_annex_panel_runs_end_to_end_with_mapped_labels(self):
        overview = next(case for case in self.selected if case.family_id == "E01_overview")
        annex = self.root / "annex.json"
        annex.write_text(json.dumps({"version": "count-assumption-annex-v1",
                                     "expectations": {overview.oracle_id: {"count_basis": "booked_seats"}}}))
        registry = json.loads(self.panels.read_text())
        registry["panels"][0]["annex"] = {"path": f"{self.relative}/annex.json",
                                          "sha256": hashlib.sha256(annex.read_bytes()).hexdigest()}
        self.panels.write_text(json.dumps(registry))
        # evaluate.record re-reads a report's annex through the default registry, so point it at the synthetic one.
        self.enterContext(patch.object(runner, "PANELS", self.panels))
        # The scripted model reads the Overview as a generic count, so it states the annexed assumption.
        self.by_oracle[overview.oracle_id] = {**self.by_oracle[overview.oracle_id], "count_request": "unresolved"}
        baseline = await self.baseline(960)
        result, slot = await self.experiment(961)
        self.assertEqual(result["status"], "complete")
        rows = {(row["case_id"], row["variant"]): row for row in result["results"]}
        for variant in ablation.VARIANTS:
            row = rows[(overview.case_id, variant)]
            # The labels schema has no "unresolved": the persisted production value can only come from map_back.
            self.assertEqual((row["reading"]["count_request"], row["annex"]), ("unresolved", "correct"))
            self.assertIs(row["mapped"], variant == "labels")
        self.assertNotIn("unresolved", json.dumps(ablation.variant_schema("labels")["oneOf"][0]))
        comparison = result["comparison"]
        self.assertEqual((comparison["baseline_runs"], comparison["refusal"]), ([baseline["run_id"]], None))
        self.assertTrue(all(item["variant_verdict"] == "correct" for item in comparison["inputs"]))
        self.assertEqual(ablation.read_report(slot / "report.json", **self.registries), result)

    async def test_two_network_failures_in_a_row_stop_the_run(self):
        first = self.selected[0].case_id
        result, _ = await self.experiment(965, failing={first})
        states = [(row["state"], row["error_code"]) for row in result["results"]]
        self.assertEqual(states[:2], [("failed", "transport_error")] * 2)
        self.assertEqual({state for state, _ in states[2:]}, {"not_started"})
        self.assertEqual((result["status"], result["stop_reason"]), ("incomplete", "network_streak"))

    async def test_live_refuses_a_drifted_packet_before_any_send_or_slot(self):
        packet_path = self.experiment_prepare()
        packet = json.loads(packet_path.read_text())
        packet["inputs"][0]["messages_sha256"] = "0" * 64
        drifted = packet_path.parent / "drifted" / "packet.json"
        drifted.parent.mkdir()
        drifted.write_text(json.dumps(packet))
        authorization = drifted.parent / "authorization.json"
        slot = self.root / "ablation-drifted-run"
        ablation.bind_authorization(drifted, f"{GRANT}966", authorization, slot)
        with patch.object(runner, "_admitted_client", return_value=self.scripted(sink=self.experiment_sent)), \
                self.assertRaises(p3_assets.P3Error):
            await ablation.run_live(self.database, slot, packet_path=drifted, authorization_path=authorization,
                                    accepted_commit=SHA, env_file=self.root / "unused.env", **self.registries)
        self.assertEqual((self.experiment_sent, slot.exists()), ([], False))

    async def test_the_comparison_applies_the_gates_integrity_checks(self):
        await self.baseline(970)
        _, slot = await self.experiment(971)
        original = runner._gate_view
        with patch.object(runner, "_gate_view", side_effect=lambda report: ("0" * 64, original(report)[1])):
            refused = ablation.read_report(slot / "report.json", **self.registries)["comparison"]
        self.assertEqual((refused["refusal"], refused["inputs"]), ("candidate_identity", []))
        self.assertEqual(ablation.COMPARISON_REFUSALS, ("no_baseline", "baseline_unavailable", "candidate_identity",
                                                        "inputs_differ", "index_mismatch"))

    async def test_readback_ties_the_selection_and_messages_to_the_registered_panel(self):
        _, slot = await self.experiment(980)
        packet = json.loads((slot / "packet.json").read_text())
        ablation._registered(packet, self.panel)
        relabelled = json.loads(json.dumps(packet))
        relabelled["canonical_packet"]["inputs"][0]["family_id"] = "E02_compare"
        renamed = json.loads(json.dumps(packet))
        renamed["inputs"][0]["messages_sha256"] = "0" * 64
        for changed in (relabelled, renamed):
            with self.assertRaises(p3_assets.P3Error) as refusal:
                ablation._registered(changed, self.panel)
            self.assertEqual(refusal.exception.code, "manifest_drift")
        # The readback runs the check: different variant messages are drift, not a silent pass.
        with patch.object(ablation, "messages", side_effect=lambda variant, question: [{"role": "user", "content": ""}]), \
                self.assertRaises(p3_assets.P3Error) as refusal:
            ablation.read_report(slot / "report.json", **self.registries)
        self.assertEqual(refusal.exception.code, "manifest_drift")

    async def test_each_comparison_refusal_fires_on_its_own_condition(self):
        baseline = await self.baseline(985)
        _, slot = await self.experiment(986)
        original_view, original_reports = runner._gate_view, runner._archived_reports
        with patch.object(runner, "_gate_view", side_effect=lambda report: (original_view(report)[0], ("other",))):
            self.assertEqual(ablation.read_report(slot / "report.json", **self.registries)["comparison"]["refusal"],
                             "inputs_differ")

        def regranted(selected):
            return [{**report, "owner_authorization_reference": f"{GRANT}1"} for report in original_reports(selected)]

        with patch.object(runner, "_archived_reports", side_effect=regranted):
            self.assertEqual(ablation.read_report(slot / "report.json", **self.registries)["comparison"]["refusal"],
                             "index_mismatch")
        # Re-read in a checkout without the baseline archive (a clean clone): refused, not failed.
        archive = runner._location(baseline["slot"] + "/report.json")
        archive.rename(archive.with_name("moved.json"))
        comparison = ablation.read_report(slot / "report.json", **self.registries)["comparison"]
        self.assertEqual((comparison["refusal"], comparison["inputs"]), ("baseline_unavailable", []))
        self.assertIn("baseline_unavailable", ablation.COMPARISON_REFUSALS)

    async def test_the_annex_verdict_follows_evaluate_annexed_on_the_persisted_action(self):
        case = self.selected[0]
        graded = {"outcome": "complete_correct"}
        stated = model.canonical_json(_overview("unresolved"))
        silent = model.canonical_json(_overview("none"))
        expectations = {case.oracle_id: {"count_basis": "booked_seats"}}
        self.assertEqual(ablation._annex_verdict(stated, graded, case, expectations), "correct")
        self.assertEqual(ablation._annex_verdict(silent, graded, case, expectations), "wrong")
        self.assertEqual(ablation._annex_verdict(stated, graded, case, {}), "wrong")
        self.assertEqual(ablation._annex_verdict(silent, graded, case, {}), "correct")
        self.assertIsNone(ablation._annex_verdict(silent, graded, case, None))
        # An operational failure is no model result: unassessed, never wrong (the candidate gate's rule).
        failed = {"outcome": "operational_failure", "operational_error": "kernel_failure"}
        self.assertEqual(ablation._annex_verdict(None, failed, case, expectations), "unassessed")
        self.assertTrue(ablation._unassessed(failed))
        self.assertFalse(ablation._unassessed({"outcome": "invalid_output", "operational_error": "invalid_json"}))
        self.assertEqual(ablation._reading(stated), {"outcome": "request", "count_request": "unresolved",
                                                     "clarification_kind": None, "choices": None})

    async def test_cli_arguments_are_closed(self):
        with redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(ablation.main(["--report"]), 2)
            self.assertEqual(ablation.main(["--prepare", "--panel", "x"]), 2)
        self.assertIn('"error_code":"invalid_arguments"', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
