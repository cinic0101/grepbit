"""Offline admission controls, not fresh content or a human novelty certificate.

Proposed-fresh fixtures are metadata only. Native intake fixtures use only the
already exposed development assets; no formal panel is created or executed.
"""

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import copy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from grepbit import recipe_model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL
from tools import (
    fixture, p3_admission as admission, p3_assets as assets, p3_eval as runner,
    p3_expectations, p3_scoring, recipe_smoke, smoke,
)
from test_p3_scoring import formal_scaffolding, metadata as allocation_metadata
from test_structured_output import GENERATION, QUESTION as EXPOSED_WIRE_WITNESS


ROOT = Path(__file__).resolve().parent.parent
DEVELOPMENT = ROOT / "evals/p3"
FROZEN_BASELINE = "20abb5592262c77c98f9cabeaf7cf4854edb6fbe"
DECLARED_AT = "2026-09-21T06:32:04Z"
AUTHORED_AT = "2026-09-21T06:33:00Z"
REVIEWED_AT = "2026-09-21T06:34:00Z"
NOW = datetime(2026, 9, 21, 7, tzinfo=timezone.utc)
OWNER_REFERENCE = "synthetic-metadata-only:owner:no-real-submission"
CHECKLIST = (
    "distinct_requirements", "not_paraphrase_or_translation", "not_parameter_only",
    "supported_frozen_capability", "independent_gold", "ancestry_reviewed", "language_equivalence",
)
PROTECTED_TOOLS = (
    "tools/p3_assets.py", "tools/p3_grading.py", "tools/p3_scoring.py",
    "tools/p3_expectations.py", "tools/recipe_smoke.py", "tools/smoke.py",
    "tools/evaluation_evidence.py", "requirements.txt",
)
SYNTHETIC_TOOLING_COMMIT = "1" * 40
SYNTHETIC_DATABASE_SHA256 = "d" * 64


def metadata_provenance(exposure):
    return {
        "origin": {
            "frozen_fresh": "independent", "design_seen": "development",
            "exposed_regression": "historical",
        }[exposure],
        "references": ["synthetic-metadata-only:no-case-asset"],
        "seen_by_implementer": exposure != "frozen_fresh",
        "exposure_history": [exposure],
    }


def abstract_inputs(family="SyntheticReviewA", languages=("en",), *,
                    exposure="frozen_fresh", start=1):
    rows = allocation_metadata(family, languages, exposure=exposure, start=start)
    for row in rows:
        row["provenance"] = metadata_provenance(exposure)
    return rows


def abstract_reviews(inputs):
    groups = {}
    for row in inputs:
        groups.setdefault(row["family_id"], []).append(row)
    return [{
        "family_id": family,
        "case_ids": [row["case_id"] for row in variants],
        "author": {
            "role": "independent_author" if variants[0]["exposure"] == "frozen_fresh"
                    else "historical_curator",
            "reference": "synthetic-metadata-only:author",
        },
        "reviewer": {
            "role": "independent_reviewer", "reference": "synthetic-metadata-only:reviewer",
        },
        "authored_at": AUTHORED_AT,
        "reviewed_at": REVIEWED_AT,
        "ancestry": ["synthetic-metadata-only:no-ancestry-claim"],
        "novelty_rationale": "Synthetic assertions only; no question, gold or human novelty claim.",
        "reviewed_signature": f"synthetic-parameter-independent-bundle:{family}",
        "checklist": dict.fromkeys(CHECKLIST, True),
        "implementer_visible_before_run": variants[0]["provenance"]["seen_by_implementer"],
    } for family, variants in groups.items()]


