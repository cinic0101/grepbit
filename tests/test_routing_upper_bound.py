"""Routing upper-bound rulers (routing-upper-bound-v1, #79): synthetic panels and mock transports only; no live call."""
import asyncio
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx

from grepbit import model, recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import evaluate as runner, p3_assets
from tools import routing_upper_bound as routing
from test_evaluate import BASE, GRANT, KEY, SHA, EvaluateHarness, envelope

_SYNTHETIC_TABLE = {"synthetic-dev": {
    "E01_overview": "overview", "E02_compare": "compare", "E03_share_denominator": "breakdown",
    "C01_count_basis": "overview", "C02_comparison_roles": "compare", "C03_center": "overview",
    "C04_metric_meaning": "overview", "D01_profit": "overview", "D02_cash_received": "overview"}}


def _canonical(value):
    return model.canonical_json(value)


class RouterAndContextTests(EvaluateHarness):
    """Pure checks against the real dev panels and the production context; no run."""

    def test_the_router_table_covers_each_real_dev_panel_and_agrees_with_its_oracles(self):
        registered = runner.load_panels()
        self.assertEqual(set(routing.ROUTER_TABLE), {"p3-dev-bound-meaning-v1", "p3-dev-mechanism-probe-v1"})
        for panel_id, table in routing.ROUTER_TABLE.items():
            entry = runner._entry(registered, "panels", panel_id, "panel_id")
            panel = p3_assets.load_panel(runner._location(entry["path"]))
            self.assertEqual(set(table), {case.family_id for case in panel.cases})
            for case in panel.cases:
                with self.subTest(case=case.case_id):
                    derived = routing.derived_scenario(case, panel.oracle_for(case))
                    if case.expected_branch == "decline":
                        self.assertIsNone(derived)
                    else:
                        self.assertEqual(derived, table[case.family_id])
        self.assertEqual(routing.ROUTER_TABLE["p3-dev-bound-meaning-v1"]["dev-BM8"], "overview")

    def test_each_narrowed_context_is_the_production_context_filtered_to_one_analysis_type(self):
        production = recipe_model.runtime_context()
        branches = {_canonical(branch) for branch in production["output_schema"]["oneOf"]}
        kinds = {"overview": {"count_basis", "center", "metric_meaning"}, "compare": {"comparison_roles"},
                 "breakdown": set()}
        for scenario in routing.SCENARIOS:
            with self.subTest(scenario=scenario):
                narrowed = routing.narrowed_context(scenario)
                self.assertEqual(set(narrowed), set(production))
                for key in set(production) - {"recipes", "clarification", "output_schema"}:
                    self.assertEqual(narrowed[key], production[key])
                self.assertEqual(narrowed["recipes"], [r for r in production["recipes"] if r["id"] == scenario])
                self.assertEqual(narrowed["clarification"], {k: v for k, v in production["clarification"].items()
                                                             if k in kinds[scenario] | {"boundary"}})
                schema = narrowed["output_schema"]
                self.assertEqual(schema, routing.narrowed_schema(scenario))
                recipes = [b["properties"]["recipe_id"]["const"] for b in schema["oneOf"]
                           if b["properties"]["outcome"]["const"] == "request"]
                self.assertEqual(recipes, [scenario])
                self.assertIn({"type": "object", "additionalProperties": False, "required": ["outcome"],
                               "properties": {"outcome": {"const": "declined"}}}, schema["oneOf"])
                clarify = [b for b in schema["oneOf"] if b["properties"]["outcome"]["const"] == "clarify"]
                found = {k["properties"]["kind"]["const"]
                         for b in clarify for k in b["properties"]["clarification"]["oneOf"]}
                self.assertEqual(found, kinds[scenario])
                self.assertEqual(len(clarify), 0 if not kinds[scenario] else 1)
                # Every kept branch is a production branch, or the production clarify branch with fewer kinds.
                production_kinds = {_canonical(k) for b in production["output_schema"]["oneOf"]
                                    if b["properties"]["outcome"]["const"] == "clarify"
                                    for k in b["properties"]["clarification"]["oneOf"]}
                for branch in schema["oneOf"]:
                    if branch["properties"]["outcome"]["const"] == "clarify":
                        self.assertTrue({_canonical(k) for k in branch["properties"]["clarification"]["oneOf"]}
                                        <= production_kinds)
                    else:
                        self.assertIn(_canonical(branch), branches)
                self.assertEqual(routing.messages(scenario, "Q?"),
                                 [{"role": "system",
                                   "content": recipe_model.SYSTEM_INSTRUCTION + "\n" + _canonical(narrowed)},
                                  {"role": "user", "content": "Q?"}])
                self.assertEqual(routing.schema_name(scenario), f"grepbit_recipe_request_{scenario}")


