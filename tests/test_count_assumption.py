"""Count-assumption evaluation rulers (count-assumption-eval-v1, ADR #136, route A): offline, synthetic registries."""
import hashlib
import json
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx

from grepbit import model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import candidate_registry as registry, evaluate as runner, p3_assets
from test_evaluate import BASE, GRANT, KEY, EvaluateHarness, envelope

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "evals/dev"
ASSUMPTION = {"count_basis": "booked_seats"}
CHANGED = {"p3-dev-bound-meaning": ("dev-BM6",),
           "p3-dev-mechanism-probe": ("dev-BM6", "dev-MN1", "dev-MN2", "dev-MN3")}
OTHER = "p3-bound-meaning-context-v8"


def _bm5():
    return next(oracle for oracle in json.loads((DEV / "bound-meaning-oracles-v1.json").read_text())["oracles"]
                if oracle["oracle_id"] == "dev-BM5.v1")


class FrozenAndDataTests(unittest.TestCase):
    def test_route_a_changes_no_protected_file(self):
        baseline = json.loads((ROOT / "tests/fixtures/p310_identity_baseline.json").read_text())
        for name in ("tools/p3_assets.py", "tools/p3_grading.py", "tools/p3_scoring.py"):
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                                 baseline["protected_files_sha256"][name])

    def test_the_v2_panels_differ_from_v1_only_where_the_rule_table_says(self):
        registered = {row["panel_id"]: row for row in runner.load_panels()["panels"]}
        # The loader canonicalizes request instants, so compare parsed oracles.
        bm5 = {key: value for key, value in p3_assets.parse_oracle(_bm5()).to_dict().items()
               if key not in ("oracle_id", "revision", "provenance")}
        for stem, families in CHANGED.items():
            with self.subTest(panel=stem):
                old_entry, new_entry = registered[f"{stem}-v1"], registered[f"{stem}-v2"]
                short = stem[len("p3-dev-"):]
                annex_path = DEV / f"{short}-annex-v2.json"
                self.assertEqual(json.loads(annex_path.read_text()), {
                    "version": "count-assumption-annex-v1",
                    "expectations": {f"{family}.v2": ASSUMPTION for family in families}})
                self.assertNotIn("annex", old_entry)
                self.assertEqual(new_entry["annex"], {"path": f"evals/dev/{short}-annex-v2.json",
                                                      "sha256": hashlib.sha256(annex_path.read_bytes()).hexdigest()})
                self.assertEqual((new_entry["tier"], new_entry["authoring"], new_entry["allocation_policy"]),
                                 ("dev", "development", None))
                old = p3_assets.load_panel(ROOT / old_entry["path"])
                new = p3_assets.load_panel(ROOT / new_entry["path"])
                for name, path in {"panel": ROOT / new_entry["path"], "cases": new.cases_path,
                                   "oracles": new.oracles_path}.items():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), new_entry["assets"][name])
                self.assertEqual(runner.annex_expectations(new_entry, new),
                                 {f"{family}.v2": ASSUMPTION for family in families})
                self.assertEqual([case.case_id for case in new.cases], [case.case_id for case in old.cases])
                raw_old = {case["case_id"]: case for case in json.loads(old.cases_path.read_text())["cases"]}
                raw_new = {case["case_id"]: case for case in json.loads(new.cases_path.read_text())["cases"]}
                for position, case in enumerate(old.cases):
                    before, after = raw_old[case.case_id], raw_new[case.case_id]
                    self.assertEqual(after["question"], before["question"])
                    if case.family_id in families:
                        changed = {key for key in before if before[key] != after[key]}
                        self.assertEqual(changed, {"oracle_id", "expected_branch", "cohort", "semantic_signature"})
                        self.assertEqual((after["oracle_id"], after["expected_branch"], after["cohort"]),
                                         (f"{case.family_id}.v2", "answer", "answer"))
                        data = new.oracle_for(new.cases[position]).to_dict()
                        self.assertEqual((data["oracle_id"], data["revision"]), (f"{case.family_id}.v2", 2))
                        # A plain Overview answer: the expected assumption lives only in the annex.
                        self.assertEqual({k: v for k, v in data.items()
                                          if k not in ("oracle_id", "revision", "provenance")}, bm5)
                    else:
                        self.assertEqual(after, before)
                        self.assertEqual(model.canonical_json(new.oracle_for(case).to_dict()),
                                         model.canonical_json(old.oracle_for(case).to_dict()))
                for name, path in {"panel": ROOT / old_entry["path"], "cases": old.cases_path,
                                   "oracles": old.oracles_path}.items():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), old_entry["assets"][name])


