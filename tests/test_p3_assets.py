"""Exposed development assets and pure parser controls, not fresh evaluation."""
from collections import Counter
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from grepbit.clarification import Clarification
from grepbit.recipe_model import _proposal
from tools import p3_assets, recipe_smoke


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "evals" / "p3"
PANEL = ASSETS / "development-panel-v1.json"


class P3AssetTests(unittest.TestCase):
    def setUp(self):
        for target in (
            "socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
            "socket.getaddrinfo", "httpx.AsyncHTTPTransport",
            "grepbit.gateway.GatewayConfig.from_env", "sqlite3.connect",
            "grepbit.execute_facts", "grepbit.execute_grouped_amount", "grepbit.execute_overview",
            "grepbit.execute_compare", "grepbit.execute_breakdown",
            "grepbit.recipe_model.execute_overview", "grepbit.recipe_model.execute_compare",
            "grepbit.recipe_model.execute_breakdown",
        ):
            guard = patch(target, side_effect=AssertionError("Asset loading must be pure and offline"))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.panel = json.loads(PANEL.read_text())
        self.cases = json.loads((ASSETS / self.panel["cases"]).read_text())
        self.oracles = json.loads((ASSETS / self.panel["oracles"]).read_text())

    def write_panel(self):
        for filename, document in (
            ("panel.json", self.panel),
            ("development-cases-v1.json", self.cases),
            ("development-oracles-v1.json", self.oracles),
        ):
            (self.directory / filename).write_text(json.dumps(document))
        return self.directory / "panel.json"

    def load(self):
        return p3_assets.load_panel(self.write_panel())

    def rejects(self, function, *args, code=None):
        with self.assertRaises(p3_assets.P3Error) as raised:
            function(*args)
        error = raised.exception
        self.assertIn(error.code, ("invalid_asset", "invalid_oracle", "invalid_panel"))
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(str(error), error.code)
        self.assertNotIn("PRIVATE_ASSET_CANARY", str(error))

    def test_development_panel_has_fifteen_exposed_inputs_and_nine_families(self):
        panel = p3_assets.load_panel(PANEL)
        self.assertEqual((panel.panel_id, panel.kind), ("p3-development-v1", "development"))
        self.assertEqual(len(panel.cases), 15)
        self.assertEqual(len(panel.oracles), 9)
        self.assertEqual(len({case.family_id for case in panel.cases}), 9)
        self.assertEqual(Counter(case.cohort for case in panel.cases),
                         {"anchor": 9, "clarify": 4, "decline": 2})
        self.assertEqual(Counter(case.language for case in panel.cases),
                         {"zh-TW": 3, "en": 9, "ja": 3})
        for case in panel.cases:
            self.assertEqual(case.exposure, "exposed_regression")
            self.assertEqual(case.provenance.exposure_history, ("exposed_regression",))
            self.assertTrue(case.provenance.seen_by_implementer)
            self.assertTrue(case.provenance.references)
            self.assertTrue(case.must_pass)
            self.assertFalse(case.observational)
            self.assertEqual(panel.oracle_for(case).branch, case.expected_branch)
        self.assertEqual({oracle.clarification.kind for oracle in panel.oracles
                          if isinstance(oracle, p3_assets.ClarifyOracle)},
                         {"count_basis", "comparison_roles", "center", "metric_meaning"})
        self.assertEqual({oracle.capability_category for oracle in panel.oracles
                          if isinstance(oracle, p3_assets.DeclineOracle)}, {"D01", "D02"})

    def test_anchor_order_questions_native_requests_coverage_and_values_are_unchanged(self):
        historical_inputs, historical_oracles = recipe_smoke.panel_inputs()
        historical_raw = json.loads((ROOT / "evals/panels/p2-recipe-smoke-v1.json").read_text())
        panel = p3_assets.load_panel(PANEL)
        for case, previous in zip(panel.cases[:9], historical_inputs, strict=True):
            self.assertEqual((case.family_id, case.language, case.question),
                             (previous["family"], previous["language"], previous["question"]))
            self.assertEqual(case.case_id, f'{previous["family"]}.{previous["language"]}')
            raw = next(item for item in self.oracles["oracles"] if item["oracle_id"] == case.oracle_id)
            parsed = panel.oracle_for(case).to_dict()
            for field in ("recipe_id", "recipe_version", "request", "coverage", "values"):
                self.assertEqual(raw[field], historical_raw["families"][case.family_id][field])
                self.assertEqual(parsed[field], historical_oracles[case.family_id][field])
        for family in historical_oracles:
            variants = [case for case in panel.cases if case.family_id == family]
            self.assertEqual(len({case.semantic_signature for case in variants}), 1)
            self.assertEqual(len({case.oracle_id for case in variants}), 1)

    def test_additional_overview_gold_pins_independent_reference_values_and_roles(self):
        overview = self.oracles["oracles"][0]
        self.assertEqual(overview["auxiliary_values"], {
            "daily_amount": [
                {"key": "2026-03-01", "value": 35000}, {"key": "2026-03-05", "value": 8000},
                {"key": "2026-03-07", "value": 10000}, {"key": "2026-03-10", "value": 15000},
            ],
            "category_amounts": [{"key": "arts", "value": 30000},
                                 {"key": "technology", "value": 38000}],
        })
        self.assertEqual(overview["required_slots"], ["amount", "bookings", "seats"])
        self.assertEqual(overview["auxiliary_slots"], ["daily_amount", "category_amounts"])
        self.assertEqual(overview["units"], {
            "amount": "TWD_minor", "bookings": "bookings", "seats": "seats",
            "daily_amount": "TWD_minor", "category_amounts": "TWD_minor",
        })
        self.assertEqual(set(overview["slot_states"].values()), {"checked"})
        provenance = "\n".join(overview["provenance"])
        for reference in ("Q11_category_breakdown", "Q12_daily_trend", "b.center_id=:center_id",
                          "reference-results-v1.json", "tests/test_overview.py", "grepbit/catalog.py"):
            self.assertIn(reference, provenance)
        for oracle in self.oracles["oracles"][:3]:
            self.assertEqual(oracle["catalog_sha256"],
                             "9027e2af35e49a790fd4c3e985ccff12e92868946f9398506ccfa7e623c897c5")
            self.assertEqual(set(oracle["slot_states"].values()), {"checked"})

    def test_fake_responses_are_separate_static_actions_with_matching_order(self):
        document = p3_assets.read_asset(ASSETS / "development-responses-v1.json")
        self.assertEqual(set(document), {"version", "responses"})
        self.assertEqual(document["version"], "p3-fake-responses-v1")
        panel = p3_assets.load_panel(PANEL)
        self.assertEqual([item["case_id"] for item in document["responses"]],
                         [case.case_id for case in panel.cases])
        for case, item in zip(panel.cases, document["responses"], strict=True):
            self.assertEqual(set(item), {"case_id", "action"})
            action, oracle = item["action"], panel.oracle_for(case)
            self.assertNotIn("presentation", action)
            self.assertNotIn("expected", action)
            if case.expected_branch == "answer":
                self.assertEqual(set(action), {"outcome", "recipe_id", "recipe_version", "request"})
                proposal = _proposal(action)
                self.assertEqual(recipe_smoke.canonical_request(proposal.request),
                                 oracle.to_dict()["request"])
            elif case.expected_branch == "clarify":
                self.assertEqual(set(action), {"outcome", "clarification"})
                actual = Clarification.from_mapping(action["clarification"])
                actual.validate_question(case.question)
                self.assertEqual(p3_assets.semantic_choices(actual), oracle.meaning["clarification"])
                self.assertTrue({choice.id for choice in actual.choices}.isdisjoint(
                    choice.id for choice in oracle.clarification.choices))
                self.assertNotEqual(actual.to_dict(), oracle.clarification.to_dict())
            else:
                self.assertEqual(action, {"outcome": "declined"})

    def test_case_fields_are_closed_required_and_strictly_typed(self):
        original = self.cases["cases"][0]
        for field in original:
            with self.subTest(missing=field):
                candidate = copy.deepcopy(original)
                del candidate[field]
                self.rejects(p3_assets.Case.from_mapping, candidate)
        for candidate in (None, [], True, {**original, "extra": "PRIVATE_ASSET_CANARY"}):
            self.rejects(p3_assets.Case.from_mapping, candidate)
        invalid_values = {
            "case_id": ("", 1, "bad id", "A" * 97),
            "family_id": (None, [], "1bad"),
            "oracle_id": (False, {}, "bad/path"),
            "question": ("", 1, "a" * 4097, "\u00e9" * 2049, "\ud800"),
            "language": ("fr", None, []),
            "expected_branch": ("request", "declined", [], None),
            "cohort": ("unknown", [], None),
            "exposure": ("fresh", [], None),
            "semantic_signature": ("", [], "a" * 1025),
            "must_pass": (1, 0, "true", None),
            "observational": (1, 0, "false", None),
        }
        for field, values in invalid_values.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.rejects(p3_assets.Case.from_mapping, {**original, field: value})

    def test_case_branch_cohort_and_required_observational_status_are_consistent(self):
        original = self.cases["cases"][0]
        for changes in (
            {"cohort": "clarify"}, {"cohort": "decline"}, {"expected_branch": "clarify"},
            {"must_pass": False}, {"observational": True},
        ):
            self.rejects(p3_assets.Case.from_mapping, {**original, **changes})
        observational = p3_assets.Case.from_mapping({
            **original, "must_pass": False, "observational": True, "cohort": "answer",
        })
        self.assertTrue(observational.observational)

    def test_all_exposure_labels_have_metadata_only_positive_witnesses(self):
        self.assertEqual(p3_assets.EXPOSURES, ("exposed_regression", "design_seen", "frozen_fresh"))
        for exposure, origin, seen in (
            ("exposed_regression", "historical", True),
            ("design_seen", "development", True),
            ("frozen_fresh", "independent", False),
        ):
            with self.subTest(exposure=exposure):
                record = {
                    **self.cases["cases"][0], "case_id": "AbstractMetadataOnly",
                    "family_id": "AbstractMetadataOnly", "question": "ABSTRACT_METADATA_ONLY",
                    "semantic_signature": "ABSTRACT_METADATA_ONLY", "exposure": exposure,
                    "provenance": {"origin": origin, "references": ["abstract metadata test"],
                                   "seen_by_implementer": seen, "exposure_history": [exposure]},
                }
                case = p3_assets.Case.from_mapping(record)
                self.assertEqual(case.exposure, exposure)
                self.assertEqual(case.provenance.seen_by_implementer, seen)

    def test_provenance_fields_types_and_history_are_strict(self):
        original = self.cases["cases"][0]["provenance"]
        for field in original:
            candidate = copy.deepcopy(original)
            del candidate[field]
            self.rejects(p3_assets.Provenance.from_mapping, candidate, "exposed_regression")
        invalid = (
            {"extra": "PRIVATE_ASSET_CANARY"}, {"origin": "unknown"}, {"origin": []},
            {"references": []}, {"references": "source"}, {"references": ["source", "source"]},
            {"references": [1]}, {"references": ["x"] * 17}, {"seen_by_implementer": 1},
            {"seen_by_implementer": "true"}, {"exposure_history": []},
            {"exposure_history": ["unknown"]}, {"exposure_history": ["design_seen"]},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                self.rejects(p3_assets.Provenance.from_mapping, {**original, **changes},
                             "exposed_regression")
        history = ["frozen_fresh", "design_seen", "exposed_regression", "exposed_regression"]
        parsed = p3_assets.Provenance.from_mapping(
            {**original, "exposure_history": history}, "exposed_regression")
        self.assertEqual(parsed.exposure_history, tuple(history))

    def test_history_cannot_launder_exposure_or_implementer_visibility(self):
        original = self.cases["cases"][0]["provenance"]
        for exposure, changes in (
            ("frozen_fresh", {}),
            ("design_seen", {}),
            ("frozen_fresh", {"origin": "independent", "seen_by_implementer": True}),
            ("frozen_fresh", {"origin": "development", "seen_by_implementer": False}),
            ("frozen_fresh", {"origin": "independent", "seen_by_implementer": False,
                              "exposure_history": ["design_seen", "frozen_fresh"]}),
            ("frozen_fresh", {"origin": "independent", "seen_by_implementer": False,
                              "exposure_history": ["exposed_regression", "frozen_fresh"]}),
            ("design_seen", {"origin": "development",
                             "exposure_history": ["exposed_regression", "design_seen"]}),
        ):
            with self.subTest(exposure=exposure, changes=changes):
                candidate = {**original, "exposure_history": [exposure], **changes}
                self.rejects(p3_assets.Provenance.from_mapping, candidate, exposure)

    def test_history_rejects_intermediate_laundering_even_when_final_label_is_exposed(self):
        original = self.cases["cases"][0]["provenance"]
        for history in (
            ["exposed_regression", "frozen_fresh", "exposed_regression"],
            ["design_seen", "frozen_fresh", "exposed_regression"],
            ["exposed_regression", "design_seen", "exposed_regression"],
        ):
            with self.subTest(history=history):
                self.rejects(p3_assets.Provenance.from_mapping,
                             {**original, "exposure_history": history}, "exposed_regression")

    def test_development_loader_rejects_fresh_metadata_without_authoring_fresh_material(self):
        item = self.cases["cases"][-1]
        item.update(question="ABSTRACT_METADATA_ONLY", semantic_signature="ABSTRACT_METADATA_ONLY",
                    exposure="frozen_fresh")
        item["provenance"] = {
            "origin": "independent", "references": ["abstract metadata test"],
            "seen_by_implementer": False, "exposure_history": ["frozen_fresh"],
        }
        self.rejects(self.load, code="invalid_panel")

    def test_loader_accepts_design_seen_development_material_without_promoting_it(self):
        for item in self.cases["cases"]:
            item["exposure"] = "design_seen"
            item["provenance"].update(origin="development", exposure_history=["design_seen"])
        self.assertEqual({case.exposure for case in self.load().cases}, {"design_seen"})

    def test_panel_and_collection_versions_and_closed_fields(self):
        for attribute, collection in (("panel", None), ("cases", "cases"), ("oracles", "oracles")):
            original = copy.deepcopy(getattr(self, attribute))
            for field in original:
                with self.subTest(asset=attribute, missing=field):
                    candidate = copy.deepcopy(original)
                    del candidate[field]
                    setattr(self, attribute, candidate)
                    self.rejects(self.load)
            for version in (None, [], True, "p3-unknown-v1", "p3-cases-v2"):
                setattr(self, attribute, {**original, "version": version})
                self.rejects(self.load)
            setattr(self, attribute, {**original, "extra": "PRIVATE_ASSET_CANARY"})
            self.rejects(self.load)
            if collection:
                for value in ([], {}, None, [original[collection][0]] * 65):
                    setattr(self, attribute, {**original, collection: value})
                    self.rejects(self.load)
            setattr(self, attribute, original)
        for kind in (None, [], "live", "fresh"):
            self.panel["kind"] = kind
            self.rejects(self.load)

    def test_panel_order_is_explicit_not_inferred_from_case_file_position(self):
        self.cases["cases"].reverse()
        panel = self.load()
        self.assertEqual([case.case_id for case in panel.cases], self.panel["order"])
        self.panel["order"].reverse()
        self.assertEqual([case.case_id for case in self.load().cases], self.panel["order"])

    def test_input_count_limit_uses_unique_exposed_aliases_not_duplicate_id_failures(self):
        original = self.cases["cases"][0]
        self.cases["cases"] = [
            {**copy.deepcopy(original), "case_id": f"ExposedAlias{index}"}
            for index in range(64)
        ]
        self.oracles["oracles"] = self.oracles["oracles"][:1]
        self.panel["order"] = [case["case_id"] for case in self.cases["cases"]]
        self.assertEqual(len(self.load().cases), 64)
        self.cases["cases"].append({**copy.deepcopy(original), "case_id": "ExposedAlias64"})
        self.panel["order"].append("ExposedAlias64")
        self.rejects(self.load, code="invalid_panel")

    def test_duplicate_case_oracle_and_order_ids_and_missing_order_entries_reject(self):
        for attribute, field in (("cases", "cases"), ("oracles", "oracles"), ("panel", "order")):
            original = copy.deepcopy(getattr(self, attribute))
            for change in ("duplicate", "empty", "missing"):
                candidate = copy.deepcopy(original)
                if change == "duplicate":
                    candidate[field].append(copy.deepcopy(candidate[field][0]))
                elif change == "empty":
                    candidate[field] = []
                else:
                    candidate[field].pop()
                setattr(self, attribute, candidate)
                self.rejects(self.load)
            setattr(self, attribute, original)
        self.panel["order"][0] = "UnknownCase"
        self.rejects(self.load)

    def test_oracle_references_must_be_complete_exact_and_branch_consistent(self):
        original = self.cases["cases"][0]["oracle_id"]
        for oracle_id in ("UnknownOracle", "D01_profit.v1", "C01_count_basis.v1"):
            self.cases["cases"][0]["oracle_id"] = oracle_id
            self.rejects(self.load)
        self.cases["cases"][0]["oracle_id"] = original
        unused = copy.deepcopy(self.oracles["oracles"][0])
        unused["oracle_id"] = "UnusedOracle"
        self.oracles["oracles"].append(unused)
        self.rejects(self.load)

    def test_family_variants_require_consistent_signature_status_cohort_and_exposure(self):
        original = copy.deepcopy(self.cases["cases"][0])
        for changes in (
            {"semantic_signature": "different semantic meaning"}, {"cohort": "answer"},
            {"must_pass": False, "observational": True},
            {"exposure": "design_seen", "provenance": {
                **original["provenance"], "origin": "development", "exposure_history": ["design_seen"],
            }},
        ):
            with self.subTest(changes=changes):
                self.cases["cases"][0] = {**copy.deepcopy(original), **changes}
                self.rejects(self.load, code="invalid_panel")

    def test_semantic_signature_cannot_create_an_extra_family_from_a_translation(self):
        self.cases["cases"][0]["family_id"] = "RenamedButNotNewSemantics"
        self.rejects(self.load, code="invalid_panel")

    def test_family_meaning_cannot_change_through_a_different_oracle_revision(self):
        revised = copy.deepcopy(self.oracles["oracles"][0])
        revised.update(oracle_id="E01_overview.v2", revision=2)
        self.oracles["oracles"].append(revised)
        self.cases["cases"][0]["oracle_id"] = revised["oracle_id"]
        self.assertEqual(len(self.load().oracles), 10)
        revised["values"]["amount"] += 1
        self.rejects(self.load, code="invalid_panel")

    def test_clarification_codes_are_literal_question_bindings_not_guessed_aliases(self):
        original = self.cases["cases"][11]["question"]
        for question in ("CTR-A01 only in March 2026", "ctr-a01 ctr-b01 in March 2026",
                         "CTR-A010 CTR-B010 in March 2026"):
            self.cases["cases"][11]["question"] = question
            self.rejects(self.load, code="invalid_panel")
        self.cases["cases"][11]["question"] = original
        self.assertEqual(len(self.load().cases), 15)

    def test_every_oracle_branch_has_closed_fields_and_positive_integer_revision(self):
        for original in self.oracles["oracles"]:
            for field in original:
                candidate = copy.deepcopy(original)
                del candidate[field]
                with self.subTest(oracle=original["oracle_id"], missing=field):
                    self.rejects(p3_assets.parse_oracle, candidate)
            self.rejects(p3_assets.parse_oracle, {**original, "unexpected": "PRIVATE_ASSET_CANARY"})
            for revision in (0, -1, True, 1.0, "1", None):
                self.rejects(p3_assets.parse_oracle, {**original, "revision": revision})
            first = p3_assets.parse_oracle(original)
            revised = p3_assets.parse_oracle({**original, "revision": 2})
            self.assertEqual(revised.revision, 2)
            self.assertEqual(first.meaning, revised.meaning)
            self.assertNotEqual(first.to_dict(), revised.to_dict())
        for invalid in ([], None, False, {"branch": "synthesis"}):
            self.rejects(p3_assets.parse_oracle, invalid)

    def test_oracle_metadata_provenance_and_identity_types_reject(self):
        original = self.oracles["oracles"][0]
        for field, values in (
            ("oracle_id", (None, "", 1, "bad id")),
            ("provenance", (None, [], "source", [1], ["source", "source"])),
            ("branch", (None, [], "request", "declined")),
            ("recipe_id", (None, [], "sql")),
            ("recipe_version", (None, 0.1, "0.2")),
            ("catalog_sha256", (None, "0" * 64, "9027")),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.rejects(p3_assets.parse_oracle, {**original, field: value})

    def test_native_request_validation_rejects_invalid_periods_metrics_scopes_and_top_k(self):
        for index, path, value in (
            (0, ("request", "start"), "2026-03-02T00:00:00+08:00"),
            (0, ("request", "end"), "2026-05-01T00:00:00+08:00"),
            (0, ("request", "timezone"), "UTC"),
            (0, ("request", "center_code"), ""),
            (0, ("request", "extra"), "PRIVATE_ASSET_CANARY"),
            (1, ("request", "current", "metrics"), ["booked_seats"]),
            (1, ("request", "baseline", "center_id"), "CA"),
            (1, ("request", "baseline", "start"), "not-a-date"),
            (2, ("request", "top_k"), True),
            (2, ("request", "top_k"), 2.0),
            (2, ("request", "top_k"), 4),
            (2, ("request", "center_id"), "CA"),
        ):
            with self.subTest(index=index, path=path, value=value):
                candidate = copy.deepcopy(self.oracles["oracles"][index])
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.rejects(p3_assets.parse_oracle, candidate, code="invalid_oracle")

    def test_native_canonicalization_accepts_equivalent_instants_but_preserves_roles_and_code(self):
        for original in self.oracles["oracles"][:3]:
            candidate = copy.deepcopy(original)
            scopes = (candidate["request"].values() if candidate["recipe_id"] == "compare"
                      else [candidate["request"]])
            conversion = {
                "2026-02-01T00:00:00+08:00": "2026-01-31T16:00:00Z",
                "2026-03-01T00:00:00+08:00": "2026-02-28T16:00:00Z",
                "2026-04-01T00:00:00+08:00": "2026-03-31T16:00:00Z",
            }
            for scope in scopes:
                for key in ("start", "end"):
                    scope[key] = conversion[scope[key]]
            self.assertEqual(p3_assets.parse_oracle(original).meaning,
                             p3_assets.parse_oracle(candidate).meaning)
        overview = copy.deepcopy(self.oracles["oracles"][0])
        overview["request"]["center_code"] = "ctr-a01"
        self.assertNotEqual(p3_assets.parse_oracle(overview).meaning,
                            p3_assets.parse_oracle(self.oracles["oracles"][0]).meaning)
        compare = copy.deepcopy(self.oracles["oracles"][1])
        request = compare["request"]
        request["current"], request["baseline"] = request["baseline"], request["current"]
        self.assertNotEqual(p3_assets.parse_oracle(compare).meaning,
                            p3_assets.parse_oracle(self.oracles["oracles"][1]).meaning)

    def test_coverage_roles_states_units_and_required_auxiliary_partition_are_closed(self):
        original = self.oracles["oracles"][0]
        for field, value in (
            ("required_slots", []), ("required_slots", ["amount", "amount", "bookings", "seats"]),
            ("auxiliary_slots", ["daily_amount"]), ("auxiliary_slots", ["amount", "daily_amount", "category_amounts"]),
            ("slot_states", {**original["slot_states"], "amount": True}),
            ("slot_states", {**original["slot_states"], "amount": "complete"}),
            ("slot_states", {"amount": "checked"}),
            ("units", {**original["units"], "amount": ""}),
            ("units", {**original["units"], "amount": 100}),
            ("units", {"amount": "TWD_minor"}), ("auxiliary_values", {}),
        ):
            with self.subTest(field=field, value=value):
                self.rejects(p3_assets.parse_oracle, {**original, field: value})
        for changes in (
            {"status": "checked"}, {"states": []}, {"states": ["unknown"]}, {"states": True},
            {"binding_center_id": ""}, {"extra": "PRIVATE_ASSET_CANARY"},
            {"slots": {**original["coverage"]["slots"], "daily_amount": "required"}},
        ):
            self.rejects(p3_assets.parse_oracle,
                         {**original, "coverage": {**original["coverage"], **changes}})
        candidate = copy.deepcopy(self.oracles["oracles"][2])
        candidate["coverage"]["group"]["top_k"] = 3
        self.rejects(p3_assets.parse_oracle, candidate)

    def test_group_coverage_top_k_does_not_accept_float_or_bool_equality(self):
        for request_k, coverage_k in ((2, 2.0), (1, True)):
            with self.subTest(request_k=request_k, coverage_k=coverage_k):
                candidate = copy.deepcopy(self.oracles["oracles"][2])
                candidate["request"]["top_k"] = request_k
                candidate["coverage"]["group"]["top_k"] = request_k
                if request_k == 1:
                    candidate["values"]["rows"] = candidate["values"]["rows"][:1]
                    candidate["values"]["top_subtotal"] = 68000
                    candidate["values"]["share"] = {"numerator": 34, "denominator": 79}
                p3_assets.parse_oracle(candidate)
                candidate["coverage"]["group"]["top_k"] = coverage_k
                self.rejects(p3_assets.parse_oracle, candidate)

    def test_values_reject_boolean_float_overflow_and_noncanonical_rationals(self):
        original = self.oracles["oracles"][1]
        for key, value in (
            ("current", True), ("baseline", 50000.0), ("delta", 2**63),
            ("delta", -(2**63) - 1), ("growth", 2.16), ("growth", True),
            ("growth", {"numerator": 108, "denominator": 50}),
            ("growth", {"numerator": 54, "denominator": 0}),
            ("growth", {"numerator": 54, "denominator": -25}),
            ("growth", {"numerator": True, "denominator": 25}),
            ("growth", {"numerator": 54, "denominator": 25.0}),
            ("growth", {"numerator": 54, "denominator": 25, "extra": 1}),
        ):
            self.rejects(p3_assets.parse_oracle, {
                **original, "values": {**original["values"], key: value},
            })
        for value in (0, -(2**63), 2**63 - 1, None):
            parsed = p3_assets.parse_oracle({
                **original, "values": {**original["values"], "delta": value},
            })
            self.assertEqual(parsed.to_dict()["values"]["delta"], value)
        unavailable = copy.deepcopy(original)
        unavailable["values"]["growth"] = None
        unavailable["slot_states"]["growth"] = "undefined"
        self.assertIsNone(p3_assets.parse_oracle(unavailable).to_dict()["values"]["growth"])

    def test_rows_have_closed_unique_keys_bounded_exact_values_and_explicit_null(self):
        original = self.oracles["oracles"][2]
        for rows in (
            None, {}, [{"key": "K1"}], [{"key": "K1", "value": 1, "extra": 1}],
            [{"key": "K1", "value": True}], [{"key": "K1", "value": 1.0}],
            [{"key": "K1", "value": -1}], [{"key": "K1", "value": 2**63}],
            [{"key": 1, "value": 1}], [{"key": "", "value": 1}],
            [{"key": "K1", "value": 1}, {"key": "K1", "value": 2}],
            [{"key": None, "value": 1}, {"key": None, "value": 2}],
            [{"key": f"K{i}", "value": i} for i in range(201)],
        ):
            self.rejects(p3_assets.parse_oracle, {
                **original, "values": {**original["values"], "rows": rows},
            })
        category = copy.deepcopy(self.oracles["oracles"][0])
        category["auxiliary_values"]["category_amounts"] = [{"key": None, "value": 0}]
        parsed = p3_assets.parse_oracle(category)
        self.assertEqual(parsed.to_dict()["auxiliary_values"]["category_amounts"],
                         [{"key": None, "value": 0}])
        self.assertNotEqual(parsed.meaning, p3_assets.parse_oracle(self.oracles["oracles"][0]).meaning)

    def test_clarification_oracles_reuse_closed_types_and_cross_choice_invariants(self):
        original = self.oracles["oracles"][3]
        for changes in (
            {"kind": "time_scope"}, {"choices": []}, {"extra": "PRIVATE_ASSET_CANARY"},
        ):
            self.rejects(p3_assets.parse_oracle, {
                **original, "clarification": {**original["clarification"], **changes},
            })
        for change in ("duplicate_id", "duplicate_semantics", "different_scope", "unknown_value",
                       "model_label"):
            candidate = copy.deepcopy(original)
            choices = candidate["clarification"]["choices"]
            if change == "duplicate_id":
                choices[1]["id"] = choices[0]["id"]
            elif change == "duplicate_semantics":
                choices[1]["semantic_value"] = copy.deepcopy(choices[0]["semantic_value"])
            elif change == "different_scope":
                choices[1]["semantic_value"]["scope"]["center_code"] = "CTR-B01"
            elif change == "unknown_value":
                choices[1]["semantic_value"]["value"] = "arbitrary_people_metric"
            else:
                choices[0]["label"] = "PRIVATE_ASSET_CANARY"
            self.rejects(p3_assets.parse_oracle, candidate)
        roles = copy.deepcopy(self.oracles["oracles"][4])
        roles["clarification"]["choices"][1]["semantic_value"]["request"] = copy.deepcopy(
            roles["clarification"]["choices"][0]["semantic_value"]["request"])
        self.rejects(p3_assets.parse_oracle, roles)

    def test_decline_oracles_need_no_reason_and_deferred_d05_cannot_be_correct_control(self):
        for original in self.oracles["oracles"][-2:]:
            parsed = p3_assets.parse_oracle(original)
            self.assertTrue(parsed.designated_control)
            self.assertNotIn("reason", parsed.to_dict())
            for field in ("reason", "expected_reason", "reason_pattern"):
                self.rejects(p3_assets.parse_oracle, {**original, field: "PRIVATE_ASSET_CANARY"})
            for category in ("D05", "P21", "D00", "profit", None, []):
                self.rejects(p3_assets.parse_oracle, {**original, "capability_category": category})
            for control in (1, "true", None):
                self.rejects(p3_assets.parse_oracle, {**original, "designated_control": control})
        deferred = {**self.oracles["oracles"][-1], "capability_category": "D05",
                    "designated_control": False}
        self.assertFalse(p3_assets.parse_oracle(deferred).designated_control)
        self.oracles["oracles"][-1] = deferred
        self.rejects(self.load, code="invalid_panel")

    def test_non_designated_decline_is_not_a_scored_control_even_in_known_category(self):
        self.oracles["oracles"][-1]["designated_control"] = False
        self.rejects(self.load, code="invalid_panel")

    def test_asset_paths_reject_traversal_absolute_paths_and_wrong_suffix(self):
        for field in ("cases", "oracles"):
            original = self.panel[field]
            for path in ("../outside.json", "nested/asset.json", "/outside.json",
                         ".", "..", "asset.txt", "", None, []):
                with self.subTest(field=field, path=path):
                    self.panel[field] = path
                    self.rejects(self.load)
            self.panel[field] = original

    def test_embedded_null_in_path_rejects_with_fixed_error(self):
        self.panel["cases"] = "PRIVATE_ASSET_CANARY\u0000.json"
        self.rejects(self.load)

    def test_symlink_assets_panels_and_ancestor_directories_are_rejected(self):
        panel_path = self.write_panel()
        linked_panel = self.directory / "linked-panel.json"
        linked_panel.symlink_to(panel_path)
        self.rejects(p3_assets.load_panel, linked_panel)
        for key in ("cases", "oracles"):
            target = self.directory / self.panel[key]
            link = self.directory / f"linked-{key}.json"
            link.symlink_to(target)
            original = self.panel[key]
            self.panel[key] = link.name
            self.rejects(self.load)
            self.panel[key] = original
        self.write_panel()
        link_directory = self.directory / "linked-directory"
        link_directory.symlink_to(self.directory, target_is_directory=True)
        self.rejects(p3_assets.load_panel, link_directory / "panel.json")
        dangling = self.directory / "dangling.json"
        dangling.symlink_to(self.directory / "missing.json")
        self.rejects(p3_assets.read_asset, dangling)

    def test_missing_directory_and_io_failures_are_sanitized(self):
        self.rejects(p3_assets.read_asset, self.directory / "missing.json")
        self.rejects(p3_assets.read_asset, self.directory)
        with patch.object(Path, "open", side_effect=OSError("PRIVATE_ASSET_CANARY")):
            self.rejects(p3_assets.read_asset, self.directory / "unreadable.json")

    def test_asset_byte_limit_has_an_exact_boundary(self):
        path = self.directory / "bounded.json"
        path.write_bytes(b"{}" + b" " * (p3_assets.MAX_ASSET_BYTES - 2))
        self.assertEqual(p3_assets.read_asset(path), {})
        with path.open("ab") as stream:
            stream.write(b" ")
        self.rejects(p3_assets.read_asset, path)

    def test_malformed_json_utf8_duplicate_keys_nonfinite_and_nonobject_roots_reject(self):
        path = self.directory / "malformed.json"
        for payload in (
            b"", b"{", b"{}{}", b"```json\n{}\n```", b"\xff", b'{"x":NaN}',
            b'{"x":Infinity}', b'{"x":"\\ud800"}', b'{"x":1,"x":2}',
            b'{"nested":{"x":1,"x":2}}', b"[]", b"null", b"true", b"123", b'"text"',
        ):
            with self.subTest(payload=payload):
                path.write_bytes(payload)
                self.rejects(p3_assets.read_asset, path, code="invalid_asset")

    def test_duplicate_keys_in_each_loader_surface_are_not_silently_overwritten(self):
        for filename in ("panel.json", "development-cases-v1.json", "development-oracles-v1.json"):
            panel_path = self.write_panel()
            path = self.directory / filename
            raw = path.read_text()
            path.write_text('{"version":"PRIVATE_ASSET_CANARY",' + raw[1:])
            self.rejects(p3_assets.load_panel, panel_path, code="invalid_asset")

    def test_returned_cases_panel_and_metadata_are_immutable_snapshots(self):
        panel = self.load()
        case = panel.cases[0]
        for item, field, value in (
            (panel, "cases", ()), (case, "question", "changed"),
            (case.provenance, "references", ()),
        ):
            with self.assertRaises(FrozenInstanceError):
                setattr(item, field, value)
        self.assertIsInstance(panel.cases, tuple)
        self.assertIsInstance(panel.oracles, tuple)
        self.assertIsInstance(case.provenance.references, tuple)
        self.cases["cases"][0]["provenance"]["references"].append("changed")
        self.cases["cases"][0]["question"] = "changed"
        self.assertNotIn("changed", case.provenance.references)
        metadata = panel.inputs()
        self.assertNotIn("question", metadata[0])
        self.assertEqual(metadata[0]["question_sha256"],
                         hashlib.sha256(case.question.encode()).hexdigest())
        self.assertEqual(metadata[0]["order"], 1)
        self.assertEqual(metadata[0]["question_reference"],
                         {"asset": "development-cases-v1.json", "case_id": case.case_id, "field": "question"})
        metadata[0]["provenance"]["references"].clear()
        metadata[0]["question_reference"]["field"] = "changed"
        self.assertTrue(panel.inputs()[0]["provenance"]["references"])
        self.assertEqual(panel.inputs()[0]["question_reference"]["field"], "question")

    def test_returned_oracles_and_native_semantics_do_not_alias_input_or_exported_mappings(self):
        for original in self.oracles["oracles"]:
            candidate = copy.deepcopy(original)
            parsed = p3_assets.parse_oracle(candidate)
            before = parsed.to_dict()
            meaning = parsed.meaning
            candidate["provenance"].clear()
            exported = parsed.to_dict()
            exported["provenance"].clear()
            with self.assertRaises(FrozenInstanceError):
                parsed.revision = 99
            if isinstance(parsed, p3_assets.AnswerOracle):
                candidate["values"].clear()
                exported["request"].clear()
                meaning["values"].clear()
                with self.assertRaises(FrozenInstanceError):
                    parsed.request.timezone = "changed"
            elif isinstance(parsed, p3_assets.ClarifyOracle):
                candidate["clarification"]["choices"].clear()
                exported["clarification"]["choices"].clear()
                meaning["clarification"]["alternatives"].clear()
                with self.assertRaises(FrozenInstanceError):
                    parsed.clarification.kind = "changed"
                self.assertIsInstance(parsed.clarification.choices, tuple)
            self.assertEqual(parsed.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