class AdmissionAssertions(unittest.TestCase):
    def setUp(self):
        for target in (
            "socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
            "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
            "grepbit.gateway.GatewayConfig.from_env", "grepbit.gateway.GatewayClient.complete",
            "sqlite3.connect",
            "grepbit.model.interpret_and_execute", "grepbit.recipe_model.interpret_recipe_and_execute",
            "tools.smoke.interpret_and_execute", "tools.recipe_smoke.interpret_recipe_and_execute",
            "tools.p3_eval.interpret_recipe_and_execute",
            "grepbit.execute_facts", "grepbit.execute_grouped_amount", "grepbit.execute_overview",
            "grepbit.execute_compare", "grepbit.execute_breakdown",
            "grepbit.kernel.execute_facts", "grepbit.grouped.execute_grouped_amount",
            "grepbit.overview.execute_overview", "grepbit.compare.execute_compare",
            "grepbit.breakdown.execute_breakdown", "grepbit.model.execute_facts",
            "grepbit.recipe_model.execute_overview", "grepbit.recipe_model.execute_compare",
            "grepbit.recipe_model.execute_breakdown",
        ):
            self.poison(target)
        temporary = tempfile.TemporaryDirectory(prefix="p33-admission-", dir=ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()

    def poison(self, target):
        guard = patch(target, side_effect=AssertionError("Admission must be pure and offline"))
        mocked = guard.start()
        self.addCleanup(guard.stop)
        self.addCleanup(mocked.assert_not_called)

    def rejects(self, function, *args, code, **kwargs):
        with self.assertRaises(assets.P3Error) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)

    def write_json(self, path, document):
        path.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def cli(self, function, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = function(arguments)
        return result, stdout.getvalue(), stderr.getvalue()


class P3ReviewMetadataTests(AdmissionAssertions):
    def setUp(self):
        super().setUp()
        self.poison("tools.p3_admission.subprocess.run")
        self.inputs = abstract_inputs(languages=assets.LANGUAGES)
        self.reviews = abstract_reviews(self.inputs)

    def validate(self, **options):
        arguments = {
            "state": "novelty_reviewed", "candidate_freeze_sha": FROZEN_BASELINE,
            "owner_review_reference": OWNER_REFERENCE, "now": NOW,
        }
        arguments.update(options)
        return admission.validate_review_metadata(self.inputs, self.reviews, **arguments)

    def test_declared_baseline_and_v1_review_contract_are_exact(self):
        self.assertEqual(admission.FROZEN_CANDIDATE, FROZEN_BASELINE)
        self.assertEqual(admission.FREEZE_DECLARED_AT, DECLARED_AT)
        self.assertEqual(admission.INTAKE_VERSION, "p3-intake-v1")
        self.assertEqual(admission.CHECKLIST, CHECKLIST)

    def test_complete_metadata_assertions_do_not_certify_novelty_or_create_assets(self):
        before = copy.deepcopy((self.inputs, self.reviews))
        result = self.validate()
        self.assertEqual(result, {
            "state": "novelty_reviewed", "family_count": 1, "input_count": 3,
            "proposed_fresh_families": 1, "eligible_for_fresh_review": True,
            "review_assertions_complete": True,
            "semantic_novelty": "requires_independent_reviewer_and_owner_acceptance",
        })
        self.assertEqual((self.inputs, self.reviews), before)
        for row in self.inputs:
            self.assertTrue({"question", "gold", "request", "values"}.isdisjoint(row))
            self.assertIsNone(row["question_reference"]["asset"])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_exact_freeze_sha_cannot_be_missing_shortened_or_substituted(self):
        for sha in (None, "", FROZEN_BASELINE[:8], FROZEN_BASELINE.upper(),
                    "f" * 40, "a" * 64, 20, [], {}):
            with self.subTest(sha=sha):
                self.rejects(self.validate, candidate_freeze_sha=sha, code="invalid_panel")

    def test_intake_states_are_not_a_configurable_workflow(self):
        for state in (None, "", "frozen", "approved", "formal", [], 1):
            with self.subTest(state=state):
                self.rejects(self.validate, state=state, code="invalid_panel")
        self.assertEqual(self.validate(state="draft")["state"], "draft")

    def test_metadata_and_review_lists_are_nonempty_and_bounded(self):
        for field in ("inputs", "reviews"):
            original = getattr(self, field)
            for value in (None, {}, (), [], original * (assets.MAX_INPUTS + 1)):
                with self.subTest(field=field, kind=type(value).__name__):
                    setattr(self, field, value)
                    self.rejects(self.validate, code="invalid_panel")
            setattr(self, field, original)

    def test_draft_can_record_incomplete_assertions_without_becoming_reviewed(self):
        self.reviews[0]["reviewed_at"] = None
        self.reviews[0]["checklist"] = dict.fromkeys(CHECKLIST, False)
        result = self.validate(state="draft", owner_review_reference=None)
        self.assertEqual(result["state"], "draft")
        self.assertFalse(result["review_assertions_complete"])
        self.assertFalse(result["eligible_for_fresh_review"])
        self.assertEqual(result["semantic_novelty"],
                         "requires_independent_reviewer_and_owner_acceptance")
        self.rejects(self.validate, code="formal_not_admitted")

    def test_reviewed_state_requires_owner_reference_even_with_complete_checklist(self):
        self.rejects(self.validate, owner_review_reference=None, code="formal_not_admitted")
        result = self.validate(state="draft", owner_review_reference=None)
        self.assertFalse(result["review_assertions_complete"])

    def test_owner_reference_is_bounded_text_not_a_truthy_placeholder(self):
        for reference in ("", " \t\n", 1, True, [], {}, "x" * 513):
            with self.subTest(reference=reference):
                self.rejects(self.validate, owner_review_reference=reference, code="invalid_asset")

    def test_reviewed_state_requires_a_review_timestamp(self):
        self.reviews[0]["reviewed_at"] = None
        self.rejects(self.validate, code="formal_not_admitted")

    def test_fresh_authoring_must_be_strictly_after_owner_declaration(self):
        for timestamp in ("2026-09-21T06:32:03Z", DECLARED_AT):
            with self.subTest(timestamp=timestamp):
                self.reviews[0]["authored_at"] = timestamp
                self.rejects(self.validate, code="formal_not_admitted")
        self.reviews[0]["authored_at"] = "2026-09-21T06:32:04.000001Z"
        self.assertTrue(self.validate()["review_assertions_complete"])

    def test_historical_exposed_authoring_may_precede_the_freeze(self):
        self.inputs = abstract_inputs(exposure="exposed_regression")
        self.reviews = abstract_reviews(self.inputs)
        self.reviews[0]["authored_at"] = "2026-09-01T00:00:00Z"
        self.reviews[0]["reviewed_at"] = "2026-09-02T00:00:00Z"
        result = self.validate()
        self.assertEqual(result["proposed_fresh_families"], 0)
        self.assertTrue(result["review_assertions_complete"])

    def test_future_authoring_and_future_or_reversed_review_are_rejected(self):
        for authored, reviewed in (
            ("2026-09-21T07:00:01Z", None),
            (AUTHORED_AT, "2026-09-21T07:00:01Z"),
            (AUTHORED_AT, DECLARED_AT),
        ):
            with self.subTest(authored=authored, reviewed=reviewed):
                self.reviews[0].update(authored_at=authored, reviewed_at=reviewed)
                self.rejects(self.validate, state="draft", code="invalid_asset")

    def test_review_order_allows_equal_authoring_and_review_up_to_now(self):
        for timestamp in (AUTHORED_AT, "2026-09-21T07:00:00Z"):
            with self.subTest(timestamp=timestamp):
                self.reviews[0].update(authored_at=timestamp, reviewed_at=timestamp)
                self.assertTrue(self.validate()["review_assertions_complete"])

    def test_timestamps_require_parseable_utc_z_text(self):
        original = copy.deepcopy(self.reviews)
        for field in ("authored_at", "reviewed_at"):
            for value in ("", "not-a-dateZ", "2026-02-30T00:00:00Z",
                          "2026-09-21T06:33:00", "2026-09-21T06:33:00+00:00",
                          "2026-09-21T06:33:00z", 1, [], {}):
                with self.subTest(field=field, value=value):
                    self.reviews = copy.deepcopy(original)
                    self.reviews[0][field] = value
                    self.rejects(self.validate, code="invalid_asset")
        self.reviews = copy.deepcopy(original)
        self.reviews[0]["authored_at"] = None
        self.rejects(self.validate, code="invalid_asset")

    def test_review_record_fields_are_required_and_closed(self):
        original = copy.deepcopy(self.reviews[0])
        for field in original:
            with self.subTest(missing=field):
                self.reviews = [copy.deepcopy(original)]
                del self.reviews[0][field]
                self.rejects(self.validate, code="invalid_asset")
        for value in (None, [], {**original, "unknown": "SYNTHETIC_PRIVATE_METADATA_CANARY"}):
            self.reviews = [value]
            self.rejects(self.validate, code="invalid_asset")

    def test_author_and_reviewer_roles_are_explicit_and_not_interchangeable(self):
        original = copy.deepcopy(self.reviews)
        for field, roles in (
            ("author", ("independent_reviewer", "owner", "", None, [])),
            ("reviewer", ("independent_author", "historical_curator",
                          "implementation_author", "owner", "", None, [])),
        ):
            for role in roles:
                with self.subTest(field=field, role=role):
                    self.reviews = copy.deepcopy(original)
                    self.reviews[0][field]["role"] = role
                    self.rejects(self.validate, code="invalid_asset")

    def test_fresh_requires_independent_author_not_curator_or_implementation_author(self):
        for role in ("historical_curator", "implementation_author"):
            with self.subTest(role=role):
                self.reviews[0]["author"]["role"] = role
                self.rejects(self.validate, code="formal_not_admitted")

    def test_exposed_records_can_truthfully_identify_each_permitted_author_role(self):
        self.inputs = abstract_inputs(exposure="exposed_regression")
        self.reviews = abstract_reviews(self.inputs)
        for role in ("independent_author", "historical_curator", "implementation_author"):
            with self.subTest(role=role):
                self.reviews[0]["author"]["role"] = role
                self.assertEqual(self.validate()["proposed_fresh_families"], 0)

    def test_actor_references_are_required_bounded_and_have_no_extra_fields(self):
        original = copy.deepcopy(self.reviews)
        for field in ("author", "reviewer"):
            for reference in (None, "", " \t\n", 1, True, [], {}, "x" * 257):
                with self.subTest(field=field, reference=reference):
                    self.reviews = copy.deepcopy(original)
                    self.reviews[0][field]["reference"] = reference
                    self.rejects(self.validate, code="invalid_asset")
            for missing in ("role", "reference"):
                with self.subTest(field=field, missing=missing):
                    self.reviews = copy.deepcopy(original)
                    del self.reviews[0][field][missing]
                    self.rejects(self.validate, code="invalid_asset")
            self.reviews = copy.deepcopy(original)
            self.reviews[0][field]["extra"] = True
            self.rejects(self.validate, code="invalid_asset")

    def test_author_cannot_review_their_own_submission_by_changing_role(self):
        self.reviews[0]["reviewer"]["reference"] = self.reviews[0]["author"]["reference"]
        self.rejects(self.validate, code="invalid_asset")

    def test_ancestry_requires_nonempty_unique_bounded_references(self):
        for ancestry in (None, "", [], [" \t\n"], ["same", "same"], [1],
                         [f"synthetic-{index}" for index in range(17)]):
            with self.subTest(ancestry=ancestry):
                self.reviews[0]["ancestry"] = ancestry
                self.rejects(self.validate, code="invalid_asset")

    def test_reviewed_signature_and_rationale_require_bounded_text(self):
        original = copy.deepcopy(self.reviews)
        for field, maximum in (("reviewed_signature", 1024), ("novelty_rationale", 2048)):
            for value in (None, "", " \t\n", 1, [], {}, "x" * (maximum + 1)):
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.reviews = copy.deepcopy(original)
                    self.reviews[0][field] = value
                    self.rejects(self.validate, code="invalid_asset")

    def test_parameter_independent_reviewed_signature_rejects_distinct_family_padding(self):
        self.inputs += abstract_inputs("SyntheticReviewB", start=4)
        self.reviews = abstract_reviews(self.inputs)
        self.assertNotEqual(self.inputs[0]["semantic_signature"], self.inputs[-1]["semantic_signature"])
        self.reviews[1]["reviewed_signature"] = self.reviews[0]["reviewed_signature"]
        self.rejects(self.validate, code="invalid_panel")

    def test_duplicate_declared_signatures_cannot_hide_behind_distinct_reviewed_signatures(self):
        self.inputs += abstract_inputs("SyntheticReviewB", start=4)
        self.reviews = abstract_reviews(self.inputs)
        self.inputs[-1]["semantic_signature"] = self.inputs[0]["semantic_signature"]
        self.assertNotEqual(self.reviews[0]["reviewed_signature"], self.reviews[1]["reviewed_signature"])
        self.rejects(self.validate, code="invalid_panel")

    def test_reviewed_checklist_rejects_parameter_paraphrase_unsupported_and_derived_gold_claims(self):
        for flag in CHECKLIST:
            with self.subTest(flag=flag):
                self.reviews = abstract_reviews(self.inputs)
                self.reviews[0]["checklist"][flag] = False
                self.rejects(self.validate, code="formal_not_admitted")

    def test_checklist_flags_are_all_required_closed_and_exact_booleans(self):
        for flag in CHECKLIST:
            for value in (None, 0, 1, "true", [], {}):
                with self.subTest(flag=flag, value=value):
                    self.reviews = abstract_reviews(self.inputs)
                    self.reviews[0]["checklist"][flag] = value
                    self.rejects(self.validate, code="invalid_asset")
            self.reviews = abstract_reviews(self.inputs)
            del self.reviews[0]["checklist"][flag]
            self.rejects(self.validate, code="invalid_asset")
        self.reviews = abstract_reviews(self.inputs)
        self.reviews[0]["checklist"]["extra"] = True
        self.rejects(self.validate, code="invalid_asset")

    def test_implementer_visibility_is_an_exact_boolean_and_matches_every_variant(self):
        for value in (None, 0, 1, "false", [], {}):
            with self.subTest(value=value):
                self.reviews[0]["implementer_visible_before_run"] = value
                self.rejects(self.validate, code="invalid_asset")
        self.inputs = abstract_inputs(languages=assets.LANGUAGES, exposure="exposed_regression")
        self.reviews = abstract_reviews(self.inputs)
        self.inputs[-1]["provenance"]["seen_by_implementer"] = False
        self.rejects(self.validate, code="invalid_asset")
        self.inputs[-1]["provenance"]["seen_by_implementer"] = True
        self.reviews[0]["implementer_visible_before_run"] = False
        self.rejects(self.validate, code="invalid_asset")

    def test_fresh_cannot_hide_implementer_visibility_even_with_matching_review(self):
        for row in self.inputs:
            row["provenance"]["seen_by_implementer"] = True
        self.reviews[0]["implementer_visible_before_run"] = True
        self.rejects(self.validate, code="invalid_asset")

    def test_monotonic_exposure_history_accepts_truthful_demotion_without_refreshing(self):
        for history in (
            ["frozen_fresh", "frozen_fresh"],
            ["frozen_fresh", "design_seen"],
            ["frozen_fresh", "design_seen", "exposed_regression", "exposed_regression"],
        ):
            with self.subTest(history=history):
                self.inputs = abstract_inputs(exposure=history[-1])
                self.inputs[0]["provenance"].update(origin="independent", exposure_history=history)
                self.reviews = abstract_reviews(self.inputs)
                result = self.validate(state="draft")
                self.assertEqual(result["proposed_fresh_families"], int(history[-1] == "frozen_fresh"))

    def test_exposure_history_cannot_upgrade_or_hide_an_intermediate_upgrade(self):
        for history in (
            ["design_seen", "frozen_fresh"],
            ["exposed_regression", "frozen_fresh"],
            ["exposed_regression", "design_seen"],
            ["frozen_fresh", "design_seen", "frozen_fresh", "exposed_regression"],
            ["exposed_regression", "design_seen", "exposed_regression"],
        ):
            with self.subTest(history=history):
                self.inputs = abstract_inputs(exposure=history[-1])
                self.inputs[0]["provenance"].update(origin="independent", exposure_history=history)
                self.reviews = abstract_reviews(self.inputs)
                self.rejects(self.validate, state="draft", code="invalid_asset")

    def test_exposure_history_must_end_at_declared_exposure_and_have_known_labels(self):
        for history in ([], ["design_seen"], ["fresh"], ["unknown", "frozen_fresh"]):
            with self.subTest(history=history):
                self.inputs[0]["provenance"]["exposure_history"] = history
                self.rejects(self.validate, code="invalid_asset")
        self.inputs = abstract_inputs()
        self.reviews = abstract_reviews(self.inputs)
        self.inputs[0]["provenance"]["origin"] = "historical"
        self.rejects(self.validate, code="invalid_asset")

    def test_review_case_membership_is_exact_not_order_dependent(self):
        original = self.reviews[0]["case_ids"]
        self.reviews[0]["case_ids"] = list(reversed(original))
        self.assertEqual(self.validate()["input_count"], 3)
        for case_ids in ([], original[:-1], original + ["SyntheticUnknownCase"]):
            with self.subTest(case_ids=case_ids):
                self.reviews[0]["case_ids"] = case_ids
                self.rejects(self.validate, code="invalid_panel")
        self.reviews[0]["case_ids"] = original + [original[0]]
        self.rejects(self.validate, code="invalid_asset")

    def test_every_family_has_exactly_one_review_without_unknown_or_duplicate_families(self):
        self.inputs += abstract_inputs("SyntheticReviewB", start=4)
        original = abstract_reviews(self.inputs)
        for reviews in (original[:1], original + [copy.deepcopy(original[0])]):
            self.reviews = reviews
            self.rejects(self.validate, code="invalid_panel")
        self.reviews = copy.deepcopy(original)
        self.reviews[1]["family_id"] = "SyntheticUnknownFamily"
        self.rejects(self.validate, code="invalid_panel")
        self.reviews = copy.deepcopy(original)
        self.reviews[1]["case_ids"] = self.reviews[0]["case_ids"]
        self.rejects(self.validate, code="invalid_panel")

    def test_family_variants_cannot_mix_exposure(self):
        self.inputs[-1]["exposure"] = "exposed_regression"
        self.inputs[-1]["provenance"] = metadata_provenance("exposed_regression")
        self.rejects(self.validate, code="invalid_panel")

    def test_duplicate_input_ids_cannot_be_hidden_by_set_based_review_membership(self):
        self.inputs.append(copy.deepcopy(self.inputs[0]))
        self.inputs[-1]["order"] = len(self.inputs)
        self.rejects(self.validate, code="invalid_panel")

    def test_input_ids_cannot_belong_to_two_families(self):
        self.inputs += abstract_inputs("SyntheticReviewB", start=4)
        self.inputs[-1]["case_id"] = self.inputs[0]["case_id"]
        self.reviews = abstract_reviews(self.inputs)
        self.rejects(self.validate, code="invalid_panel")

    def test_malformed_input_membership_rejects_with_a_safe_panel_error(self):
        original = copy.deepcopy(self.inputs)
        for field in ("family_id", "case_id"):
            with self.subTest(missing=field):
                self.inputs = copy.deepcopy(original)
                del self.inputs[0][field]
                self.rejects(self.validate, code="invalid_panel")
        for row in (None, [], {}):
            self.inputs = [row]
            self.rejects(self.validate, code="invalid_panel")

    def test_metadata_only_24_family_44_input_proof_reuses_frozen_allocation_validator(self):
        self.inputs = formal_scaffolding()
        for row in self.inputs:
            row["provenance"] = metadata_provenance(row["exposure"])
            self.assertTrue({"question", "gold", "request", "values"}.isdisjoint(row))
            self.assertIsNone(row["question_reference"]["asset"])
        self.reviews = abstract_reviews(self.inputs)
        self.assertIsNone(p3_scoring.validate_formal_allocation(self.inputs))
        result = self.validate()
        self.assertEqual((result["family_count"], result["input_count"],
                          result["proposed_fresh_families"]), (24, 44, 12))
        self.assertEqual(result["semantic_novelty"],
                         "requires_independent_reviewer_and_owner_acceptance")
        self.rejects(self.validate, owner_review_reference=None, code="formal_not_admitted")
        self.assertEqual(list(self.directory.iterdir()), [])


class P3IntakeTests(AdmissionAssertions):
    def setUp(self):
        super().setUp()
        self.poison("tools.p3_admission.subprocess.run")
        self.cases = json.loads((DEVELOPMENT / "development-cases-v1.json").read_bytes())
        self.oracles = json.loads((DEVELOPMENT / "development-oracles-v1.json").read_bytes())
        self.bundle_count = 0

    def write_bundle(self, *, cases=None, oracles=None):
        cases = self.cases if cases is None else cases
        oracles = self.oracles if oracles is None else oracles
        self.bundle_count += 1
        directory = self.directory / f"submission-{self.bundle_count}"
        directory.mkdir()
        intake = {
            "version": "p3-intake-v1", "intake_id": "SyntheticExposedIntake",
            "candidate_freeze_sha": FROZEN_BASELINE, "state": "draft",
            "families": abstract_reviews(cases["cases"]), "owner_review_reference": None,
        }
        for field, document in (("cases", cases), ("oracles", oracles)):
            source = directory / f"development-{field}-v1.json"
            self.write_json(source, document)
            intake[field] = {"reference": source.name,
                             "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        path = directory / "intake.json"
        self.write_json(path, intake)
        return path, intake

    def replace_asset(self, path, intake, field, document):
        source = path.parent / intake[field]["reference"]
        self.write_json(source, document)
        intake[field]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.write_json(path, intake)

    def test_original_exposed_native_intake_audits_without_execution_or_writes(self):
        path, _ = self.write_bundle()
        before = {source.name: source.read_bytes() for source in path.parent.iterdir()}
        result = admission.audit_intake(path)
        self.assertEqual(result, {
            "state": "draft", "family_count": 9, "input_count": 15,
            "proposed_fresh_families": 0, "eligible_for_fresh_review": True,
            "review_assertions_complete": False,
            "semantic_novelty": "requires_independent_reviewer_and_owner_acceptance",
            "intake": {"reference": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "live_model_attempts": 0,
        })
        self.assertEqual({source.name: source.read_bytes() for source in path.parent.iterdir()}, before)
        self.assertTrue(all(row["exposure"] == "exposed_regression" for row in self.cases["cases"]))
        encoded = json.dumps(result, ensure_ascii=False)
        for case in self.cases["cases"]:
            self.assertNotIn(case["question"], encoded)
        self.assertNotIn("novelty_rationale", result)
        self.assertNotIn("oracles", result)

    def test_owner_exposed_projection_supports_draft_intake_not_formal_admission(self):
        cases = json.loads((DEVELOPMENT / "exposed-projection-cases-v1.json").read_bytes())
        oracles = json.loads((DEVELOPMENT / "exposed-projection-oracles-v1.json").read_bytes())
        # Review assertions are synthetic test metadata, not actual independent reviews.
        path, _ = self.write_bundle(cases=cases, oracles=oracles)
        before = {source.name: source.read_bytes() for source in path.parent.iterdir()}
        result = admission.audit_intake(path)
        self.assertEqual((result["state"], result["family_count"], result["input_count"]),
                         ("draft", 9, 15))
        self.assertEqual((result["proposed_fresh_families"], result["live_model_attempts"]), (0, 0))
        self.assertFalse(result["review_assertions_complete"])
        self.assertEqual(result["semantic_novelty"], "requires_independent_reviewer_and_owner_acceptance")
        self.assertEqual({source.name: source.read_bytes() for source in path.parent.iterdir()}, before)

    def test_intake_fields_are_exact_and_freeze_sha_cannot_be_omitted(self):
        _, original = self.write_bundle()
        for field in original:
            with self.subTest(missing=field):
                path, intake = self.write_bundle()
                del intake[field]
                self.write_json(path, intake)
                self.rejects(admission.audit_intake, path, code="invalid_asset")
        path, intake = self.write_bundle()
        intake["extra"] = "SYNTHETIC_PRIVATE_METADATA_CANARY"
        self.write_json(path, intake)
        self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_intake_and_native_versions_must_be_exact_v1(self):
        for version in ("p3-intake-v2", "p3-panel-v1", None, 1, []):
            with self.subTest(intake_version=version):
                path, intake = self.write_bundle()
                intake["version"] = version
                self.write_json(path, intake)
                self.rejects(admission.audit_intake, path, code="invalid_asset")
        for field in ("cases", "oracles"):
            for version in (f"p3-{field}-v2", "p3-intake-v1", None, 1, []):
                with self.subTest(field=field, native_version=version):
                    path, intake = self.write_bundle()
                    document = copy.deepcopy(getattr(self, field))
                    document["version"] = version
                    self.replace_asset(path, intake, field, document)
                    self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_intake_freeze_sha_and_review_state_are_actually_validated(self):
        for changes, code in (
            ({"candidate_freeze_sha": None}, "invalid_panel"),
            ({"candidate_freeze_sha": "f" * 40}, "invalid_panel"),
            ({"state": "frozen"}, "invalid_panel"),
            ({"state": "novelty_reviewed"}, "formal_not_admitted"),
        ):
            with self.subTest(changes=changes):
                path, intake = self.write_bundle()
                intake.update(changes)
                self.write_json(path, intake)
                self.rejects(admission.audit_intake, path, code=code)

    def test_reference_records_are_closed_and_require_name_and_byte_hash(self):
        for field in ("cases", "oracles"):
            for missing in ("reference", "sha256"):
                with self.subTest(field=field, missing=missing):
                    path, intake = self.write_bundle()
                    del intake[field][missing]
                    self.write_json(path, intake)
                    self.rejects(admission.audit_intake, path, code="invalid_asset")
            path, intake = self.write_bundle()
            intake[field]["extra"] = True
            self.write_json(path, intake)
            self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_referenced_sha256_is_lowercase_exact_length_text(self):
        for field in ("cases", "oracles"):
            for sha in (None, 1, [], "", "a" * 63, "a" * 65, "A" * 64, "g" * 64):
                with self.subTest(field=field, sha=sha):
                    path, intake = self.write_bundle()
                    intake[field]["sha256"] = sha
                    self.write_json(path, intake)
                    self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_referenced_hashes_are_bytes_not_canonical_json_meaning(self):
        for field in ("cases", "oracles"):
            with self.subTest(field=field):
                path, intake = self.write_bundle()
                canonical_hash = assets.digest(getattr(self, field))
                self.assertNotEqual(intake[field]["sha256"], canonical_hash)
                intake[field]["sha256"] = canonical_hash
                self.write_json(path, intake)
                self.rejects(admission.audit_intake, path, code="manifest_drift")

    def test_even_nonsemantic_referenced_byte_drift_rejects_a_previously_valid_intake(self):
        for field in ("cases", "oracles"):
            with self.subTest(field=field):
                path, intake = self.write_bundle()
                self.assertEqual(admission.audit_intake(path)["input_count"], 15)
                source = path.parent / intake[field]["reference"]
                with source.open("ab") as stream:
                    stream.write(b"\n")
                self.rejects(admission.audit_intake, path, code="manifest_drift")

    def test_native_documents_and_rows_reject_unknown_fields(self):
        for field in ("cases", "oracles"):
            for level in ("document", "row"):
                with self.subTest(field=field, level=level):
                    path, intake = self.write_bundle()
                    document = copy.deepcopy(getattr(self, field))
                    target = document if level == "document" else document[field][0]
                    target["unknown"] = "SYNTHETIC_PRIVATE_METADATA_CANARY"
                    self.replace_asset(path, intake, field, document)
                    self.rejects(admission.audit_intake, path,
                                 code="invalid_oracle" if field == "oracles" and level == "row"
                                 else "invalid_asset")
        path, intake = self.write_bundle()
        document = copy.deepcopy(self.cases)
        document["cases"][0]["provenance"]["unknown"] = True
        self.replace_asset(path, intake, "cases", document)
        self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_native_asset_arrays_are_required_nonempty_and_bounded(self):
        for field in ("cases", "oracles"):
            for value in (None, {}, [], [getattr(self, field)[field][0]] * (assets.MAX_INPUTS + 1)):
                with self.subTest(field=field, value_type=type(value).__name__):
                    path, intake = self.write_bundle()
                    document = copy.deepcopy(getattr(self, field))
                    document[field] = value
                    self.replace_asset(path, intake, field, document)
                    self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_malformed_and_duplicate_key_json_are_rejected(self):
        for raw in (b"{", b"[]", b'{"version":"p3-intake-v1","version":"p3-intake-v1"}'):
            path, _ = self.write_bundle()
            path.write_bytes(raw)
            self.rejects(admission.audit_intake, path, code="invalid_asset")
        for field in ("cases", "oracles"):
            path, intake = self.write_bundle()
            source = path.parent / intake[field]["reference"]
            source.write_bytes(b'{"version":null,"version":null}')
            intake[field]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            self.write_json(path, intake)
            self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_references_reject_traversal_absolute_paths_and_reserved_output_names(self):
        for field in ("cases", "oracles"):
            for reference in (
                "../development-cases-v1.json", "./development-cases-v1.json",
                "sub/cases.json", "sub\\cases.json", str(self.directory / "cases.json"),
                "cases.json\x00", "cases.txt", "manifest.json", "report.json",
                "terminal-candidate.json", "terminal.next.json", "checkpoint-1.json", ".pending-cases.json",
            ):
                with self.subTest(field=field, reference=reference):
                    path, intake = self.write_bundle()
                    intake[field]["reference"] = reference
                    self.write_json(path, intake)
                    self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_intake_and_two_asset_references_must_be_distinct(self):
        for field in ("cases", "oracles"):
            path, intake = self.write_bundle()
            intake[field]["reference"] = path.name
            self.write_json(path, intake)
            self.rejects(admission.audit_intake, path, code="invalid_asset")
        path, intake = self.write_bundle()
        intake["oracles"] = copy.deepcopy(intake["cases"])
        self.write_json(path, intake)
        self.rejects(admission.audit_intake, path, code="invalid_asset")

    def test_missing_files_and_directory_references_fail_closed(self):
        self.rejects(admission.audit_intake, self.directory / "absent.json", code="invalid_asset")
        for field in ("cases", "oracles"):
            for directory in (False, True):
                with self.subTest(field=field, directory=directory):
                    path, intake = self.write_bundle()
                    source = path.parent / intake[field]["reference"]
                    source.unlink()
                    if directory:
                        source.mkdir()
                    self.rejects(admission.audit_intake, path, code="source_identity_failure")

    def test_symlinked_intake_and_parent_directory_are_rejected(self):
        path, _ = self.write_bundle()
        alias = self.directory / "alias.json"
        alias.symlink_to(path)
        self.rejects(admission.audit_intake, alias, code="invalid_asset")
        parent_alias = self.directory / "linked-parent"
        parent_alias.symlink_to(path.parent, target_is_directory=True)
        self.rejects(admission.audit_intake, parent_alias / path.name, code="invalid_asset")

    def test_symlinked_referenced_assets_are_rejected_even_with_matching_bytes(self):
        for field in ("cases", "oracles"):
            with self.subTest(field=field):
                path, intake = self.write_bundle()
                source = path.parent / intake[field]["reference"]
                target = source.with_name(f"actual-{source.name}")
                source.rename(target)
                source.symlink_to(target.name)
                with self.assertRaises((assets.P3Error, smoke.SmokeError)) as raised:
                    admission.audit_intake(path)
                self.assertEqual(str(raised.exception), "artifact_conflict")

    def test_duplicate_native_case_and_oracle_ids_reject(self):
        for field in ("cases", "oracles"):
            with self.subTest(field=field):
                path, intake = self.write_bundle()
                document = copy.deepcopy(getattr(self, field))
                document[field].append(copy.deepcopy(document[field][0]))
                self.replace_asset(path, intake, field, document)
                self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_case_oracle_membership_rejects_dangling_and_unreferenced_oracles(self):
        path, intake = self.write_bundle()
        cases = copy.deepcopy(self.cases)
        cases["cases"][0]["oracle_id"] = "SyntheticMissingOracle"
        self.replace_asset(path, intake, "cases", cases)
        self.rejects(admission.audit_intake, path, code="invalid_panel")
        path, intake = self.write_bundle()
        cases = copy.deepcopy(self.cases)
        removed_oracle = cases["cases"][0]["oracle_id"]
        cases["cases"] = [row for row in cases["cases"] if row["oracle_id"] != removed_oracle]
        intake["families"] = abstract_reviews(cases["cases"])
        self.replace_asset(path, intake, "cases", cases)
        self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_native_case_and_oracle_branches_must_match(self):
        for branch in ("answer", "clarify", "decline"):
            with self.subTest(branch=branch):
                case = copy.deepcopy(next(row for row in self.cases["cases"]
                                          if row["expected_branch"] == branch))
                oracle = next(row for row in self.oracles["oracles"] if row["branch"] != branch)
                case["oracle_id"] = oracle["oracle_id"]
                path, _ = self.write_bundle(
                    cases={"version": "p3-cases-v1", "cases": [case]},
                    oracles={"version": "p3-oracles-v1", "oracles": [oracle]})
                self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_decline_oracle_must_be_a_designated_control(self):
        path, intake = self.write_bundle()
        oracles = copy.deepcopy(self.oracles)
        oracle = next(row for row in oracles["oracles"] if row["branch"] == "decline")
        oracle["designated_control"] = False
        self.replace_asset(path, intake, "oracles", oracles)
        self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_same_exposed_oracle_meaning_cannot_be_split_under_distinct_family_ids(self):
        for branch in ("answer", "clarify", "decline"):
            for clone_oracle in (False, True):
                with self.subTest(branch=branch, clone_oracle=clone_oracle):
                    original = copy.deepcopy(next(row for row in self.cases["cases"]
                                                  if row["expected_branch"] == branch))
                    duplicate = copy.deepcopy(original)
                    duplicate.update(case_id="SyntheticExposedDuplicate",
                                     family_id="SyntheticExposedDuplicate",
                                     semantic_signature="synthetic-exposed-id-change-only")
                    oracle = copy.deepcopy(next(row for row in self.oracles["oracles"]
                                                if row["oracle_id"] == original["oracle_id"]))
                    oracles = [oracle]
                    if clone_oracle:
                        copied_oracle = copy.deepcopy(oracle)
                        copied_oracle.update(oracle_id="SyntheticExposedDuplicate.v2", revision=2,
                                             provenance=["Synthetic ID-only copy of exposed gold."])
                        duplicate["oracle_id"] = copied_oracle["oracle_id"]
                        oracles.append(copied_oracle)
                    path, _ = self.write_bundle(
                        cases={"version": "p3-cases-v1", "cases": [original, duplicate]},
                        oracles={"version": "p3-oracles-v1", "oracles": oracles})
                    self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_one_family_cannot_mix_native_signatures_cohorts_or_oracle_meanings(self):
        for field, value in (
            ("semantic_signature", "synthetic-exposed-mismatch"), ("cohort", "answer"),
            ("oracle_id", "E02_compare.v1"),
        ):
            with self.subTest(field=field):
                path, intake = self.write_bundle()
                cases = copy.deepcopy(self.cases)
                cases["cases"][3][field] = value
                self.replace_asset(path, intake, "cases", cases)
                self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_intake_review_membership_is_checked_after_native_loading(self):
        for change in ("missing_family", "wrong_case", "duplicate_signature"):
            with self.subTest(change=change):
                path, intake = self.write_bundle()
                if change == "missing_family":
                    intake["families"].pop()
                elif change == "wrong_case":
                    intake["families"][0]["case_ids"][0] = "SyntheticUnknownCase"
                else:
                    intake["families"][1]["reviewed_signature"] = intake["families"][0]["reviewed_signature"]
                self.write_json(path, intake)
                self.rejects(admission.audit_intake, path, code="invalid_panel")

    def test_real_development_bundle_never_freezes_even_when_reviewed_or_relabelled_in_memory(self):
        for state, relabel in (("draft", False), ("novelty_reviewed", False),
                               ("novelty_reviewed", True)):
            with self.subTest(state=state, relabel=relabel):
                path, intake = self.write_bundle()
                intake.update(state=state, owner_review_reference=OWNER_REFERENCE)
                self.write_json(path, intake)
                panel_path = path.parent / "development-panel-v1.json"
                panel_path.write_bytes((DEVELOPMENT / panel_path.name).read_bytes())
                panel = assets.load_panel(panel_path)
                if relabel:
                    panel = replace(panel, kind="formal")
                output = path.parent / "must-not-freeze"
                with patch.object(assets, "load_panel", return_value=panel):
                    self.rejects(
                        admission.freeze_panel, self.directory / "unused.sqlite", path, panel_path,
                        output, accepted_commit=SYNTHETIC_TOOLING_COMMIT,
                        code="formal_not_admitted" if state == "draft" else "invalid_panel")
                self.assertFalse(output.exists())

    def test_audit_cli_prints_only_sanitized_metadata_summary(self):
        path, _ = self.write_bundle()
        code, stdout, stderr = self.cli(admission.main, ["audit", "--intake", str(path)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), {
            "state": "draft", "family_count": 9, "input_count": 15,
            "proposed_fresh_families": 0, "eligible_for_fresh_review": True,
            "review_assertions_complete": False, "live_model_attempts": 0,
        })


class P3CandidateIdentityTests(AdmissionAssertions):
    def runtime_paths(self):
        return tuple(sorted(path.relative_to(ROOT).as_posix()
                            for path in (ROOT / "grepbit").rglob("*.py")))

    def mock_git(self, runtime_paths=None):
        paths = self.runtime_paths() if runtime_paths is None else runtime_paths

        def run(command, **options):
            self.assertEqual(command[:2], ["git", "--no-optional-locks"])
            self.assertEqual(options["cwd"], ROOT)
            self.assertTrue(options["capture_output"])
            self.assertTrue(options["check"])
            self.assertEqual(options["timeout"], 5)
            if command[2] == "ls-tree":
                self.assertEqual(command[3:], ["-r", "--name-only", FROZEN_BASELINE, "--", "grepbit"])
                self.assertTrue(options["text"])
                return SimpleNamespace(stdout="\n".join(paths))
            self.assertEqual(command[2], "show")
            self.assertTrue(command[3].startswith(FROZEN_BASELINE + ":"))
            name = command[3].split(":", 1)[1]
            return SimpleNamespace(stdout=self.synthetic_bytes(name))

        return run

    def synthetic_bytes(self, name):
        return f"synthetic-source-identity-only:{name}".encode("ascii")

    def mock_pin(self, path):
        name = path.relative_to(ROOT).as_posix()
        return {"reference": path.name, "sha256": hashlib.sha256(self.synthetic_bytes(name)).hexdigest()}

    def test_real_protected_sources_match_the_declared_frozen_git_snapshot(self):
        identity = admission.candidate_identity()
        self.assertEqual(identity["candidate_freeze_sha"], FROZEN_BASELINE)
        self.assertEqual(identity["declared_at"], DECLARED_AT)
        self.assertEqual(identity["declaration"], "https://github.com/cinic0101/grepbit/issues/43")
        expected_paths = set(self.runtime_paths()) | set(PROTECTED_TOOLS)
        self.assertTrue(expected_paths.issubset(identity["files_sha256"]))
        for name, digest in identity["files_sha256"].items():
            with self.subTest(source=name):
                self.assertEqual(digest, hashlib.sha256((ROOT / name).read_bytes()).hexdigest())
        self.assertEqual(identity["evidence_expectations"], p3_expectations.identity())
        self.assertEqual(identity["evidence_expectations"]["version"], "p3-evidence-expectations-v1")

    def test_isolated_identity_mocks_preserve_the_full_protected_inventory(self):
        with patch.object(admission.subprocess, "run", side_effect=self.mock_git()) as git, \
                patch.object(admission.p3_eval, "_pin", side_effect=self.mock_pin) as pin:
            identity = admission.candidate_identity()
        paths = set(self.runtime_paths()) | set(PROTECTED_TOOLS)
        self.assertTrue(paths.issubset(identity["files_sha256"]))
        self.assertEqual(pin.call_count, len(identity["files_sha256"]))
        self.assertEqual(git.call_count, len(identity["files_sha256"]) + 1)
        for name in paths:
            self.assertEqual(identity["files_sha256"][name],
                             hashlib.sha256(self.synthetic_bytes(name)).hexdigest())

    def test_source_byte_drift_is_rejected_without_mutating_any_product_file(self):
        for target in ("grepbit/recipe_model.py", "grepbit/kernel.py", *PROTECTED_TOOLS):
            with self.subTest(target=target):
                def drift(path):
                    result = self.mock_pin(path)
                    if path.relative_to(ROOT).as_posix() == target:
                        result["sha256"] = "0" * 64
                    return result

                with patch.object(admission.subprocess, "run", side_effect=self.mock_git()), \
                        patch.object(admission.p3_eval, "_pin", side_effect=drift):
                    self.rejects(admission.candidate_identity, code="source_identity_failure")

    def test_empty_missing_or_added_frozen_runtime_inventory_is_rejected(self):
        paths = self.runtime_paths()
        for inventory in ((), paths[1:], (*paths, "grepbit/synthetic_missing.py")):
            with self.subTest(inventory_size=len(inventory)):
                with patch.object(admission.subprocess, "run", side_effect=self.mock_git(inventory)) as git, \
                        patch.object(admission.p3_eval, "_pin") as pin:
                    self.rejects(admission.candidate_identity, code="source_identity_failure")
                self.assertEqual(git.call_count, 1)
                pin.assert_not_called()

    def test_git_failures_and_timeouts_are_sanitized_source_identity_failures(self):
        for failure in (
            OSError("SYNTHETIC_PRIVATE_METADATA_CANARY"),
            subprocess.CalledProcessError(1, ["git"], stderr=b"SYNTHETIC_PRIVATE_METADATA_CANARY"),
            subprocess.TimeoutExpired(["git"], 5),
        ):
            for fail_show in (False, True):
                with self.subTest(failure=type(failure).__name__, fail_show=fail_show):
                    effects = ([SimpleNamespace(stdout="\n".join(self.runtime_paths())), failure]
                               if fail_show else failure)
                    with patch.object(admission.subprocess, "run", side_effect=effects):
                        self.rejects(admission.candidate_identity, code="source_identity_failure")

    def test_unreadable_current_source_is_sanitized_without_disk_mutation(self):
        with patch.object(admission.subprocess, "run", side_effect=self.mock_git()), \
                patch.object(admission.p3_eval, "_pin",
                             side_effect=OSError("SYNTHETIC_PRIVATE_METADATA_CANARY")):
            self.rejects(admission.candidate_identity, code="source_identity_failure")


class PreparationAssertions(AdmissionAssertions):
    """Mock only DB/source attestations; never execute or manufacture a database."""

    def setUp(self):
        super().setUp()
        self.poison("tools.p3_admission.subprocess.run")
        self.poison("tools.p3_eval.fake_client")
        self.database = self.directory / "unused-metadata-only.sqlite"
        self.source = {
            "git_commit": SYNTHETIC_TOOLING_COMMIT, "branch": "dev", "worktree_dirty": False,
            "files_sha256": {}, "synthetic_metadata_only": True,
        }
        self.enterContext(patch.object(recipe_smoke, "_source_identity",
                                       side_effect=lambda: copy.deepcopy(self.source)))
        self.fixture_identity = self.enterContext(patch.object(
            smoke, "_fixture_identity", return_value=SYNTHETIC_DATABASE_SHA256))
        self.enterContext(patch.object(smoke, "_stable_database", return_value=SYNTHETIC_DATABASE_SHA256))
        self.candidate = self.enterContext(patch.object(admission, "candidate_identity", return_value={
            "candidate_freeze_sha": FROZEN_BASELINE, "declared_at": DECLARED_AT,
            "synthetic_metadata_only": True, "files_sha256": {},
            "evidence_expectations": p3_expectations.identity(),
        }))


class MetadataPublicationAssertions(PreparationAssertions):
    """Trusted admission/native metadata are mocked, not real formal readiness.

    Snapshot inputs are the original exposed development bytes and a deliberately
    non-native metadata marker. No fresh question, oracle or formal panel asset
    is authored. The returned Panel and oracle objects are plumbing test doubles.
    """

    def setUp(self):
        super().setUp()
        self.rows = formal_scaffolding()
        for row in self.rows:
            row["provenance"] = metadata_provenance(row["exposure"])
        p3_scoring.validate_formal_allocation(self.rows)
        self.review = {
            "families": abstract_reviews(self.rows), "owner_review_reference": OWNER_REFERENCE,
            "state": "novelty_reviewed",
        }
        self.intake_path = self.directory / "synthetic-metadata-only-intake.json"
        self.write_json(self.intake_path, {"synthetic_metadata_only": True, "not_a_native_intake": True})
        self.panel_path = DEVELOPMENT / "development-panel-v1.json"
        self.mock_cases = tuple(SimpleNamespace(
            case_id=row["case_id"], oracle_id=row["oracle_id"],
            metadata=lambda order, reference, row=row: {
                **copy.deepcopy(row), "order": order,
                "question_reference": {"asset": reference, "case_id": row["case_id"], "field": "question"},
            },
        ) for row in self.rows)
        self.mock_oracles = tuple(SimpleNamespace(
            oracle_id=oracle_id, revision=1,
            to_dict=lambda oracle_id=oracle_id: {
                "oracle_id": oracle_id, "synthetic_metadata_only": True, "not_native_gold": True,
            },
        ) for oracle_id in dict.fromkeys(row["oracle_id"] for row in self.rows))
        self.materials = self.enterContext(patch.object(
            admission, "_formal_materials",
            side_effect=lambda intake, panel: (self.metadata_panel(panel), copy.deepcopy(self.review))))
        self.enterContext(patch.object(assets, "load_panel", side_effect=self.metadata_panel))
        self.output = self.directory / "mock-publication-not-an-admitted-freeze"

    def metadata_panel(self, path):
        return assets.Panel(
            "SyntheticMetadataPlumbingNotAdmitted", "formal", self.mock_cases, self.mock_oracles,
            path, path.parent / "development-cases-v1.json", path.parent / "development-oracles-v1.json")

    def freeze(self, output=None, **options):
        arguments = {"accepted_commit": SYNTHETIC_TOOLING_COMMIT, **options}
        return admission.freeze_panel(
            self.database, self.intake_path, self.panel_path, output or self.output, **arguments)

    def validate_frozen(self, output=None, **options):
        directory = output or self.output
        arguments = {"accepted_commit": SYNTHETIC_TOOLING_COMMIT, **options}
        return admission.validate_freeze(
            directory / "report.json", self.database, directory / self.panel_path.name, **arguments)

    def assert_incomplete(self, directory):
        manifest = json.loads((directory / "manifest.json").read_bytes())
        report = json.loads((directory / "report.json").read_bytes())
        self.assertEqual((manifest["state"], report["state"]), ("incomplete", "incomplete"))
        self.assertEqual(report["live_model_attempts"], 0)
        self.assertEqual(report["planned_sha256"], manifest["planned_sha256"])
        self.rejects(self.validate_frozen, directory, code="invalid_manifest")


class P3FreezePublicationPlumbingTests(MetadataPublicationAssertions):
    def test_mocked_admission_publication_copies_original_bytes_without_claiming_real_readiness(self):
        sources = {
            "intake": self.intake_path, "panel": self.panel_path,
            "cases": DEVELOPMENT / "development-cases-v1.json",
            "oracles": DEVELOPMENT / "development-oracles-v1.json",
        }
        before = {key: path.read_bytes() for key, path in sources.items()}
        payload = self.freeze()
        self.assertTrue(payload["candidate"]["synthetic_metadata_only"])
        self.assertEqual((payload["state"], payload["execution"], payload["live_model_attempts"]),
                         ("frozen", "not_admitted", 0))
        self.assertEqual(payload["accepted_tooling_commit"], SYNTHETIC_TOOLING_COMMIT)
        self.assertEqual(payload["allocation"], {
            "families": 24, "inputs": 44,
            "family_cohorts": {"answer": 12, "clarify": 4, "decline": 5, "anchor": 3},
            "input_cohorts": {"answer": 18, "clarify": 8, "decline": 9, "anchor": 9},
            "family_exposures": {"frozen_fresh": 12, "exposed_regression": 12},
            "input_exposures": {"frozen_fresh": 26, "exposed_regression": 18},
            "languages": {"zh-TW": 14, "en": 15, "ja": 15},
        })
        self.assertEqual(payload["order"], [row["case_id"] for row in self.rows])
        for name, source in sources.items():
            snapshot = self.output / source.name
            self.assertEqual(snapshot.read_bytes(), before[name])
            self.assertEqual(source.read_bytes(), before[name])
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
            self.assertEqual(payload["assets"][name]["sha256"], hashlib.sha256(before[name]).hexdigest())
        self.assertEqual(json.loads((self.output / self.panel_path.name).read_bytes())["kind"], "development")
        self.assertEqual(json.loads((self.output / "report.json").read_bytes()), payload)
        self.assertEqual(json.loads((self.output / "checkpoint-0000.json").read_bytes())["state"], "incomplete")
        self.assertEqual(self.validate_frozen(), {
            "version": admission.FREEZE_VERSION, "sha256": assets.digest(payload),
            "candidate_freeze_sha": FROZEN_BASELINE,
        })

    def test_freeze_output_is_exclusive_for_existing_empty_populated_and_file_paths(self):
        for kind in ("empty", "populated", "file"):
            with self.subTest(kind=kind):
                output = self.directory / kind
                if kind == "file":
                    output.write_bytes(b"existing-file")
                else:
                    output.mkdir()
                    if kind == "populated":
                        (output / "report.json").write_bytes(b"existing-evidence")
                with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
                    self.freeze(output)
                if kind == "file":
                    self.assertEqual(output.read_bytes(), b"existing-file")
                elif kind == "empty":
                    self.assertEqual(list(output.iterdir()), [])
                else:
                    self.assertEqual((output / "report.json").read_bytes(), b"existing-evidence")
                    self.assertEqual(len(list(output.iterdir())), 1)

    def test_snapshot_exclusive_conflict_retains_incomplete_evidence(self):
        original = admission._snapshot

        def conflict(artifacts, source, expected):
            (artifacts.directory / expected["reference"]).write_bytes(b"existing-snapshot")
            return original(artifacts, source, expected)

        with patch.object(admission, "_snapshot", side_effect=conflict):
            self.rejects(self.freeze, code="artifact_conflict")
        self.assert_incomplete(self.output)
        self.assertEqual((self.output / self.intake_path.name).read_bytes(), b"existing-snapshot")

    def test_source_byte_drift_between_planning_and_snapshot_retains_incomplete(self):
        original = admission._snapshot

        def drift(artifacts, source, expected):
            self.assertEqual(source, self.intake_path)
            source.write_bytes(source.read_bytes() + b"\n")
            return original(artifacts, source, expected)

        with patch.object(admission, "_snapshot", side_effect=drift):
            self.rejects(self.freeze, code="manifest_drift")
        self.assert_incomplete(self.output)
        self.assertFalse((self.output / self.intake_path.name).exists())

    def test_each_snapshot_is_revalidated_before_terminal_publication(self):
        original = admission.stage_terminal
        for name in ("intake", "panel", "cases", "oracles"):
            with self.subTest(asset=name):
                output = self.directory / f"copy-drift-{name}"

                def drift(artifacts, payload, **options):
                    path = artifacts.directory / payload["assets"][name]["reference"]
                    path.write_bytes(path.read_bytes() + b"\n")
                    return original(artifacts, payload, **options)

                with patch.object(admission, "stage_terminal", side_effect=drift):
                    self.rejects(self.freeze, output, code="manifest_drift")
                self.assert_incomplete(output)
                self.assertEqual(json.loads((output / "terminal-candidate.json").read_bytes())["state"], "frozen")

    def test_db_candidate_and_tooling_drift_at_finalization_do_not_publish_success(self):
        original = admission.stage_terminal
        initial_candidate = copy.deepcopy(self.candidate.return_value)
        for kind in ("database", "candidate", "tooling"):
            with self.subTest(kind=kind):
                self.fixture_identity.return_value = SYNTHETIC_DATABASE_SHA256
                self.candidate.return_value = copy.deepcopy(initial_candidate)
                self.source["files_sha256"] = {}
                output = self.directory / f"identity-drift-{kind}"

                def drift(artifacts, payload, **options):
                    if kind == "database":
                        self.fixture_identity.return_value = "e" * 64
                    elif kind == "candidate":
                        self.candidate.return_value = {
                            **initial_candidate, "files_sha256": {"synthetic-drift": "e" * 64},
                        }
                    else:
                        self.source["files_sha256"] = {"synthetic-drift": "e" * 64}
                    return original(artifacts, payload, **options)

                with patch.object(admission, "stage_terminal", side_effect=drift):
                    self.rejects(self.freeze, output, code="manifest_drift")
                self.assert_incomplete(output)

    def test_failed_atomic_commit_keeps_incomplete_report_and_staged_candidate(self):
        with patch.object(admission, "commit_terminal", side_effect=smoke.SmokeError("artifact_io")):
            with self.assertRaisesRegex(smoke.SmokeError, "^artifact_io$"):
                self.freeze()
        self.assert_incomplete(self.output)
        self.assertTrue((self.output / "terminal.next.json").exists())
        self.assertEqual(json.loads((self.output / "terminal-candidate.json").read_bytes())["state"], "frozen")

    def test_expired_finalization_budget_keeps_incomplete_report(self):
        with patch.object(admission.time, "monotonic", side_effect=(0.0, 60.0)):
            with self.assertRaisesRegex(smoke.SmokeError, "^panel_budget$"):
                self.freeze()
        self.assert_incomplete(self.output)

    def test_freeze_requires_exact_clean_dev_tooling_not_the_product_baseline(self):
        for changes, commit in (
            ({}, None), ({}, FROZEN_BASELINE), ({}, SYNTHETIC_TOOLING_COMMIT[:8]),
            ({"branch": "main"}, SYNTHETIC_TOOLING_COMMIT),
            ({"branch": "feat/synthetic"}, SYNTHETIC_TOOLING_COMMIT),
            ({"worktree_dirty": True}, SYNTHETIC_TOOLING_COMMIT),
            ({"worktree_dirty": 0}, SYNTHETIC_TOOLING_COMMIT),
        ):
            with self.subTest(changes=changes, commit=commit):
                self.source.update(branch="dev", worktree_dirty=False)
                self.source.update(changes)
                with self.assertRaisesRegex(recipe_smoke.RecipeSmokeError, "^accepted_commit_required$"):
                    self.freeze(accepted_commit=commit)
                self.assertFalse(self.output.exists())

    def test_validation_requires_new_freeze_version_state_and_matching_planned_hash(self):
        payload = self.freeze()
        report_path = self.output / "report.json"
        header_path = self.output / "manifest.json"
        header = json.loads(header_path.read_bytes())
        for changes in ({"version": "p3-formal-freeze-v0"}, {"state": "incomplete"},
                        {"owner_review_reference": "synthetic:changed-owner-reference"}):
            with self.subTest(changes=changes):
                self.write_json(report_path, {**payload, **changes})
                self.rejects(self.validate_frozen, code="invalid_manifest")
        self.write_json(report_path, payload)
        self.write_json(header_path, {**header, "planned_sha256": "0" * 64})
        self.rejects(self.validate_frozen, code="invalid_manifest")
        changed = {**payload, "owner_review_reference": "synthetic:changed-owner-reference"}
        self.write_json(report_path, changed)
        self.write_json(header_path, {**header, "planned_sha256": assets.digest(changed)})
        self.rejects(self.validate_frozen, code="manifest_drift")

    def test_validating_freeze_rejects_any_changed_snapshot_and_wrong_panel_bytes(self):
        self.freeze()
        payload = json.loads((self.output / "report.json").read_bytes())
        for name, pin in payload["assets"].items():
            with self.subTest(asset=name):
                path = self.output / pin["reference"]
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                self.rejects(self.validate_frozen, code="manifest_drift")
                path.write_bytes(original)
        wrong_panel = self.directory / self.panel_path.name
        wrong_panel.write_bytes(self.panel_path.read_bytes() + b"\n")
        self.rejects(admission.validate_freeze, self.output / "report.json", self.database, wrong_panel,
                     accepted_commit=SYNTHETIC_TOOLING_COMMIT, code="manifest_drift")


class P3ProbePreparationTests(PreparationAssertions):
    def test_probe_preparation_selects_only_exposed_english_anchor_with_zero_calls_and_fixed_limits(self):
        output = self.directory / "probe-plan"
        payload = admission.prepare_probe(self.database, output)
        case = next(case for case in assets.load_panel(runner.DEFAULT_PANEL).cases
                    if case.case_id == "E01_overview.en")
        self.assertEqual((payload["version"], payload["state"]),
                         ("p3-compatibility-preparation-v1", "prepared"))
        self.assertEqual(payload["preparation"], {"kind": "candidate", "accepted_commit": None})
        self.assertEqual(payload["exposure"], "exposed_regression")
        self.assertEqual(payload["question_sha256"], hashlib.sha256(case.question.encode()).hexdigest())
        self.assertEqual(payload["question_reference"]["case_id"], case.case_id)
        self.assertEqual(payload["execution"], "not_admitted")
        self.assertTrue(payload["owner_authorization_required"])
        self.assertEqual((payload["client_http_attempts"], payload["live_model_attempts"]), (0, 0))
        self.assertIsNone(payload["upstream_inference_attempts"])
        self.assertEqual(payload["upstream_retry_policy"], "requires_owner_attestation_before_live")
        self.assertEqual((payload["max_future_client_http_attempts"], payload["retries"],
                          payload["repairs"], payload["fallbacks"]), (1, 0, 0, 0))
        limits = payload["settings"]
        self.assertEqual((limits["inputs"], limits["max_client_http_attempts"], limits["concurrency"],
                          limits["client_retries"], limits["call_timeout_seconds"], limits["max_tokens"]),
                         (1, 1, 1, 0, 60.0, 2048))
        self.assertEqual(payload["settings_sha256"], assets.digest(limits))
        self.assertEqual(payload["database_sha256"], SYNTHETIC_DATABASE_SHA256)
        self.assertNotIn(case.question, json.dumps(payload, ensure_ascii=False))
        self.assertEqual(json.loads((output / "manifest.json").read_bytes()), payload)
        self.assertEqual(json.loads((output / "report.json").read_bytes()), {
            "version": admission.PROBE_VERSION, "state": "prepared",
            "manifest_sha256": assets.digest(payload), "client_http_attempts": 0, "live_model_attempts": 0,
        })

    def test_candidate_probe_plan_is_not_accepted_dev_authorization(self):
        self.source.update(branch="feat/synthetic", worktree_dirty=True)
        candidate = admission.prepare_probe(self.database, self.directory / "candidate")
        self.assertEqual(candidate["preparation"]["kind"], "candidate")
        with self.assertRaisesRegex(recipe_smoke.RecipeSmokeError, "^accepted_commit_required$"):
            admission.prepare_probe(self.database, self.directory / "rejected",
                                    accepted_commit=SYNTHETIC_TOOLING_COMMIT)
        self.assertFalse((self.directory / "rejected").exists())
        self.source.update(branch="dev", worktree_dirty=False)
        accepted = admission.prepare_probe(self.database, self.directory / "accepted",
                                           accepted_commit=SYNTHETIC_TOOLING_COMMIT)
        self.assertEqual(accepted["preparation"],
                         {"kind": "accepted", "accepted_commit": SYNTHETIC_TOOLING_COMMIT})
        self.assertEqual(accepted["execution"], "not_admitted")

    def test_existing_probe_evidence_cannot_be_overwritten(self):
        output = self.directory / "probe"
        admission.prepare_probe(self.database, output)
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        with self.assertRaisesRegex(smoke.SmokeError, "^artifact_conflict$"):
            admission.prepare_probe(self.database, output)
        self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_probe_revalidation_detects_source_candidate_database_and_protocol_drift(self):
        original_pin = runner._pin
        for kind in ("source", "candidate", "database", "protocol"):
            with self.subTest(kind=kind):
                output = self.directory / f"drift-{kind}"
                source = runner._source_identity(assets.load_panel(runner.DEFAULT_PANEL), None)
                candidate = copy.deepcopy(self.candidate.return_value)
                with patch.object(runner, "_source_identity",
                                  side_effect=[source, {**source, "drift": True} if kind == "source" else source]), \
                        patch.object(admission, "candidate_identity",
                                     side_effect=[candidate, {**candidate, "drift": True}
                                                  if kind == "candidate" else candidate]), \
                        patch.object(smoke, "_fixture_identity", side_effect=[
                            SYNTHETIC_DATABASE_SHA256,
                            "e" * 64 if kind == "database" else SYNTHETIC_DATABASE_SHA256,
                        ]):
                    protocol_reads = 0

                    def pin(path):
                        nonlocal protocol_reads
                        result = original_pin(path)
                        if path == admission.PROTOCOL:
                            protocol_reads += 1
                            if kind == "protocol" and protocol_reads > 1:
                                result["sha256"] = "e" * 64
                        return result

                    with patch.object(runner, "_pin", side_effect=pin):
                        self.rejects(admission.prepare_probe, self.database, output, code="manifest_drift")
                self.assertTrue((output / "manifest.json").exists())
                self.assertFalse((output / "report.json").exists())

    def test_probe_requires_exactly_one_exposed_english_anchor(self):
        panel = assets.load_panel(runner.DEFAULT_PANEL)
        target = next(case for case in panel.cases if case.case_id == "E01_overview.en")
        for cases in (
            tuple(case for case in panel.cases if case != target),
            panel.cases + (target,),
            tuple(replace(case, exposure="design_seen") if case == target else case for case in panel.cases),
        ):
            with self.subTest(size=len(cases)):
                output = self.directory / "rejected-probe"
                with patch.object(assets, "load_panel", return_value=replace(panel, cases=cases)):
                    self.rejects(admission.prepare_probe, self.database, output, code="invalid_panel")
                self.assertFalse(output.exists())

    def test_probe_cli_is_preparation_only_and_explicit_live_is_rejected_by_both_clis(self):
        output = self.directory / "cli-probe"
        code, stdout, stderr = self.cli(admission.main, [
            "probe-prepare", "--db", str(self.database), "--output-dir", str(output),
        ])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), {"state": "prepared", "live_model_attempts": 0})
        for function, arguments in (
            (admission.main, ["probe-prepare", "--db", str(self.database),
                              "--output-dir", str(self.directory / "live-probe"), "--live"]),
            (admission.main, ["freeze", "--live"]),
            (runner.main, ["prepare", "--db", str(self.database),
                           "--output-dir", str(self.directory / "live-formal"), "--live"]),
        ):
            with self.subTest(cli=function.__module__, arguments=arguments[0]):
                code, stdout, stderr = self.cli(function, arguments)
                self.assertEqual((code, stdout), (2, ""))
                self.assertEqual(json.loads(stderr)["error_code"], "invalid_arguments")
        self.assertFalse((self.directory / "live-probe").exists())
        self.assertFalse((self.directory / "live-formal").exists())

    def test_archived_development_preparation_needs_no_freeze_or_current_checkout(self):
        output = self.directory / "development-archive"
        report = runner.prepare(self.database, output, responses_path=runner.DEFAULT_RESPONSES)
        manifest = json.loads((output / "manifest.json").read_bytes())
        self.assertEqual(manifest["panel_kind"], "development")
        self.assertNotIn("formal_freeze", manifest["assets"])
        self.assertEqual(report["client_http_attempts"], 0)
        for target in (
            "tools.p3_eval._source_identity", "tools.smoke._fixture_identity",
            "tools.smoke._stable_database", "tools.p3_assets.load_panel",
            "tools.p3_admission.validate_freeze", "tools.p3_admission.candidate_identity",
        ):
            self.poison(target)
        self.assertEqual(runner.read_report(output / "report.json"), report)
        code, stdout, stderr = self.cli(runner.main, ["report", "--report", str(output / "report.json")])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout)["status"], "prepared")


