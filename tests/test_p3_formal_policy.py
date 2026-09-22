"""Versioned metadata-only policy tests; no actual fresh payloads or model calls."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import p3_admission, p3_assets, p3_eval, p3_scoring
import test_p3_admission as helpers
from test_p3_scoring import formal_scaffolding, successes

ROOT = Path(__file__).resolve().parent.parent
V1 = "p3-formal-allocation-v1"
V2 = "p3-formal-allocation-v2"


def revised_scaffolding():
    """Subset of existing synthetic metadata, not real FA input identities."""
    keep = {
        "synthetic-answer-frozen_fresh-1", "synthetic-answer-frozen_fresh-3",
        "synthetic-answer-exposed_regression-0", "synthetic-clarify-frozen_fresh-1",
        "synthetic-clarify-exposed_regression-0", "synthetic-clarify-exposed_regression-1",
        "synthetic-decline-frozen_fresh-0", "synthetic-decline-frozen_fresh-1",
        "synthetic-decline-exposed_regression-0", "synthetic-decline-exposed_regression-1",
        "synthetic-decline-exposed_regression-2", "synthetic-anchor-exposed_regression-0",
        "synthetic-anchor-exposed_regression-1", "synthetic-anchor-exposed_regression-2",
    }
    return [{**row, "order": index} for index, row in enumerate(
        (row for row in formal_scaffolding() if row["family_id"] in keep), 1)]


class FormalPolicyTests(unittest.TestCase):
    def setUp(self):
        for target in ("tools.p3_assets.read_asset", "socket.socket.connect", "socket.getaddrinfo",
                       "sqlite3.connect", "grepbit.gateway.GatewayClient.complete"):
            guard = patch(target, side_effect=AssertionError("Metadata policy must not read payloads or execute"))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)

    def policy(self):
        return importlib.import_module("tools.p3_formal_policy")

    def test_policy_is_separate_from_unchanged_protected_scorer(self):
        self.assertTrue((ROOT / "tools/p3_formal_policy.py").is_file(),
                        "Explicit allocation revision needs a separate admission policy, not a scorer edit")
        self.assertIn("tools/p3_scoring.py", p3_admission._FROZEN_TOOLS)
        self.assertEqual(hashlib.sha256((ROOT / "tools/p3_scoring.py").read_bytes()).hexdigest(),
                         "927dd43968e9afc83c805b15a0935e230b1ff2da0dc12fd6e89b0d7654679d6e")

    def test_historical_v1_accepts_24_44_and_rejects_14_28(self):
        self.policy().validate_allocation(formal_scaffolding(), V1)
        p3_scoring.validate_formal_allocation(formal_scaffolding())
        for validate in (p3_scoring.validate_formal_allocation,
                         lambda rows: self.policy().validate_allocation(rows, V1)):
            with self.assertRaisesRegex(p3_assets.P3Error, "invalid_panel"):
                validate(revised_scaffolding())

    def test_v2_accepts_exact_metadata_and_refuses_historical_allocation(self):
        self.policy().validate_allocation(revised_scaffolding(), V2)
        with self.assertRaisesRegex(p3_assets.P3Error, "invalid_panel"):
            self.policy().validate_allocation(formal_scaffolding(), V2)

    def test_v2_rejects_count_language_exposure_cohort_and_family_drift(self):
        mutations = (
            lambda rows: rows.pop(),
            lambda rows: rows[0].update(language="en"),
            lambda rows: rows[0].update(exposure="exposed_regression"),
            lambda rows: rows[0].update(cohort="anchor"),
            lambda rows: rows[0].update(family_id=rows[-1]["family_id"]),
            lambda rows: rows[0].update(case_id=rows[-1]["case_id"]),
            lambda rows: rows[0].update(semantic_signature="inconsistent-metadata"),
            lambda rows: rows[0].update(order=2),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                rows = revised_scaffolding()
                mutate(rows)
                with self.assertRaises(p3_assets.P3Error):
                    self.policy().validate_allocation(rows, V2)

    def test_v2_rejects_design_seen_observational_nonmandatory_and_p21(self):
        for changes in ({"exposure": "design_seen"}, {"observational": True}, {"must_pass": False},
                        {"case_id": "P21"}, {"family_id": "P21"}, {"slot": "P21"}):
            with self.subTest(changes=changes):
                rows = revised_scaffolding()
                rows[0].update(changes)
                with self.assertRaises(p3_assets.P3Error):
                    self.policy().validate_allocation(rows, V2)

    def test_cross_strata_cannot_drift_even_when_total_marginals_match(self):
        rows = revised_scaffolding()
        for row in rows:
            if row["family_id"] == "synthetic-answer-frozen_fresh-1":
                row["exposure"] = "exposed_regression"
            elif row["family_id"] == "synthetic-anchor-exposed_regression-0":
                row["exposure"] = "frozen_fresh"
        with self.assertRaises(p3_assets.P3Error):
            self.policy().validate_allocation(rows, V2)

    def test_input_marginals_are_checked_separately_from_family_counts(self):
        for target in ("synthetic-answer-exposed_regression-0", "synthetic-clarify-frozen_fresh-1"):
            rows = revised_scaffolding()
            representative = next(row for row in rows if row["family_id"] == target)
            for field in ("family_id", "semantic_signature", "exposure", "cohort", "expected_branch", "oracle_id"):
                rows[0][field] = representative[field]
            with self.subTest(target=target), self.assertRaises(p3_assets.P3Error):
                self.policy().validate_allocation(rows, V2)

    def test_identity_is_closed_explicit_and_hash_pinned(self):
        for version in (V1, V2):
            pin = self.policy().identity(version)
            self.assertEqual(set(pin), {"version", "sha256"})
            self.assertEqual(self.policy().validate_identity(pin), version)
            for bad in ({**pin, "sha256": "0" * 64}, {**pin, "extra": True},
                        {"version": version}, None, version):
                with self.assertRaises(p3_assets.P3Error):
                    self.policy().validate_identity(bad)
        self.assertNotEqual(self.policy().identity(V1), self.policy().identity(V2))
        for bad in (None, "v2", {}, "p3-formal-allocation-v3"):
            with self.assertRaises(p3_assets.P3Error):
                self.policy().identity(bad)

    def test_accounting_is_reused_exactly_not_reimplemented(self):
        rows = revised_scaffolding()
        results = successes(rows)
        expected = p3_scoring.summarize(rows, results, panel_kind="development", run_status="complete")
        actual = self.policy().summarize(rows, results, panel_kind="formal", run_status="complete",
                                         allocation_policy=self.policy().identity(V2))
        self.assertTrue(actual["promotion"]["passed"])
        self.assertEqual(actual["promotion"]["required_answer_successes"], 3)
        self.assertEqual(actual["promotion"]["required_fresh_answer_successes"], 2)
        actual.pop("allocation_policy")
        actual["panel_kind"] = "development"
        actual["promotion"].update(eligible=False, passed=False)
        self.assertEqual(actual, expected)

    def test_every_variant_and_checked_wrong_veto_remain_mandatory(self):
        rows = revised_scaffolding()
        for index in range(len(rows)):
            results = successes(rows)
            results[index]["outcome"] = "partial" if rows[index]["expected_branch"] == "answer" else "wrong_action"
            with self.subTest(index=index):
                result = self.policy().summarize(rows, results, panel_kind="formal", run_status="complete",
                                                 allocation_policy=self.policy().identity(V2))
                self.assertFalse(result["promotion"]["passed"])
        results = successes(rows)
        results[0]["checked_wrong"] = True
        result = self.policy().summarize(rows, results, panel_kind="formal", run_status="complete",
                                         allocation_policy=self.policy().identity(V2))
        self.assertTrue(result["checked_wrong_veto"])
        self.assertFalse(result["promotion"]["passed"])

    def test_legacy_summary_and_no_implicit_v2_are_preserved(self):
        rows = formal_scaffolding()
        expected = p3_scoring.summarize(rows, successes(rows), panel_kind="formal", run_status="complete")
        self.assertEqual(self.policy().summarize(rows, successes(rows), panel_kind="formal", run_status="complete"),
                         expected)
        with self.assertRaises(p3_assets.P3Error):
            self.policy().summarize(revised_scaffolding(), successes(revised_scaffolding()),
                                    panel_kind="formal", run_status="complete")
        with self.assertRaises(p3_assets.P3Error):
            self.policy().summarize(rows, successes(rows), panel_kind="development", run_status="complete",
                                    allocation_policy=self.policy().identity(V1))

    def test_stability_is_fixed_owner_selection_with_unresolved_fresh_case_ids(self):
        selection = self.policy().stability_preselection()
        self.assertEqual(selection["trials_per_input"], 3)
        self.assertEqual([(row["slot"], row["language"]) for row in selection["inputs"]],
                         [("P02", "zh-TW"), ("P04", "en"), ("R03", "ja"),
                          ("P14", "zh-TW"), ("P17", "ja"), ("P18", "en")])
        self.assertEqual(sum(row["case_id"] is None for row in selection["inputs"]), 5)
        self.assertEqual(selection["inputs"][2]["case_id"], "E03_share_denominator.ja")
        selection["inputs"].clear()
        self.assertEqual(len(self.policy().stability_preselection()["inputs"]), 6)


class PolicyPreparationTests(helpers.MetadataPublicationAssertions):
    """Mock native intake with existing synthetic metadata, never fresh payloads.

