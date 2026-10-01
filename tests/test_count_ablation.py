"""Count ablation rulers (count-ablation-v1, #152): synthetic panels and mock transports only; no live call."""
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


class AblationRunTests(EvaluateHarness):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(ablation, "SELECTION", _SYNTHETIC))
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        self.selected = [case for case in self.panel.cases if case.family_id in _SYNTHETIC["synthetic-dev"]]
        self.recorded, self.experiment_sent = 0, []

    def scripted(self, *, page=(), sink=None):
        cases = self.panel.cases

        def respond(request):
            if sink is not None:
                sink.append(request)
            payload = json.loads(request.content)
            question = payload["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
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
        for key, value in (("annex", "correct"), ("reading", {"outcome": "declined", "count_request": None,
                                                              "clarification_kind": None, "choices": None})):
            tampered = json.loads(original)
            tampered["results"][0][key] = value
            report_path.write_text(json.dumps(tampered))
            with self.assertRaises(p3_assets.P3Error):
                ablation.read_report(report_path, **self.registries)
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
        self.assertEqual(ablation._reading(stated), {"outcome": "request", "count_request": "unresolved",
                                                     "clarification_kind": None, "choices": None})

    async def test_cli_arguments_are_closed(self):
        with redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(ablation.main(["--report"]), 2)
            self.assertEqual(ablation.main(["--prepare", "--panel", "x"]), 2)
        self.assertIn('"error_code":"invalid_arguments"', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