class P3FormalPreparationPlumbingTests(MetadataPublicationAssertions):
    """Only publication under mocked trusted admission/native metadata, not gold."""

    def setUp(self):
        super().setUp()
        self.freeze()
        self.frozen = self.output / "report.json"
        self.frozen_panel = self.output / self.panel_path.name
        self.prepared = self.directory / "mock-formal-preparation"

    def prepare(self, **options):
        arguments = {
            "panel_path": self.frozen_panel, "formal_freeze": self.frozen,
            "accepted_commit": SYNTHETIC_TOOLING_COMMIT, **options,
        }
        return runner.prepare(self.database, self.prepared, **arguments)

    def test_metadata_only_formal_preparation_pins_freeze_bytes_but_never_executes_or_promotes(self):
        report = self.prepare()
        manifest = json.loads((self.prepared / "manifest.json").read_bytes())
        self.assertEqual((report["status"], report["origin"], report["panel_kind"]),
                         ("prepared", "preparation", "formal"))
        self.assertEqual((report["client_http_attempts"], report["live_model_attempts"]), (0, 0))
        self.assertEqual((report["summary"]["semantic_families"], len(report["results"])), (24, 44))
        self.assertFalse(report["summary"]["promotion"]["passed"])
        self.assertIn("preparation only", report["scope"])
        self.assertIsNone(manifest["fake_responses"])
        digest = hashlib.sha256(self.frozen.read_bytes()).hexdigest()
        self.assertEqual(manifest["assets"]["formal_freeze"], {"reference": "report.json", "sha256": digest})
        self.assertEqual(manifest["identities"]["files_sha256"]["p3_asset:formal_freeze"], digest)
        self.assertEqual(report["manifest_sha256"], assets.digest(manifest))
        self.assertTrue(all(pin["value"]["synthetic_metadata_only"] for pin in manifest["oracles"]))
        for row in report["results"]:
            self.assertEqual((row["status"], row["outcome"]), ("not_run", "not_run"))
            self.assertFalse(row["runtime_invoked"])
            self.assertEqual(set(row["layers"].values()), {"not_assessed"})
            self.assertNotIn("question", row)

    def test_formal_prepare_requires_freeze_accepted_tooling_and_no_fake_script(self):
        for options in (
            {"formal_freeze": None}, {"accepted_commit": None}, {"responses_path": runner.DEFAULT_RESPONSES},
        ):
            with self.subTest(options=options):
                self.rejects(self.prepare, **options, code="formal_not_admitted")
                self.assertFalse(self.prepared.exists())
        panel = self.metadata_panel(self.frozen_panel)
        with patch.object(assets, "load_panel", return_value=replace(panel, kind="development")):
            self.rejects(self.prepare, code="formal_not_admitted")
        self.assertFalse(self.prepared.exists())

    def test_formal_prepare_rejects_unaccepted_or_dirty_non_dev_tooling(self):
        for changes, accepted in (
            ({}, FROZEN_BASELINE), ({"branch": "main"}, SYNTHETIC_TOOLING_COMMIT),
            ({"branch": "feat/synthetic"}, SYNTHETIC_TOOLING_COMMIT),
            ({"worktree_dirty": True}, SYNTHETIC_TOOLING_COMMIT),
        ):
            with self.subTest(changes=changes, accepted=accepted):
                self.source.update(branch="dev", worktree_dirty=False)
                self.source.update(changes)
                with self.assertRaisesRegex(recipe_smoke.RecipeSmokeError, "^accepted_commit_required$"):
                    self.prepare(accepted_commit=accepted)
                self.assertFalse(self.prepared.exists())

    def test_formal_prepare_rechecks_freeze_after_persisting_incomplete_report(self):
        original = admission.validate_freeze
        calls = 0

        def validate(*args, **options):
            nonlocal calls
            calls += 1
            if (self.prepared / "report.json").exists():
                raise assets.P3Error("manifest_drift")
            return original(*args, **options)

        with patch.object(admission, "validate_freeze", side_effect=validate):
            self.rejects(self.prepare, code="manifest_drift")
        # Admission routing may add pre-publication reads; the protected boundary
        # is revalidation after the incomplete report, not an incidental call count.
        self.assertGreaterEqual(calls, 3)
        report = json.loads((self.prepared / "report.json").read_bytes())
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(all(row["status"] == "pending" for row in report["results"]))
        self.assertEqual(report["client_http_attempts"], 0)

    def test_formal_freeze_raw_byte_identity_gate_catches_even_whitespace_drift(self):
        original = runner.build_manifest

        def drift(*args, **options):
            manifest = original(*args, **options)
            self.frozen.write_bytes(self.frozen.read_bytes() + b"\n")
            return manifest

        with patch.object(runner, "build_manifest", side_effect=drift):
            self.rejects(self.prepare, code="manifest_drift")
        self.assertEqual(json.loads((self.prepared / "report.json").read_bytes())["status"], "incomplete")
        self.assertEqual(self.validate_frozen()["version"], admission.FREEZE_VERSION)

    def test_formal_preparation_cli_omits_default_fake_responses(self):
        code, stdout, stderr = self.cli(runner.main, [
            "prepare", "--db", str(self.database), "--panel", str(self.frozen_panel),
            "--formal-freeze", str(self.frozen), "--accepted-commit", SYNTHETIC_TOOLING_COMMIT,
            "--output-dir", str(self.prepared),
        ])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout)["status"], "prepared")
        self.assertIsNone(json.loads((self.prepared / "manifest.json").read_bytes())["fake_responses"])

    def test_formal_fake_execution_and_formal_freeze_with_fake_run_flag_remain_rejected(self):
        self.rejects(
            asyncio.run, runner.run_panel(
                self.database, self.directory / "must-not-execute", manifest_path=self.frozen,
                panel_path=self.frozen_panel, responses_path=runner.DEFAULT_RESPONSES),
            code="formal_not_admitted")
        code, stdout, stderr = self.cli(runner.main, [
            "fake-run", "--db", str(self.database), "--output-dir", str(self.directory / "must-not-execute"),
            "--manifest", str(self.frozen), "--panel", str(self.frozen_panel),
            "--formal-freeze", str(self.frozen),
        ])
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(json.loads(stderr)["error_code"], "invalid_arguments")
        self.assertFalse((self.directory / "must-not-execute").exists())

    def test_formal_archive_under_mocked_native_parser_is_preparation_only(self):
        report = self.prepare()
        by_id = {oracle.oracle_id: oracle for oracle in self.mock_oracles}
        with patch.object(assets, "parse_oracle", side_effect=lambda value: by_id[value["oracle_id"]]):
            self.assertEqual(runner.read_report(self.prepared / "report.json"), report)
        invoked = copy.deepcopy(report["results"])
        invoked[0]["runtime_invoked"] = True
        for changes in (
            {"status": "complete"}, {"origin": "mock"}, {"client_http_attempts": 1},
            {"attempt_budget_used": 1}, {"possible_in_flight_attempts": 1}, {"results": invoked},
        ):
            with self.subTest(changes=changes):
                self.write_json(self.prepared / "report.json", {**report, **changes})
                self.rejects(runner.read_report, self.prepared / "report.json", code="formal_not_admitted")

    def test_formal_archive_requires_the_new_freeze_asset_and_matching_identity_pin(self):
        report = self.prepare()
        original = json.loads((self.prepared / "manifest.json").read_bytes())
        by_id = {oracle.oracle_id: oracle for oracle in self.mock_oracles}
        for missing in (False, True):
            with self.subTest(missing=missing):
                manifest = copy.deepcopy(original)
                if missing:
                    del manifest["assets"]["formal_freeze"]
                else:
                    manifest["identities"]["files_sha256"]["p3_asset:formal_freeze"] = "0" * 64
                self.write_json(self.prepared / "manifest.json", manifest)
                self.write_json(self.prepared / "report.json",
                                {**report, "manifest_sha256": assets.digest(manifest)})
                with patch.object(assets, "parse_oracle", side_effect=lambda value: by_id[value["oracle_id"]]):
                    self.rejects(runner.read_report, self.prepared / "report.json", code="invalid_manifest")