Only existing exposed development bytes are copied as publication witnesses.
No artifact produced by these plumbing tests is a real formal freeze.
"""
    def setUp(self):
        super().setUp()
        self.rows = revised_scaffolding()
        for row in self.rows:
            row["provenance"] = helpers.metadata_provenance(row["exposure"])
        case_ids = {row["case_id"] for row in self.rows}
        oracle_ids = {row["oracle_id"] for row in self.rows}
        self.mock_cases = tuple(case for case in self.mock_cases if case.case_id in case_ids)
        self.mock_oracles = tuple(oracle for oracle in self.mock_oracles if oracle.oracle_id in oracle_ids)
        for name in ("development-cases-v1.json", "development-oracles-v1.json"):
            (self.directory / name).write_bytes((helpers.DEVELOPMENT / name).read_bytes())
        self.panel_path = self.directory / "synthetic-policy-panel.json"
        self.panel_doc = {
            "version": "p3-panel-v1", "panel_id": "SyntheticPolicyPlumbingNotAdmitted", "kind": "formal",
            "cases": "development-cases-v1.json", "oracles": "development-oracles-v1.json",
            "order": [row["case_id"] for row in self.rows],
        }
        self.write_json(self.panel_path, self.panel_doc)
        self.review = {
            "families": helpers.abstract_reviews(self.rows), "owner_review_reference": helpers.OWNER_REFERENCE,
            "state": "novelty_reviewed",
            **{name: p3_eval._pin(self.directory / self.panel_doc[name]) for name in ("cases", "oracles")},
        }
        self.intake = self.enterContext(patch.object(
            p3_admission, "_intake", side_effect=lambda path: (
                copy.deepcopy(self.review), self.mock_cases, self.mock_oracles, {"review_assertions_complete": True})))
        self.prepared = self.directory / "synthetic-policy-preparation"

    def prepare_policy(self):
        self.freeze(allocation_policy=V2)
        return p3_eval.prepare(self.database, self.prepared,
                              panel_path=self.output / self.panel_path.name,
                              formal_freeze=self.output / "report.json",
                              accepted_commit=helpers.SYNTHETIC_TOOLING_COMMIT)

    def read_prepared(self):
        by_id = {oracle.oracle_id: oracle for oracle in self.mock_oracles}
        with patch.object(p3_assets, "parse_oracle", side_effect=lambda value: by_id[value["oracle_id"]]):
            return p3_eval.read_report(self.prepared / "report.json")

    def test_policy_is_pinned_in_mock_freeze_manifest_report_and_summary(self):
        report = self.prepare_policy()
        pin = importlib.import_module("tools.p3_formal_policy").identity(V2)
        freeze = json.loads((self.output / "report.json").read_bytes())
        manifest = json.loads((self.prepared / "manifest.json").read_bytes())
        for document in (freeze, manifest, report, report["summary"]):
            self.assertEqual(document["allocation_policy"], pin)
        self.assertEqual(freeze["version"], "p3-formal-freeze-v2")
        self.assertEqual(manifest["manifest_version"], "p3-manifest-v2")
        self.assertEqual(report["report_version"], "p3-report-v2")
        self.assertIn("tools/p3_formal_policy.py", manifest["identities"]["files_sha256"])
        self.assertEqual((report["status"], report["client_http_attempts"], report["live_model_attempts"]),
                         ("prepared", 0, 0))
        self.assertEqual((report["summary"]["semantic_families"], len(report["results"])), (14, 28))
        self.assertFalse(report["summary"]["promotion"]["passed"])
        self.assertTrue(all(row["status"] == "not_run" and not row["runtime_invoked"] for row in report["results"]))
        self.assertEqual(self.read_prepared(), report)

    def test_v2_archive_is_offline_and_independent_of_current_checkout(self):
        report = self.prepare_policy()
        for target in ("tools.p3_eval._source_identity", "tools.p3_admission.validate_freeze",
                       "tools.p3_admission._intake", "tools.p3_admission.candidate_identity",
                       "tools.p3_assets.load_panel", "tools.smoke._fixture_identity"):
            self.poison(target)
        self.assertEqual(self.read_prepared(), report)

    def test_policy_cannot_be_removed_changed_or_downgraded_in_archives(self):
        report = self.prepare_policy()
        manifest = json.loads((self.prepared / "manifest.json").read_bytes())
        for mutation in ("remove", "hash", "version", "envelope", "report"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(manifest)
                changed_report = copy.deepcopy(report)
                if mutation == "remove":
                    changed.pop("allocation_policy")
                elif mutation == "hash":
                    changed["allocation_policy"]["sha256"] = "0" * 64
                elif mutation == "version":
                    changed["allocation_policy"] = importlib.import_module("tools.p3_formal_policy").identity(V1)
                    changed_report["allocation_policy"] = changed["allocation_policy"]
                elif mutation == "envelope":
                    changed["manifest_version"] = "p3-manifest-v1"
                else:
                    changed_report.pop("allocation_policy")
                changed_report["manifest_sha256"] = p3_assets.digest(changed)
                self.write_json(self.prepared / "manifest.json", changed)
                self.write_json(self.prepared / "report.json", changed_report)
                with self.assertRaises(p3_assets.P3Error):
                    self.read_prepared()

    def test_policy_and_hash_are_revalidated_in_freeze(self):
        payload = self.freeze(allocation_policy=V2)
        for mutation in ("remove", "hash", "version", "envelope"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(payload)
                if mutation == "remove":
                    changed.pop("allocation_policy")
                elif mutation == "hash":
                    changed["allocation_policy"]["sha256"] = "0" * 64
                elif mutation == "version":
                    changed["allocation_policy"] = importlib.import_module("tools.p3_formal_policy").identity(V1)
                else:
                    changed["version"] = "p3-formal-freeze-v1"
                self.write_json(self.output / "report.json", changed)
                self.write_json(self.output / "manifest.json", {
                    "version": changed["version"], "state": "incomplete", "planned_sha256": p3_assets.digest(changed)})
                with self.assertRaises(p3_assets.P3Error):
                    self.validate_frozen()

    def test_v2_panel_envelope_requires_exact_membership_pins_and_formal_kind(self):
        for changes in ({"kind": "development"}, {"order": self.panel_doc["order"][:-1]},
                        {"order": self.panel_doc["order"] + self.panel_doc["order"][:1]},
                        {"cases": "../development-cases-v1.json"}, {"version": "p3-panel-v99"}):
            with self.subTest(changes=changes):
                self.write_json(self.panel_path, {**self.panel_doc, **changes})
                with self.assertRaises(p3_assets.P3Error):
                    p3_admission._policy_materials(self.intake_path, self.panel_path, V2)

    def test_v2_uses_native_intake_errors_and_review_gate_without_bypass(self):
        self.intake.side_effect = p3_assets.P3Error("invalid_panel")
        self.rejects(p3_admission._policy_materials, self.intake_path, self.panel_path, V2, code="invalid_panel")
        self.intake.side_effect = None
        self.intake.return_value = (self.review, self.mock_cases, self.mock_oracles, {"review_assertions_complete": False})
        self.rejects(p3_admission._policy_materials, self.intake_path, self.panel_path, V2, code="formal_not_admitted")

    def test_execution_is_not_authorized_by_v2_preparation(self):
        report = self.prepare_policy()
        for changes in ({"status": "complete"}, {"client_http_attempts": 1}, {"origin": "mock"}):
            self.write_json(self.prepared / "report.json", {**report, **changes})
            self.rejects(self.read_prepared, code="formal_not_admitted")


class ExplicitHistoricalPolicyTests(helpers.MetadataPublicationAssertions):
    def test_explicit_v1_identity_uses_new_envelope_without_changing_old_allocation(self):
        payload = self.freeze(allocation_policy=V1)
        self.assertEqual(payload["allocation_policy"]["version"], V1)
        self.assertEqual((payload["allocation"]["families"], payload["allocation"]["inputs"]), (24, 44))
        self.assertEqual(self.validate_frozen()["allocation_policy"], payload["allocation_policy"])
