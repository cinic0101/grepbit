"""An empty annex and the compare-first v3 panel (docs/count-assumption.md, ADR #146): offline only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import test_count_assumption as annex_runs
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from test_evaluate import BASE, GRANT, KEY, envelope
from tools import evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
V2, V3 = "p3-dev-matrix-compare-first-v2", "p3-dev-matrix-compare-first-v3"
ASSUMPTION = {"count_basis": "booked_seats"}


def entry(panel_id):
    return next(row for row in evaluate.load_panels()["panels"] if row["panel_id"] == panel_id)


class EmptyAnnexTests(unittest.TestCase):
    def test_an_empty_annex_is_admitted_and_malformed_ones_are_not(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".artifacts") as tmp:
            def read(document):
                path = Path(tmp) / f"annex-{hashlib.sha256(json.dumps(document).encode()).hexdigest()[:8]}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                return evaluate._read_annex(path)

            self.assertEqual(read({"version": evaluate.ANNEX_VERSION, "expectations": {}}), {})
            for bad in ({"version": evaluate.ANNEX_VERSION}, {"version": "other", "expectations": {}},
                        {"version": evaluate.ANNEX_VERSION, "expectations": []},
                        {"version": evaluate.ANNEX_VERSION, "expectations": {"x": {"count_basis": "distinct_people"}}},
                        {"version": evaluate.ANNEX_VERSION, "expectations": {}, "note": "x"}):
                with self.subTest(bad=bad), self.assertRaises(p3_assets.P3Error):
                    read(bad)

    def test_under_an_empty_annex_every_stated_assumption_is_wrong(self):
        for action, verdict in (({"outcome": "request", "recipe_id": "overview", "count_request": "none"}, "correct"),
                                ({"outcome": "request", "recipe_id": "overview", "count_request": "unresolved"}, "wrong"),
                                ({"outcome": "request", "recipe_id": "overview", "assumption": ASSUMPTION}, "wrong"),
                                ({"outcome": "declined"}, "correct")):
            row = {"oracle_id": "dev-A2.v1", "validated_action": json.dumps(action)}
            with self.subTest(action=action):
                self.assertEqual(evaluate.annexed(row, True, {}), verdict)
        self.assertEqual(evaluate.annexed({"oracle_id": "dev-A2.v1", "validated_action": None}, True, {}), "unassessed")


class CompareFirstV3PanelTests(unittest.TestCase):
    def test_v3_is_v2_with_dev_c1_ruled_rule_one(self):
        old, new = entry(V2), entry(V3)
        self.assertEqual((new["tier"], new["authoring"], new["allocation_policy"], new["intake"], new["freeze"]),
                         ("dev", "development", None, None, None))
        self.assertNotIn("annex", old)
        v2_bytes = (ROOT / old["path"]).read_text(encoding="utf-8")
        self.assertEqual((ROOT / new["path"]).read_text(encoding="utf-8"),
                         v2_bytes.replace(f'"panel_id": "{V2}"', f'"panel_id": "{V3}"', 1)
                         .replace('"cases": "dev-cases-v2.json"', '"cases": "dev-cases-v3.json"', 1)
                         .replace('"oracles": "dev-oracles-v2.json"', '"oracles": "dev-oracles-v3.json"', 1))
        for name, relative in (("panel", new["path"]), ("cases", "evals/dev/dev-cases-v3.json"),
                               ("oracles", "evals/dev/dev-oracles-v3.json")):
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), new["assets"][name], name)
        folder = ROOT / "evals/dev"
        cases = {name: {c["case_id"]: c for c in json.loads(
            (folder / f"dev-cases-{name}.json").read_text(encoding="utf-8"))["cases"]}
                 for name in ("v2", "v3")}
        self.assertEqual(list(cases["v2"]), list(cases["v3"]))
        for case_id, case in cases["v3"].items():
            before = cases["v2"][case_id]
            if case["family_id"] != "dev-C1":
                self.assertEqual(case, before, case_id)
                continue
            self.assertEqual({key for key in case if case[key] != before.get(key)},
                             {"oracle_id", "expected_branch", "cohort", "semantic_signature"})
            self.assertEqual((case["oracle_id"], case["expected_branch"], case["cohort"], case["question"]),
                             ("dev-C1.v2", "answer", "answer", before["question"]))
        oracles = {name: json.loads((folder / f"dev-oracles-{name}.json").read_text(encoding="utf-8"))["oracles"]
                   for name in ("v2", "v3")}
        ids = [o["oracle_id"] for o in oracles["v3"]]
        self.assertEqual(ids, [("dev-C1.v2" if i == "dev-C1.v1" else i) for i in (o["oracle_id"] for o in oracles["v2"])])
        by_id = {o["oracle_id"]: o for o in oracles["v2"] + oracles["v3"]}
        for oracle_id in ids:
            if oracle_id != "dev-C1.v2":
                self.assertEqual(by_id[oracle_id], next(o for o in oracles["v2"] if o["oracle_id"] == oracle_id))
        revised, a2 = by_id["dev-C1.v2"], by_id["dev-A2.v1"]
        drop = ("oracle_id", "revision", "provenance")
        self.assertEqual({k: v for k, v in revised.items() if k not in drop}, {k: v for k, v in a2.items() if k not in drop})
        self.assertEqual((revised["revision"], revised["request"]["center_code"]), (2, "CTR-B01"))
        panel = p3_assets.load_panel(ROOT / new["path"])
        self.assertEqual(panel.panel_id, V3)
        self.assertEqual(evaluate.annex_expectations(new, panel), {"dev-C1.v2": ASSUMPTION})
        annex = ROOT / new["annex"]["path"]
        self.assertEqual(hashlib.sha256(annex.read_bytes()).hexdigest(), new["annex"]["sha256"])


class EmptyAnnexRunTests(annex_runs.AnnexRunTests):
    """The run-level consumers under an empty annex: a stated assumption is wrong, never mistaken for no annex.

    The synthetic dev panel's E01 Overview answers are frozen-correct; the mock model states the assumption on
    them (count_request "unresolved") only in the runs named in ``self.stating_runs``."""

    def setUp(self):
        super().setUp()
        annex = self.root / "annex.json"
        annex.write_text(json.dumps({"version": evaluate.ANNEX_VERSION, "expectations": {}}))
        index = json.loads(self.panels.read_text())
        index["panels"][0]["annex"]["sha256"] = hashlib.sha256(annex.read_bytes()).hexdigest()
        self.panels.write_text(json.dumps(index))
        self.stating_runs, self.run_number = set(), 0

    def client(self):
        cases, number = self.inputs, self.run_number

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            action = dict(self.by_oracle[case.oracle_id])
            if number in self.stating_runs and case.case_id in self.listed:
                action["count_request"] = "unresolved"
            return httpx.Response(200, json=envelope(json.dumps(action)))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    async def observe(self, grant, candidate=None):
        self.run_number += 1
        return await super().observe(grant, candidate)

    async def test_the_packet_pins_the_annex_and_record_counts_the_annex_verdict(self):
        self.stating_runs = {1}
        run, output = await self.observe(901)
        packet = json.loads((output / "packet.json").read_text())
        self.assertEqual(packet["panel"]["annex_sha256"],
                         hashlib.sha256((self.root / "annex.json").read_bytes()).hexdigest())
        evaluate._packet_contract(packet)
        self.assertEqual(evaluate._panel_annex(packet["panel"], self.panels), {})
        report = evaluate.read_report(output / "report.json")
        frozen = sum(item["correct"] for item in report["summary"]["per_input"])
        self.assertEqual((frozen, run["correct"]), (len(self.inputs), len(self.inputs) - len(self.listed)))
        plain, _ = await self.observe(902)
        self.assertEqual(plain["correct"], len(self.inputs))

    async def test_the_packet_contract_and_the_annex_listing_are_checked(self):
        _, output = await self.observe(901)
        evaluate._packet_contract(json.loads((output / "packet.json").read_text()))
        entry = next(row for row in evaluate.load_panels(self.panels)["panels"] if row["panel_id"] == "synthetic-dev")
        panel = p3_assets.load_panel(self.root / "development-panel-v1.json")
        self.assertEqual(evaluate.annex_expectations(entry, panel), {})

    async def test_pooled_reports_must_pin_the_same_annex(self):
        first, second = await self.observe(901), await self.observe(902)
        reports = [evaluate._read_archived(first[1] / "report.json"), evaluate._read_archived(second[1] / "report.json")]
        self.assertEqual(evaluate._shared_annex(reports, self.panels), {})

    async def test_aggregate_and_gate_use_the_annex_verdict(self):
        await self.observe(901)
        await self.observe(902)
        await self.observe(950)
        self.stating_runs = {4}
        await self.observe(950, candidate=annex_runs.OTHER)
        aggregate = evaluate.aggregate("synthetic-dev", "litellm-31b", self.candidate, runs_path=self.runs,
                                       panels_path=self.panels)
        self.assertEqual({row["class"] for row in aggregate["inputs"]}, {"stable_correct"})
        [panel] = evaluate.gate(annex_runs.OTHER, self.candidate, "litellm-31b", f"{GRANT}950", ["synthetic-dev"],
                                runs_path=self.runs, panels_path=self.panels)["panels"]
        # The candidate states the assumption on the E01 answers, which the empty annex expects nowhere.
        self.assertEqual((sorted(panel["broke"]), panel["verdict"]), (sorted(self.listed), "regression"))

    async def test_the_gate_checks_the_annex_identity_and_the_sentinels_annex_assessment(self):
        await self.observe(901)
        await self.observe(902)
        sentinel = await self.observe(950)
        await self.observe(950, candidate=annex_runs.OTHER)
        original = evaluate._read_archived

        def without_annex(path):
            report = original(path)
            if path.parent == sentinel[1]:
                report["panel"] = {key: value for key, value in report["panel"].items() if key != "annex_sha256"}
            return report

        # A report without the empty annex's digest is a different input identity, not the same "no annex".
        with patch.object(evaluate, "_read_archived", side_effect=without_annex), \
                self.assertRaises(evaluate.GateRefused) as refused:
            evaluate.gate(annex_runs.OTHER, self.candidate, "litellm-31b", f"{GRANT}950", ["synthetic-dev"],
                          runs_path=self.runs, panels_path=self.panels)
        self.assertEqual(refused.exception.reason, "inputs_differ")

    async def test_replay_compares_the_annex_verdict(self):
        self.stating_runs = {1}
        _, output = await self.observe(901)
        with patch.object(evaluate, "PANELS", self.panels), patch.object(evaluate, "RUNS", self.runs):
            same = await evaluate._replay_execute(evaluate._replay_plan(
                output / "report.json", self.database, self.root / "replay-same.json"))
        listed = [row for row in same["rows"] if row["case_id"] in self.listed]
        self.assertEqual({row["class"] for row in same["rows"]}, {"replayed_same"})
        self.assertEqual({(row["annex"]["archived"], row["annex"]["replayed"]) for row in listed}, {("wrong", "wrong")})


if __name__ == "__main__":
    unittest.main()