class P3ExposedWrapperIsolationTests(unittest.IsolatedAsyncioTestCase):
    """Exposed question-only wire plumbing, never fresh/formal execution evidence."""

    def setUp(self):
        for target in (
            "socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
            "socket.getaddrinfo", "httpx.AsyncHTTPTransport", "httpx.HTTPTransport",
            "grepbit.gateway.GatewayConfig.from_env",
        ):
            guard = patch(target, side_effect=AssertionError("Only explicit MockTransport is permitted"))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)
        temporary = tempfile.TemporaryDirectory(prefix="p33-exposed-isolation-", dir=ROOT / ".artifacts")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.database = self.directory / "exposed-fixture.sqlite"
        fixture.build(self.database)
        self.cases = json.loads((DEVELOPMENT / "development-cases-v1.json").read_bytes())
        self.oracles = json.loads((DEVELOPMENT / "development-oracles-v1.json").read_bytes())
        self.actions = {
            row["case_id"]: row["action"]
            for row in json.loads((DEVELOPMENT / "development-responses-v1.json").read_bytes())["responses"]
        }

    def client(self, actions, sent):
        def respond(request):
            action = actions[len(sent)]
            sent.append(request)
            return httpx.Response(200, json={
                "model": MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(action)}}],
            })

        return GatewayClient(
            GatewayConfig("https://p33-exposed-isolation.invalid/v1", "synthetic-p33-offline-token"),
            transport=httpx.MockTransport(respond))

    async def test_exposed_wrapper_canaries_never_enter_wire_native_evidence_or_presentation(self):
        ids = ("E01_overview.en", "C01_count_basis.en")
        cases = [copy.deepcopy(next(case for case in self.cases["cases"] if case["case_id"] == case_id))
                 for case_id in ids]
        reviews = abstract_reviews(cases)
        markers = [FROZEN_BASELINE]
        for case, review in zip(cases, reviews, strict=True):
            family = case["family_id"]
            canaries = {
                "novelty_rationale": f"SYNTHETIC_EXPOSED_WRAPPER_NOVELTY_{family}",
                "author": f"SYNTHETIC_EXPOSED_WRAPPER_AUTHOR_{family}",
                "reviewer": f"SYNTHETIC_EXPOSED_WRAPPER_REVIEWER_{family}",
                "reviewed_signature": f"SYNTHETIC_EXPOSED_WRAPPER_SIGNATURE_{family}",
            }
            review.update(novelty_rationale=canaries["novelty_rationale"],
                          reviewed_signature=canaries["reviewed_signature"])
            review["author"]["reference"] = canaries["author"]
            review["reviewer"]["reference"] = canaries["reviewer"]
            markers.extend(canaries.values())
            # Carry the wrapper canaries into evaluator metadata too, so exclusion
            # is exercised rather than merely observing an unattached intake file.
            case["provenance"]["references"].extend([*canaries.values(), FROZEN_BASELINE])
            case["semantic_signature"] += "|" + canaries["reviewed_signature"]
            self.assertEqual(case["exposure"], "exposed_regression")
            original = next(row for row in self.cases["cases"] if row["case_id"] == case["case_id"])
            self.assertEqual(case["question"], original["question"])
        oracle_ids = {case["oracle_id"] for case in cases}
        documents = {
            "cases": {"version": "p3-cases-v1", "cases": cases},
            "oracles": {"version": "p3-oracles-v1", "oracles": [
                oracle for oracle in self.oracles["oracles"] if oracle["oracle_id"] in oracle_ids
            ]},
        }
        intake = {
            "version": "p3-intake-v1", "intake_id": "SyntheticExposedWrapperIsolation",
            "candidate_freeze_sha": FROZEN_BASELINE, "state": "draft",
            "families": reviews, "owner_review_reference": None,
        }
        for name, document in documents.items():
            path = self.directory / f"exposed-{name}.json"
            AdmissionAssertions.write_json(self, path, document)
            intake[name] = {"reference": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        intake_path = self.directory / "exposed-intake.json"
        AdmissionAssertions.write_json(self, intake_path, intake)
        with patch.object(admission, "validate_review_metadata",
                          wraps=admission.validate_review_metadata) as review_validation:
            summary = admission.audit_intake(intake_path)
        self.assertEqual(summary["proposed_fresh_families"], 0)
        self.assertEqual(review_validation.call_args.kwargs["candidate_freeze_sha"], FROZEN_BASELINE)
        self.assertEqual(review_validation.call_args.args[1], reviews)

        panel_path = self.directory / "exposed-development-panel.json"
        AdmissionAssertions.write_json(self, panel_path, {
            "version": "p3-panel-v1", "panel_id": "SyntheticExposedWrapperIsolation",
            "kind": "development", "cases": intake["cases"]["reference"],
            "oracles": intake["oracles"]["reference"], "order": list(ids),
        })
        prepared = self.directory / "exposed-preparation"
        runner.prepare(self.database, prepared, panel_path=panel_path)
        sent = []
        report = await runner.run_panel(
            self.database, self.directory / "exposed-mock-run",
            manifest_path=prepared / "manifest.json", panel_path=panel_path,
            client=self.client([self.actions[case_id] for case_id in ids], sent), clock=lambda: 0.0)
        self.assertEqual((report["status"], report["panel_kind"]), ("complete", "development"))
        self.assertEqual((len(sent), report["client_http_attempts"], report["live_model_attempts"]), (2, 2, 0))
        self.assertIsNone(report["upstream_inference_attempts"])
        self.assertFalse(report["summary"]["promotion"]["eligible"])
        for marker in markers:
            self.assertIn(marker, json.dumps(report["results"]))
        for case, request, row in zip(cases, sent, report["results"], strict=True):
            direct_sent = []
            direct = await recipe_model.interpret_recipe_and_execute(
                case["question"], self.database,
                self.client([self.actions[case["case_id"]]], direct_sent), clock=lambda: 0.0)
            self.assertIsNone(direct.error)
            self.assertEqual(len(direct_sent), 1)
            self.assertEqual(request.content, direct_sent[0].content)
            wire = json.loads(request.content)
            self.assertEqual(wire["messages"], recipe_model.messages_for(case["question"]))
            self.assertEqual(wire["messages"][1], {"role": "user", "content": case["question"]})
            self.assertEqual(wire["response_format"], {
                "type": "json_schema", "json_schema": {
                    "name": GENERATION["schema_name"], "schema": recipe_model.output_schema(),
                },
            })
            self.assertEqual(assets.digest(wire["response_format"]), GENERATION["response_format_sha256"])
            self.assertEqual(
                {key: value for key, value in row["evidence"].items() if key != "analysis_pack"},
                {key: value for key, value in direct.evidence.items() if key != "analysis_pack"})
            self.assertEqual(row["actual_signature"],
                             runner.p3_grading.actual_signature(direct, case["expected_branch"]))
            if case["expected_branch"] == "answer":
                self.assertIsNotNone(row["evidence"]["analysis_pack"])
            else:
                self.assertIsNotNone(direct.presentation)
                self.assertEqual(row["evidence"]["presentation"], direct.presentation.to_dict())
            for marker in markers:
                for surface in (
                    request.content.decode(), json.dumps(wire["messages"]),
                    json.dumps(wire["response_format"]), json.dumps(row["evidence"]),
                    json.dumps(direct.evidence), json.dumps(row["evidence"]["presentation"]),
                ):
                    self.assertNotIn(marker, surface)

    async def test_existing_exposed_representative_wire_witness_remains_exactly_25250_bytes(self):
        sent = []
        result = await recipe_model.interpret_recipe_and_execute(
            EXPOSED_WIRE_WITNESS, self.database, self.client([self.actions["D01_profit.en"]], sent),
            clock=lambda: 0.0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(sent[0].content), 25250)
        wire = json.loads(sent[0].content)
        self.assertEqual(wire["messages"], recipe_model.messages_for(EXPOSED_WIRE_WITNESS))
        self.assertEqual(assets.digest(wire["response_format"]), GENERATION["response_format_sha256"])
        self.assertEqual(result.evidence["client_http_attempts"], 1)
        self.assertIsNone(result.analysis_pack)
        self.assertEqual(result.error.code, "model_declined")


if __name__ == "__main__":
    unittest.main()