class VerdictTests(unittest.TestCase):
    def action(self, **extra):
        return model.canonical_json({"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                                     "request": _bm5()["request"], **extra})

    def test_the_annex_verdict_checks_the_persisted_assumption(self):
        expectations = {"dev-BM6.v2": ASSUMPTION}
        listed = {"oracle_id": "dev-BM6.v2", "validated_action": self.action(assumption=ASSUMPTION)}
        silent = {"oracle_id": "dev-BM6.v2", "validated_action": self.action()}
        spurious = {"oracle_id": "dev-BM5.v1", "validated_action": self.action(assumption=ASSUMPTION)}
        plain = {"oracle_id": "dev-BM5.v1", "validated_action": self.action()}
        unrecorded = {"oracle_id": "dev-BM6.v2", "validated_action": None}
        self.assertEqual([runner.annexed(row, True, expectations) for row in
                          (listed, silent, spurious, plain, unrecorded)],
                         ["correct", "wrong", "wrong", "correct", "unassessed"])
        self.assertEqual(runner.annexed(listed, False, expectations), "wrong")
        self.assertIsNone(runner.annexed(listed, True, None))

    def test_a_persisted_action_admits_only_the_stated_overview_assumption(self):
        base = json.loads(self.action())
        self.assertTrue(runner._action_shape(dict(base, assumption=ASSUMPTION)))
        self.assertTrue(runner._action_shape(base))
        for bad in ({"count_basis": "distinct_people"}, {"count_basis": "booked_seats", "x": 1}, "booked_seats"):
            with self.subTest(bad=bad):
                self.assertFalse(runner._action_shape(dict(base, assumption=bad)))
        compare = {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": {}}
        self.assertFalse(runner._action_shape(dict(compare, assumption=ASSUMPTION)))

    def test_the_annex_document_is_closed(self):
        for bad in ({"version": "count-assumption-annex-v1", "expectations": {}},
                    {"version": "count-assumption-annex-v2", "expectations": {"a.v2": ASSUMPTION}},
                    {"version": "count-assumption-annex-v1", "expectations": {"a.v2": {"count_basis": "x"}}},
                    {"version": "count-assumption-annex-v1", "expectations": {"a.v2": ASSUMPTION}, "note": ""}):
            with self.subTest(bad=bad), patch.object(runner, "_read_json", return_value=bad), \
                    self.assertRaises(p3_assets.P3Error):
                runner._read_annex(Path("unused"))


class AnnexRunTests(EvaluateHarness):
    """A synthetic dev panel whose Overview answers (E01_overview) expect the stated assumption."""

    def setUp(self):
        super().setUp()
        self.inputs = p3_assets.load_panel(self.root / "development-panel-v1.json").cases
        self.listed = [case.case_id for case in self.inputs if case.family_id == "E01_overview"]
        annex = self.root / "annex.json"
        annex.write_text(json.dumps({"version": "count-assumption-annex-v1",
                                     "expectations": {"E01_overview.v1": ASSUMPTION}}))
        index = json.loads(self.panels.read_text())
        index["panels"][0]["annex"] = {"path": f"{self.relative}/annex.json",
                                       "sha256": hashlib.sha256(annex.read_bytes()).hexdigest()}
        self.panels.write_text(json.dumps(index))
        self.recorded, self.repetitions = 0, {}
        self.stated = set()

    def client(self):
        cases = self.inputs

        def respond(request):
            question = json.loads(request.content)["messages"][-1]["content"]
            case = next(case for case in cases if case.question == question)
            return httpx.Response(200, json=envelope(json.dumps(self.by_oracle[case.oracle_id])))

        return GatewayClient(GatewayConfig(BASE, KEY, MODEL), transport=httpx.MockTransport(respond))

    @contextmanager
    def bytes_of(self, candidate_id):
        if candidate_id == self.candidate:
            yield
            return
        entry = registry.load_entry(candidate_id)
        checked = {"candidate_id": candidate_id, "semantic_identity_sha256": entry["semantic_identity_sha256"],
                   "runtime_files_changed": []}
        with patch.object(registry, "check", return_value=checked), \
                patch.object(registry, "current", return_value=entry), patch.object(self, "candidate", candidate_id):
            yield

    async def observe(self, grant, candidate=None):
        candidate = candidate or self.candidate
        self.repetitions[candidate] = self.repetitions.get(candidate, 0) + 1
        with self.bytes_of(candidate):
            packet = self.prepare(repetition=self.repetitions[candidate])
            output = self.output()
            authorization = self.root / f"authorization-{output.name}.json"
            runner.bind_authorization(packet, f"{GRANT}{grant}", authorization, output)
            await self.run_mock(packet, output, authorization, client=self.client())
        self.recorded += 1
        return runner.record(output / "report.json", runs_path=self.runs, panels_path=self.panels,
                             now=f"2026-09-30T02:{self.recorded:02d}:00Z"), output

    def stating(self, slots):
        """Serve archived reports as if the given runs had persisted the stated assumption on the listed rows."""
        original = runner._read_archived

        def read(path):
            report = original(path)
            if path.parent in slots:
                for row in report["results"]:
                    if row["case_id"] in self.listed:
                        action = json.loads(row["validated_action"])
                        row["validated_action"] = model.canonical_json({**action, "assumption": ASSUMPTION})
            return report

        return patch.object(runner, "_read_archived", side_effect=read)

    async def test_the_packet_pins_the_annex_and_record_counts_the_annex_verdict(self):
        run, output = await self.observe(901)
        packet = json.loads((output / "packet.json").read_text())
        self.assertEqual(packet["panel"]["annex_sha256"],
                         hashlib.sha256((self.root / "annex.json").read_bytes()).hexdigest())
        report = runner.read_report(output / "report.json")
        frozen = sum(item["correct"] for item in report["summary"]["per_input"])
        # Every answer is frozen-correct, but the listed Overview answers state no assumption.
        self.assertEqual((frozen, run["correct"]), (len(self.inputs), len(self.inputs) - len(self.listed)))
        self.assertEqual(run["families_correct"], len(report["summary"]["per_family"]) - 1)
        # A changed annex no longer matches the pinned digest.
        (self.root / "annex.json").write_text(json.dumps({"version": "count-assumption-annex-v1",
                                                         "expectations": {"E02_compare.v1": ASSUMPTION}}))
        with self.assertRaises(p3_assets.P3Error) as drift:
            runner._panel_annex(packet["panel"], self.panels)
        self.assertEqual(drift.exception.code, "manifest_drift")

    async def test_aggregate_and_gate_use_the_annex_verdict(self):
        baseline = [await self.observe(901), await self.observe(902)]
        sentinel = await self.observe(950)
        candidate = await self.observe(950, candidate=OTHER)
        classes = runner.aggregate("synthetic-dev", "litellm-31b", self.candidate, runs_path=self.runs,
                                   panels_path=self.panels)
        by_case = {row["case_id"]: row["class"] for row in classes["inputs"]}
        self.assertEqual({by_case[case] for case in self.listed}, {"stable_wrong"})
        self.assertEqual({kind for case, kind in by_case.items() if case not in self.listed}, {"stable_correct"})
        with self.stating({candidate[1]}):
            result = runner.gate(OTHER, self.candidate, "litellm-31b", f"{GRANT}950", ["synthetic-dev"],
                                 runs_path=self.runs, panels_path=self.panels)
        [panel] = result["panels"]
        self.assertEqual((sorted(panel["fixed"]), panel["broke"], panel["verdict"]),
                         (sorted(self.listed), [], "passed"))
        # The same candidate run without the stated assumption fixes nothing.
        result = runner.gate(OTHER, self.candidate, "litellm-31b", f"{GRANT}950", ["synthetic-dev"],
                             runs_path=self.runs, panels_path=self.panels)
        self.assertEqual((result["panels"][0]["fixed"], result["verdict"]), ([], "no_fix"))
        del baseline, sentinel


if __name__ == "__main__":
    unittest.main()