class RoutingExperimentTests(EvaluateHarness):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(routing, "ROUTER_TABLE", _SYNTHETIC_TABLE))
        self.panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        self.inputs = self.panel.cases
        self.recorded = 0
        self.experiment_sent = []

    # ----------------------------------------------------------------- helpers
    def scripted(self, *, declined=(), broken=(), page=(), cancel=(), sink=None, base=BASE):
        cases = self.inputs

        def respond(request):
            if sink is not None:
                sink.append(request)
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            if case.case_id in cancel:
                raise asyncio.CancelledError()
            if case.case_id in page:
                return httpx.Response(200, text="<html>gateway error</html>", headers={"content-type": "text/html"})
            content = ("{not json" if case.case_id in broken else json.dumps({"outcome": "declined"})
                       if case.case_id in declined else json.dumps(self.by_oracle[case.oracle_id]))
            return httpx.Response(200, json=envelope(content))

        return GatewayClient(GatewayConfig(base, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def baseline(self, grant, *, declined=()):
        self.recorded += 1
        packet = self.prepare(repetition=self.recorded)
        output = self.output()
        authorization = self.root / f"authorization-{output.name}.json"
        runner.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
        await self.run_mock(packet, output, authorization, client=self.scripted(declined=declined))
        return runner.record(output / "report.json", runs_path=self.runs,
                             now=f"2026-09-30T01:{self.recorded:02d}:00Z")

    def experiment_prepare(self, *, panel="synthetic-dev", route="litellm-31b"):
        self.serial += 1
        directory = self.root / f"routing-{self.serial}"
        directory.mkdir()
        routing.prepare(self.database, directory / "packet.json", panel_id=panel, route_id=route,
                        accepted_commit=SHA, **self.registries)
        return directory / "packet.json"

    async def experiment(self, grant, **answers):
        packet = self.experiment_prepare()
        self.serial += 1
        slot = self.root / f"routing-run-{self.serial}"
        authorization = packet.parent / "authorization.json"
        routing.bind_authorization(packet, f"{GRANT}{grant}", authorization, slot)
        with patch.object(runner, "_admitted_client", return_value=self.scripted(sink=self.experiment_sent,
                                                                                 **answers)):
            return await routing.run_live(self.database, slot, packet_path=packet, authorization_path=authorization,
                                          accepted_commit=SHA, env_file=self.root / "unused.env",
                                          **self.registries), slot

    # ----------------------------------------------------------------- packet
    async def test_prepare_pins_the_router_the_narrowed_contexts_and_each_message(self):
        await self.baseline(901)
        packet = json.loads(self.experiment_prepare().read_text())
        self.assertEqual((packet["version"], packet["evidence_class"], packet["promotion_eligible"]),
                         ("routing-upper-bound-v1", "diagnostic_observation", False))
        canonical, _ = runner.build_packet(
            self.database, candidate_id=self.candidate, panel_id="synthetic-dev", route_id="litellm-31b",
            accepted_commit=SHA, gateway_policies=dict(runner.ROUTE_POLICY), **self.registries)
        self.assertEqual(packet["canonical_packet"], canonical)
        self.assertEqual([row["case_id"] for row in packet["inputs"]], [case.case_id for case in self.inputs])
        for row, case in zip(packet["inputs"], self.inputs):
            scenario = _SYNTHETIC_TABLE["synthetic-dev"][case.family_id]
            self.assertEqual(row["scenario"], scenario)
            self.assertEqual(row["messages_sha256"], routing._sha(routing.messages(scenario, case.question)))
        self.assertEqual(set(packet["scenarios"]), {"overview", "compare", "breakdown"})
        for scenario, pins in packet["scenarios"].items():
            self.assertEqual(pins, {"context_sha256": routing._sha(routing.narrowed_context(scenario)),
                                    "schema_name": routing.schema_name(scenario),
                                    "schema_sha256": routing._sha(routing.narrowed_schema(scenario))})
        self.assertEqual((packet["max_calls"], packet["run_seconds"]), (len(self.inputs), len(self.inputs) * 60.0 + 120))

    async def test_prepare_refuses_with_one_closed_reason(self):
        def refused(reason, **kwargs):
            with self.assertRaises(routing.ExperimentRefused) as refusal:
                self.experiment_prepare(**kwargs)
            self.assertEqual((refusal.exception.code, refusal.exception.reason), ("invalid_manifest", reason))

        refused("not_dev_panel", panel="synthetic-regression")
        refused("route", route="bedrock-sonnet")
        with patch.object(routing, "ROUTER_TABLE", {}):
            refused("router_table")
        wrong = {"synthetic-dev": dict(_SYNTHETIC_TABLE["synthetic-dev"], E02_compare="overview")}
        with patch.object(routing, "ROUTER_TABLE", wrong):
            refused("router_table")
        self.assertEqual(routing.REFUSALS, ("not_dev_panel", "route", "router_table"))

    # ----------------------------------------------------------------- live and comparison
    async def test_live_grades_through_the_production_pipeline_and_compares_with_the_baseline(self):
        x, z = self.inputs[0].case_id, self.inputs[2].case_id
        earlier = [await self.baseline(901, declined={x}), await self.baseline(902, declined={x})]
        sentinel = await self.baseline(950, declined={x})
        result, slot = await self.experiment(950, declined={z})
        # Exactly one model call per input; replaying the content through the pipeline makes none.
        self.assertEqual(len(self.experiment_sent), len(self.inputs))
        for request, case in zip(self.experiment_sent, self.inputs):
            scenario = _SYNTHETIC_TABLE["synthetic-dev"][case.family_id]
            body = json.loads(request.content)
            self.assertEqual(body["messages"], routing.messages(scenario, case.question))
            self.assertEqual(body["response_format"]["json_schema"],
                             {"name": routing.schema_name(scenario), "schema": routing.narrowed_schema(scenario)})
        self.assertEqual((result["status"], result["stop_reason"], result["client_http_attempts"]),
                         ("complete", "complete", len(self.inputs)))
        rows = {row["case_id"]: row for row in result["results"]}
        self.assertEqual((rows[x]["graded"]["outcome"], rows[z]["graded"]["outcome"]),
                         ("complete_correct", "false_refusal"))
        self.assertEqual(rows[z]["validated_action"], '{"outcome":"declined"}')
        self.assertEqual(rows[x]["usage"], {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7})
        comparison = result["comparison"]
        self.assertEqual(comparison["baseline_runs"], [run["run_id"] for run in (*earlier, sentinel)])
        self.assertEqual(comparison["sentinel_runs"], [sentinel["run_id"]])
        classes = {row["case_id"]: row["class"] for row in comparison["inputs"]}
        self.assertEqual((classes[x], classes[z]), ("fixed", "broke"))
        self.assertEqual((comparison["fixed"], comparison["broke"], comparison["verdict"]), ([x], [z], "regression"))
        self.assertEqual(routing.read_report(slot / "report.json", **self.registries), result)

        await self.baseline(951, declined={x})
        result, _ = await self.experiment(951)
        self.assertEqual((result["comparison"]["fixed"], result["comparison"]["verdict"]), ([x], "passed"))
        # Without a same-authorization sentinel the comparison is refused, but the report still reads back.
        result, _ = await self.experiment(952)
        self.assertEqual((result["comparison"]["verdict"], result["comparison"]["refusal"]), (None, "no_sentinel"))

    async def test_model_content_is_graded_and_route_failures_stop_unassessed(self):
        await self.baseline(959)
        await self.baseline(960)
        y, w = self.inputs[1].case_id, self.inputs[3].case_id
        result, _ = await self.experiment(960, broken={y}, page={w})
        rows = [(row["case_id"], row["state"], row["error_code"], (row["graded"] or {}).get("outcome"))
                for row in result["results"]]
        self.assertEqual(rows[1], (y, "returned", None, "invalid_output"))
        self.assertEqual(rows[3], (w, "failed", "unsupported_output", None))
        self.assertEqual({state for _, state, _, _ in rows[4:]}, {"not_started"})
        self.assertEqual((result["status"], result["stop_reason"]), ("incomplete", "anomaly"))
        classes = {row["case_id"]: (row["experiment"], row["class"]) for row in result["comparison"]["inputs"]}
        self.assertEqual(classes[y], ("wrong", "broke"))
        self.assertEqual(classes[w], ("unassessed", "unassessed"))
        self.assertEqual(result["comparison"]["verdict"], "regression")

    async def test_readback_rejects_tampering_and_live_refuses_drift_before_any_send(self):
        await self.baseline(970)
        result, slot = await self.experiment(970)
        path = slot / "report.json"
        raw = path.read_bytes()
        original = json.loads(raw)
        tampered = []
        for mutate in (lambda r: r["results"][0]["graded"].update(outcome="complete_correct_ish"),
                       lambda r: r["results"][0].update(completion_text="{}"),
                       lambda r: r.update(client_http_attempts=r["client_http_attempts"] + 1),
                       lambda r: r["results"][0].update(scenario="compare")):
            value = json.loads(json.dumps(original))
            mutate(value)
            tampered.append(value)
        for number, value in enumerate(tampered):
            with self.subTest(case=number):
                try:
                    path.write_text(json.dumps(value))
                    with self.assertRaises(p3_assets.P3Error):
                        routing.read_report(path, **self.registries)
                finally:
                    path.write_bytes(raw)
        self.assertEqual(routing.read_report(path, **self.registries)["status"], "complete")
        packet = self.experiment_prepare()
        authorization = packet.parent / "authorization.json"
        slot = self.root / "routing-drift-run"
        routing.bind_authorization(packet, f"{GRANT}971", authorization, slot)
        await self.baseline(971)
        sent = []
        with patch.object(runner, "_admitted_client", return_value=self.scripted(sink=sent)), \
                self.assertRaises(p3_assets.P3Error) as drift:
            await routing.run_live(self.database, slot, packet_path=packet, authorization_path=authorization,
                                   accepted_commit=SHA, env_file=self.root / "unused.env", **self.registries)
        self.assertEqual((drift.exception.code, sent, slot.exists()), ("manifest_drift", [], False))

    async def test_an_isolated_timeout_leaves_a_complete_run_readable(self):
        await self.baseline(985)
        await self.baseline(986)
        slow = self.inputs[1].case_id
        cases = self.inputs
        scripted = self.scripted(sink=self.experiment_sent)

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            if next(case for case in cases if case.question == question).case_id == slow:
                raise httpx.ReadTimeout("synthetic timeout")
            return scripted._transport.handle_request(request)

        packet = self.experiment_prepare()
        authorization = packet.parent / "authorization.json"
        slot = self.root / "routing-timeout-run"
        routing.bind_authorization(packet, f"{GRANT}986", authorization, slot)
        client = GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))
        with patch.object(runner, "_admitted_client", return_value=client):
            result = await routing.run_live(self.database, slot, packet_path=packet,
                                            authorization_path=authorization, accepted_commit=SHA,
                                            env_file=self.root / "unused.env", **self.registries)
        self.assertEqual((result["status"], result["results"][1]["error_code"]), ("complete", "timeout"))
        self.assertEqual(dict(zip(("experiment", "class"), next(
            (row["experiment"], row["class"]) for row in result["comparison"]["inputs"] if row["case_id"] == slow))),
            {"experiment": "unassessed", "class": "unassessed"})
        self.assertEqual(result["comparison"]["verdict"], "inconclusive")

    async def test_interruption_transport_and_pinned_assets(self):
        await self.baseline(989)
        await self.baseline(990)
        third = self.inputs[2].case_id
        with self.assertRaises(asyncio.CancelledError):
            await self.experiment(990, cancel={third})
        slot = sorted(self.root.glob("routing-run-*"), key=lambda path: int(path.name.rsplit("-", 1)[1]))[-1]
        result = routing.read_report(slot / "report.json", **self.registries)
        self.assertEqual((result["status"], result["stop_reason"], result["possible_in_flight_attempts"],
                          result["client_http_attempts"], result["results"][2]["error_code"]),
                         ("incomplete", "interrupted", 0, 3, "interrupted"))
        # A client on another transport than the packet's is refused before the first send.
        packet = self.experiment_prepare()
        authorization = packet.parent / "authorization.json"
        tls_slot = self.root / "routing-tls-run"
        routing.bind_authorization(packet, f"{GRANT}990", authorization, tls_slot)
        sent = []
        with patch.object(runner, "_admitted_client", return_value=self.scripted(
                sink=sent, base="https://synthetic-evaluate.invalid/v1")):
            result = await routing.run_live(self.database, tls_slot, packet_path=packet,
                                            authorization_path=authorization, accepted_commit=SHA,
                                            env_file=self.root / "unused.env", **self.registries)
        self.assertEqual((result["stop_reason"], result["results"][0]["error_code"], sent),
                         ("anomaly", "invalid_configuration", []))
        # Readback pins the oracles it grades against.
        target = self.root / "development-oracles-v1.json"
        raw = target.read_bytes()
        try:
            target.write_bytes(raw + b"\n")
            with self.assertRaises(p3_assets.P3Error) as drift:
                routing.read_report(tls_slot / "report.json", **self.registries)
            self.assertEqual(drift.exception.code, "manifest_drift")
        finally:
            target.write_bytes(raw)

    async def test_cli_dispatches_through_the_runner_and_its_arguments_are_closed(self):
        await self.baseline(980)
        directory = self.root / "cli"
        directory.mkdir()
        argv = ["--routing-upper-bound", "--prepare", "--panel", "synthetic-dev", "--route", "litellm-31b",
                "--db", str(self.database), "--accepted-commit", SHA, "--output", str(directory / "packet.json")]
        stdout = io.StringIO()
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                patch.object(runner, "ROUTES", self.routes), redirect_stdout(stdout):
            self.assertEqual(runner.main(argv), 0)
        self.assertEqual(json.loads(stdout.getvalue())["state"], "prepared_not_authorized")
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                patch.object(runner, "ROUTES", self.routes), patch("sys.stdout"), patch("sys.stderr"):
            for bad in (argv[:-2], argv + ["--variant", "fresh"], ["--routing-upper-bound", "--report"],
                        ["--routing-upper-bound", "--gate", "--panels", "synthetic-dev"]):
                with self.subTest(argv=bad):
                    self.assertEqual(runner.main(bad), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
