"""Candidate gate rulers (evaluation-gate-v3, #79, #164, #168): synthetic panels and mock transports only; no live call."""
from contextlib import contextmanager, redirect_stdout
import hashlib
import io
import json
from unittest.mock import patch

import httpx

from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate as runner, p3_assets
import registry_twin
from test_evaluate import BASE, GRANT, KEY, SERVER_ANSWERED, EvaluateHarness, envelope

OTHER = "p3-bound-meaning-context-v8"
_CLASSES = ("fixed", "broke", "unchanged_correct", "unchanged_wrong", "excluded", "unassessed")


class CandidateGateTests(EvaluateHarness):
    def setUp(self):
        # The baseline is the current candidate's twin; the real current candidate has its bytes.
        _, self.same_bytes = registry_twin.use(self)
        super().setUp()
        # A second development panel: the same inputs under another id and panel pin.
        raw = json.loads((self.root / "development-panel-v1.json").read_text())
        raw["panel_id"] = "synthetic-dev-b"
        (self.root / "dev-b-panel.json").write_text(json.dumps(raw))
        index = json.loads(self.panels.read_text())
        second = dict(index["panels"][0])
        second.update(panel_id="synthetic-dev-b", path=f"{self.relative}/dev-b-panel.json", note="dev b",
                      assets={**second["assets"],
                              "panel": hashlib.sha256((self.root / "dev-b-panel.json").read_bytes()).hexdigest()})
        index["panels"].append(second)
        self.panels.write_text(json.dumps(index))
        self.baseline = self.candidate
        self.inputs = p3_assets.load_panel(self.root / "development-panel-v1.json").cases
        self.repetitions, self.recorded = {}, 0

    # ----------------------------------------------------------------- helpers
    def client(self, broken=(), failing=(), wrong=(), error_page=()):
        """Scripted answers per case id: a valid decline (assessed and wrong: every chosen input expects an
        answer), raw invalid JSON (graded invalid_output: the candidate's answer, but unassessed in a
        baseline's aggregate class), a transport error (unassessed) or a gateway error page (an envelope
        failure that stops the run: unassessed, never the model's answer)."""
        cases = self.inputs

        def respond(request):
            self.sent.append(request)
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            if case.case_id in failing:
                raise httpx.ConnectError("synthetic transport failure", request=request)
            if case.case_id in error_page:
                return httpx.Response(200, text="<html>gateway error</html>", headers={"content-type": "text/html"})
            content = ("{not json" if case.case_id in broken else json.dumps({"outcome": "declined"})
                       if case.case_id in wrong else json.dumps(self.by_oracle[case.oracle_id]))
            return httpx.Response(200, json=envelope(content))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    @contextmanager
    def bytes_of(self, candidate_id):
        """Prepare and run as another registered candidate, whose model-facing bytes differ."""
        if candidate_id == self.baseline:
            yield
            return
        entry = registry.load_entry(candidate_id)
        checked = {"candidate_id": candidate_id, "semantic_identity_sha256": entry["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=entry), patch.object(self, "candidate", candidate_id):
            yield

    async def observe(self, grant, *, candidate=None, panel="synthetic-dev", broken=(), failing=(), wrong=(),
                      error_page=()):
        candidate = candidate or self.baseline
        key = (candidate, panel)
        self.repetitions[key] = self.repetitions.get(key, 0) + 1
        with self.bytes_of(candidate):
            packet = self.prepare(panel=panel, repetition=self.repetitions[key])
            output = self.output()
            authorization = self.root / f"authorization-{output.name}.json"
            runner.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
            await self.run_mock(packet, output, authorization, client=self.client(broken, failing, wrong, error_page))
        self.recorded += 1
        return runner.record(output / "report.json", runs_path=self.runs,
                             now=f"2026-09-29T00:{self.recorded:02d}:00Z")

    def gate(self, grant, *, panels=("synthetic-dev",), candidate=OTHER, baseline=None, route="litellm-31b",
             reference=None):
        return runner.gate(candidate, baseline or self.baseline, route, reference or f"{GRANT}{grant}", list(panels),
                           runs_path=self.runs, panels_path=self.panels)

    def refused(self, reason, grant, **kwargs):
        with self.assertRaises(runner.GateRefused) as refusal:
            self.gate(grant, **kwargs)
        self.assertEqual((refusal.exception.code, refusal.exception.reason), ("invalid_manifest", reason))

    # ----------------------------------------------------------------- classes and verdicts
    async def test_gate_classifies_each_input_against_the_measured_baseline_and_applies_the_verdict_in_order(self):
        ids = [case.case_id for case in self.inputs]
        x, y, z, w = ids[0], ids[1], ids[2], ids[-1]
        self.assertEqual([case.expected_branch for case in self.inputs[:3]], ["answer"] * 3)
        # Baseline: x wrong in every session, y wrong in one (flaky), every other input right. A baseline
        # "wrong" is a valid, graded decline; malformed output would leave the row unassessed.
        baseline = [await self.observe(901, wrong={x}), await self.observe(902, wrong={x, y}),
                    await self.observe(903, wrong={x}), await self.observe(904, wrong={x}),
                    await self.observe(905, wrong={x})]
        regression = await self.observe(902, candidate=OTHER, broken={y, z})
        passed = await self.observe(903, candidate=OTHER, broken={y})
        no_fix = await self.observe(904, candidate=OTHER, broken={x})
        inconclusive = await self.observe(905, candidate=OTHER, failing={w})
        # A stable baseline class needs three assessed runs (#168).
        second = [await self.observe(950, panel="synthetic-dev-b"), await self.observe(951, panel="synthetic-dev-b"),
                  await self.observe(903, panel="synthetic-dev-b")]
        other_panel = await self.observe(903, candidate=OTHER, panel="synthetic-dev-b", broken={z})

        result = self.gate(902)
        self.assertEqual(result, self.gate(902))
        self.assertEqual((result["version"], result["promotion_eligible"], result["claim"]),
                         ("evaluation-gate-v3", False, "development_observation"))
        self.assertEqual((result["route_id"], result["owner_authorization_reference"]), ("litellm-31b", f"{GRANT}902"))
        for key, cid in (("candidate", OTHER), ("baseline", self.baseline)):
            entry = registry.load_entry(cid)
            self.assertEqual(result[key], {"candidate_id": cid, "candidate_sha256": entry["candidate_sha256"],
                                           "behavior_sha256": registry.behavior_identity(entry)})
        self.assertEqual(result["run_index_sha256"], hashlib.sha256(self.runs.read_bytes()).hexdigest())
        [panel] = result["panels"]
        self.assertEqual(panel["panel_id"], "synthetic-dev")
        self.assertEqual(panel["baseline_runs"], [run["run_id"] for run in baseline])
        self.assertEqual(panel["sentinel_runs"], [baseline[1]["run_id"]])
        self.assertEqual(panel["candidate_run"], regression["run_id"])
        self.assertEqual([row["case_id"] for row in panel["inputs"]], ids)
        rows = {row["case_id"]: row for row in panel["inputs"]}
        self.assertEqual((rows[x]["baseline_class"], rows[x]["candidate"], rows[x]["class"]),
                         ("stable_wrong", "correct", "fixed"))
        self.assertEqual((rows[y]["baseline_class"], rows[y]["candidate"], rows[y]["class"]),
                         ("flaky", "wrong", "excluded"))
        self.assertEqual((rows[z]["baseline_class"], rows[z]["candidate"], rows[z]["class"]),
                         ("stable_correct", "wrong", "broke"))
        self.assertEqual({rows[i]["class"] for i in ids if i not in (x, y, z) and i not in SERVER_ANSWERED},
                         {"unchanged_correct"})
        # v19 answers the scripted C01 count_basis clarification, which its frozen oracle grades wrong (ADR #158).
        self.assertEqual({rows[i]["class"] for i in ids if i in SERVER_ANSWERED and i not in (x, y, z)},
                         {"unchanged_wrong"})
        # Malformed candidate output on an input the baseline always got right is a break, not unassessed.
        self.assertEqual((rows[x]["outcome"], rows[y]["outcome"], rows[z]["outcome"]),
                         ("complete_correct", "invalid_output", "invalid_output"))
        self.assertEqual((panel["fixed"], panel["broke"], panel["excluded"], panel["unassessed"]), ([x], [z], [y], []))
        self.assertEqual(panel["counts"], {"fixed": 1, "broke": 1, "unchanged_correct": 12 - len(SERVER_ANSWERED),
                                           "unchanged_wrong": len(SERVER_ANSWERED), "excluded": 1, "unassessed": 0})
        # A break is a regression even next to a fix; a gain never offsets it.
        self.assertEqual((panel["verdict"], result["counts"], result["verdict"]),
                         ("regression", panel["counts"], "regression"))

        result = self.gate(903)
        [panel] = result["panels"]
        self.assertEqual((panel["sentinel_runs"], panel["candidate_run"]), ([baseline[2]["run_id"]], passed["run_id"]))
        self.assertEqual((panel["fixed"], panel["broke"], panel["excluded"], panel["verdict"]), ([x], [], [y], "passed"))

        result = self.gate(904)
        [panel] = result["panels"]
        rows = {row["case_id"]: row for row in panel["inputs"]}
        self.assertEqual(panel["candidate_run"], no_fix["run_id"])
        self.assertEqual((rows[x]["class"], rows[y]["candidate"], rows[y]["class"]),
                         ("unchanged_wrong", "correct", "excluded"))
        self.assertEqual((rows[x]["candidate"], rows[x]["outcome"]), ("wrong", "invalid_output"))
        self.assertEqual((panel["fixed"], panel["broke"], panel["verdict"]), ([], [], "no_fix"))

        # An unassessed candidate row makes the gate inconclusive, even next to a fix.
        result = self.gate(905)
        [panel] = result["panels"]
        rows = {row["case_id"]: row for row in panel["inputs"]}
        self.assertEqual(panel["candidate_run"], inconclusive["run_id"])
        self.assertEqual((rows[w]["baseline_class"], rows[w]["candidate"], rows[w]["class"]),
                         ("stable_correct", "unassessed", "unassessed"))
        self.assertEqual((panel["fixed"], panel["unassessed"], panel["verdict"]), ([x], [w], "inconclusive"))

        # Several panels: each has its own verdict, and the overall verdict uses the union.
        result = self.gate(903, panels=("synthetic-dev", "synthetic-dev-b"))
        first, last = result["panels"]
        self.assertEqual((first["panel_id"], first["verdict"]), ("synthetic-dev", "passed"))
        self.assertEqual((last["panel_id"], last["baseline_runs"], last["sentinel_runs"], last["candidate_run"]),
                         ("synthetic-dev-b", [run["run_id"] for run in second], [second[2]["run_id"]],
                          other_panel["run_id"]))
        self.assertEqual((last["broke"], last["verdict"]), ([z], "regression"))
        self.assertEqual(result["counts"], {kind: first["counts"][kind] + last["counts"][kind] for kind in _CLASSES})
        self.assertEqual(result["verdict"], "regression")

    async def test_gate_keeps_route_failures_out_of_the_verdict_and_needs_same_session_evidence(self):
        ids = [case.case_id for case in self.inputs]
        x, z, w = ids[0], ids[2], ids[-1]
        earlier = [await self.observe(901, wrong={x}), await self.observe(901, wrong={x})]
        sentinel = await self.observe(902, wrong={x})
        route_failure = await self.observe(902, candidate=OTHER, error_page={z})
        await self.observe(903, wrong={x})
        regression = await self.observe(903, candidate=OTHER, broken={z}, failing={w})
        stopped = await self.observe(904, error_page={x})
        await self.observe(904, candidate=OTHER)
        unseen = await self.observe(905, failing={x})
        await self.observe(905, candidate=OTHER)
        self.assertEqual((route_failure["status"], stopped["status"], unseen["status"]),
                         ("incomplete", "incomplete", "complete"))

        # A gateway error page is an envelope failure: unassessed, so inconclusive rather than a regression.
        result = self.gate(902)
        [panel] = result["panels"]
        rows = {row["case_id"]: row for row in panel["inputs"]}
        self.assertEqual((rows[z]["baseline_class"], rows[z]["outcome"], rows[z]["candidate"], rows[z]["class"]),
                         ("stable_correct", "invalid_output", "unassessed", "unassessed"))
        self.assertEqual((panel["fixed"], panel["broke"], panel["verdict"]), ([x], [], "inconclusive"))
        self.assertEqual(panel["recorded_at"], {"sentinel_runs": [sentinel["recorded_at"]],
                                                "candidate_run": route_failure["recorded_at"]})
        # Same-bytes candidate runs under other authorizations stay visible: no silent re-gate.
        self.assertEqual(panel["other_candidate_runs"],
                         [run["run_id"] for run in runner.load_runs(self.runs)
                          if run["candidate_id"] == OTHER and run["grant"] != f"{GRANT}902"])

        # A break outranks an unassessed row on the same panel.
        [panel] = self.gate(903)["panels"]
        self.assertEqual((panel["candidate_run"], panel["broke"], panel["unassessed"], panel["verdict"]),
                         (regression["run_id"], [z], [w], "regression"))

        # A sentinel that did not complete gives no same-session evidence.
        self.refused("sentinel_incomplete", 904)
        # A complete sentinel that could not assess x: x is not a fix, however the earlier sessions classed it.
        [panel] = self.gate(905)["panels"]
        rows = {row["case_id"]: row for row in panel["inputs"]}
        self.assertEqual((rows[x]["baseline_class"], rows[x]["sentinel_assessed"], rows[x]["candidate"],
                          rows[x]["class"]), ("stable_wrong", False, "correct", "excluded"))
        self.assertEqual((panel["fixed"], panel["excluded"], panel["verdict"]), ([], [x], "no_fix"))

        # The index decides the selection, so it must agree with each digest-pinned report.
        rows = runner.load_runs(self.runs)

        def index(changed):
            self.runs.write_text("".join(json.dumps(changed.get(row["run_id"], row), sort_keys=True) + "\n"
                                         for row in rows))

        for label, changed in (("grant", dict(earlier[0], grant=f"{GRANT}902")),
                               ("status", dict(route_failure, status="complete"))):
            with self.subTest(field=label):
                index({changed["run_id"]: changed})
                self.refused("index_mismatch", 902)

    # ----------------------------------------------------------------- refusals
    async def test_gate_refuses_by_identity_with_one_closed_reason_before_any_verdict(self):
        x = self.inputs[0].case_id
        earlier = [await self.observe(901, wrong={x}), await self.observe(901, wrong={x})]
        sentinel = await self.observe(902, wrong={x})
        candidate = await self.observe(902, candidate=OTHER)
        rerun = await self.observe(902, candidate=OTHER)
        other_panel = await self.observe(901, candidate=OTHER, panel="synthetic-dev-b")

        def index(*rows):
            self.runs.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

        base = (*earlier, sentinel, candidate, other_panel)
        # No best-of: a second candidate run under the same authorization is refused.
        self.refused("multiple_candidate_runs", 902)
        index(*base)
        self.assertEqual(self.gate(902)["verdict"], "passed")
        self.refused("same_bytes", 902, candidate=self.baseline)
        # Another registered id with the baseline's bytes: a noise measurement, not a candidate.
        self.assertEqual(registry.load_entry(self.same_bytes)["candidate_sha256"],
                         registry.load_entry(self.baseline)["candidate_sha256"])
        self.refused("same_bytes", 902, candidate=self.same_bytes)
        self.refused("not_dev_panel", 902, panels=("synthetic-regression",))
        self.refused("not_dev_panel", 902, panels=("synthetic-dev", "synthetic-holdout"))
        self.refused("no_baseline_runs", 902, route="litellm-12b")
        self.refused("no_baseline_runs", 902, panels=("synthetic-dev", "synthetic-dev-b"))
        self.refused("no_sentinel", 999)
        self.refused("no_candidate_run", 901)
        for arguments in ({"panels": ("synthetic-dev", "synthetic-dev")}, {"reference": "not-a-grant"},
                          {"panels": ()}):
            with self.subTest(arguments=arguments), self.assertRaises(p3_assets.P3Error) as invalid:
                self.gate(902, **arguments)
            self.assertEqual(invalid.exception.code, "invalid_arguments")
        # Every selected report must carry its index entry's registry bytes: a baseline report
        # indexed as the candidate, and a candidate report indexed under a same-bytes baseline id.
        index(earlier[0], dict(earlier[1], candidate_id=OTHER), sentinel, candidate, other_panel)
        self.refused("candidate_identity", 901)
        index(*base, dict(rerun, candidate_id=self.same_bytes))
        self.refused("candidate_identity", 902)
        # A candidate report of another panel indexed under this panel's id.
        index(*earlier, sentinel, candidate, dict(other_panel, panel_id="synthetic-dev"))
        self.refused("inputs_differ", 901)
        # A changed question hash in the candidate report.
        index(*base)
        original = runner._read_archived

        def altered(path):
            report = original(path)
            if path.parent.as_posix().endswith(candidate["slot"]):
                report["results"][0]["question_sha256"] = "0" * 64
            return report

        with patch.object(runner, "_read_archived", side_effect=altered):
            self.refused("inputs_differ", 902)
        # An archive that no longer matches its index digest fails closed as drift, not as a refusal.
        index(*base[:-2], dict(candidate, report_sha256="0" * 64), other_panel)
        with self.assertRaises(p3_assets.P3Error) as drift:
            self.gate(902)
        self.assertNotIsInstance(drift.exception, runner.GateRefused)
        self.assertEqual(drift.exception.code, "manifest_drift")

    # ----------------------------------------------------------------- CLI
    async def test_cli_gate_prints_the_verdict_names_a_refusal_and_its_arguments_are_closed(self):
        x = self.inputs[0].case_id
        await self.observe(901, wrong={x})
        await self.observe(902, wrong={x})
        await self.observe(902, candidate=OTHER)
        expected = self.gate(902)
        argv = ["--gate", "--candidate", OTHER, "--baseline-candidate", self.baseline, "--route", "litellm-31b",
                "--owner-authorization-reference", f"{GRANT}902", "--panels", "synthetic-dev"]
        stdout = io.StringIO()
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                redirect_stdout(stdout):
            self.assertEqual(runner.main(argv), 0)
        self.assertEqual(json.loads(stdout.getvalue()), expected)
        for changed, reason in ((["--candidate", self.same_bytes], "same_bytes"),
                                (["--panels", "synthetic-dev", "synthetic-dev-b"], "no_baseline_runs")):
            with self.subTest(reason=reason):
                stderr = io.StringIO()
                with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                        patch("sys.stdout"), patch("sys.stderr", stderr):
                    code = runner.main([*argv[:argv.index(changed[0])], *changed,
                                        *argv[argv.index(changed[0]) + 2:]])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stderr.getvalue()),
                                 {"status": "incomplete", "error_code": "invalid_manifest", "gate_refusal": reason})
        with patch.object(runner, "RUNS", self.runs), patch.object(runner, "PANELS", self.panels), \
                patch("sys.stdout"), patch("sys.stderr"):
            for bad in (argv[:-2], argv[:1] + argv[3:], argv + ["--db", str(self.database)],
                        argv + ["--panels", "synthetic-dev"],
                        argv + ["--repetition", "2"], [("--panel" if a == "--panels" else a) for a in argv],
                        ["--aggregate", *argv[1:]], ["--gate", "--panel", "synthetic-dev", "--route", "litellm-31b",
                                                     "--candidate", OTHER]):
                with self.subTest(argv=bad):
                    self.assertEqual(runner.main(bad), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
