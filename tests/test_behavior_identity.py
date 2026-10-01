"""Behaviour identity rulers (docs/behavior-identity.md, ADR #164 option C): offline, temporary registries only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import candidate_registry as registry, evaluate, p3_assets

import registry_twin

ROOT = Path(__file__).resolve().parents[1]
GRANT = "https://github.com/cinic0101/grepbit/issues/164#issuecomment-1"
PANEL, ROUTE = "p3-dev-mechanism-probe-v2", "litellm-gemma-4-31b"
# Same-bytes groups of the registry at #164; each shares one behaviour identity, and no other entry shares one.
GROUPS = {
    "3c9b06ede23173e8": ("p3-31b-count-context-v7", "p3-v7-context-restoration-v10", "p3-v10-restoration-v12",
                         "p3-v12-restoration-v14"),
    "7cc9614581d51ea8": ("p3-count-scope-v18", "p3-v18-restoration-v20"),
    "37185c31027c0273": ("p3-count-basis-answer-v19",),
}


def formula(entry):
    """The contract's formula, written out independently of the registry module."""
    value = {"candidate_sha256": entry["candidate_sha256"], "runtime_files_sha256": entry["runtime_files_sha256"]}
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def runtime_drift(identity, name="grepbit/overview.py"):
    return dict(identity, runtime_files_sha256=dict(identity["runtime_files_sha256"], **{name: "0" * 64}))


class FormulaTests(unittest.TestCase):
    def test_every_entry_has_the_formula_identity_and_the_same_bytes_groups_are_kept(self):
        entries = [registry.load_entry(row["candidate_id"]) for row in registry.load_index()["entries"]]
        behaviours = {}
        for entry in entries:
            value = registry.behavior_identity(entry)
            self.assertEqual(value, formula(entry), entry["candidate_id"])
            behaviours.setdefault(value, []).append(entry["candidate_id"])
        for prefix, members in GROUPS.items():
            [group] = [ids for value, ids in behaviours.items() if value.startswith(prefix)]
            self.assertEqual(tuple(group), members)
        # The behaviour groups equal the model-input groups: no historical pooling changes.
        by_bytes = {}
        for entry in entries:
            by_bytes.setdefault(entry["candidate_sha256"], []).append(entry["candidate_id"])
        self.assertEqual(sorted(behaviours.values()), sorted(by_bytes.values()))
        live = registry.live_identity()
        self.assertEqual(registry.behavior_identity(live), formula(live))


class RegistrationTests(unittest.TestCase):
    def test_a_runtime_only_change_registers_and_an_unchanged_behaviour_does_not(self):
        with tempfile.TemporaryDirectory(prefix="behavior-", dir=ROOT / ".artifacts") as tmp:
            index_path = Path(tmp) / "index.json"
            registry.register("synthetic-base", "synthetic copy of the live identity", index_path=index_path,
                              now="2026-10-01T00:00:00Z")
            drifted = runtime_drift(registry.live_identity())
            with patch.object(registry, "live_identity", return_value=drifted):
                result = registry.register("synthetic-runtime", "one runtime file changed", index_path=index_path,
                                           now="2026-10-01T00:00:01Z")
                self.assertEqual(result["candidate_id"], "synthetic-runtime")
                with self.assertRaises(registry.RegistryError) as unchanged:
                    registry.register("synthetic-again", "same behaviour", index_path=index_path)
                self.assertEqual(unchanged.exception.code, "identity_unchanged")
            base = registry.load_entry("synthetic-base", index_path)
            runtime = registry.load_entry("synthetic-runtime", index_path)
            self.assertEqual(runtime["candidate_sha256"], base["candidate_sha256"])
            self.assertNotEqual(registry.behavior_identity(runtime), registry.behavior_identity(base))


class PrepareTests(unittest.TestCase):
    def test_a_packet_is_refused_while_a_runtime_file_differs_from_the_current_entry(self):
        current = registry.current()
        checked = {"candidate_id": current["candidate_id"], "semantic_identity_sha256": current["semantic_identity_sha256"],
                   "runtime_files_changed": ["grepbit/overview.py"]}
        with patch.object(registry, "check", return_value=checked), self.assertRaises(p3_assets.P3Error) as refused:
            evaluate.build_packet(ROOT / ".artifacts/unused.sqlite", candidate_id=current["candidate_id"],
                                  panel_id=PANEL, route_id=ROUTE, accepted_commit="0" * 40,
                                  gateway_policies=dict(evaluate.ROUTE_POLICY))
        self.assertEqual(refused.exception.code, "source_identity_failure")


class GateSelectionTests(unittest.TestCase):
    def setUp(self):
        self.same, self.sibling = registry_twin.use(self)
        self.runtime = registry_twin.use_runtime_twin(self)
        tmp = tempfile.TemporaryDirectory(prefix="behavior-runs-", dir=ROOT / ".artifacts")
        self.addCleanup(tmp.cleanup)
        self.runs = Path(tmp.name) / "runs.jsonl"
        self.runs.write_text("")

    def gate(self, candidate, baseline):
        return evaluate.gate(candidate, baseline, ROUTE, GRANT, [PANEL], runs_path=self.runs)

    def test_same_bytes_means_same_behaviour(self):
        for twin in (self.same, self.sibling):
            with self.subTest(candidate=twin), self.assertRaises(evaluate.GateRefused) as refused:
                self.gate(twin, self.sibling if twin == self.same else self.same)
            self.assertEqual(refused.exception.reason, "same_bytes")
        # A runtime twin shares the model input but not the behaviour, so the gate looks for runs.
        self.assertEqual(registry.load_entry(self.runtime)["candidate_sha256"],
                         registry.load_entry(self.sibling)["candidate_sha256"])
        with self.assertRaises(evaluate.GateRefused) as refused:
            self.gate(self.runtime, self.sibling)
        self.assertEqual(refused.exception.reason, "no_baseline_runs")

    def test_baselines_pool_by_behaviour_and_diagnostics_by_model_input(self):
        runs = [{"panel_id": PANEL, "route_id": ROUTE, "candidate_id": cid, "run_id": cid}
                for cid in (self.sibling, self.same, self.runtime)]
        behaviour = registry.behavior_identity(registry.load_entry(self.sibling))
        selected = evaluate._same_behavior_runs(PANEL, ROUTE, behaviour, runs, {}, None)
        self.assertEqual([run["run_id"] for run in selected], [self.sibling, self.same])
        model_input = registry.load_entry(self.sibling)["candidate_sha256"]
        selected = evaluate._same_bytes_runs(PANEL, ROUTE, model_input, runs, {}, None)
        self.assertEqual([run["run_id"] for run in selected], [self.sibling, self.same, self.runtime])

    def test_the_gate_and_aggregate_contracts_are_versioned(self):
        self.assertEqual((evaluate.GATE_VERSION, evaluate.AGGREGATE_VERSION),
                         ("evaluation-gate-v2", "evaluation-aggregate-v2"))


if __name__ == "__main__":
    unittest.main()
