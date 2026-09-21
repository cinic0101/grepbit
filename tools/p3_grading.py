"""Observe production results against independent oracles; never repair or execute."""
from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from grepbit import (
    BreakdownAnalysisPack, CompareAnalysisPack, Fact, OverviewAnalysisPack,
)
from grepbit import grouped, kernel
from grepbit.contracts import FactRequest, KernelError, utc_text
from grepbit.model import canonical_json, normalized_request
from grepbit.presentation import ClarificationPresentation
from grepbit.recipe_model import RecipeInterpretation
from tools import recipe_smoke
from tools.p3_assets import (
    AnswerOracle, ClarifyOracle, DeclineOracle, Oracle, ROLES, digest, semantic_choices,
)

VERSION = "p3-evaluator-v1"
LAYERS = (
    "action", "recipe", "request", "execution", "coverage", "fact_selection", "values",
    "clarification_kind", "semantic_choices", "presentation", "decline_eligibility", "no_substitution",
)
_MALFORMED = {"invalid_response", "unsupported_output", "invalid_json", "invalid_request"}
_PACKS = (OverviewAnalysisPack, CompareAnalysisPack, BreakdownAnalysisPack)
_METRICS = {
    "amount": "confirmed_booked_amount", "bookings": "confirmed_booking_count", "seats": "booked_seats",
    "daily_amount": "confirmed_booked_amount", "category_amounts": "confirmed_booked_amount",
    "current": "confirmed_booked_amount", "baseline": "confirmed_booked_amount",
    "all_amount": "confirmed_booked_amount", "top_courses": "confirmed_booked_amount",
}
_DIMENSIONS = {"daily_amount": "booking_day", "category_amounts": "category", "top_courses": "course"}


def _facts(pack) -> dict:
    if isinstance(pack, OverviewAnalysisPack):
        optional = tuple(role for role in ("daily_amount", "category_amounts")
                         if any(slot.slot_id == role and slot.state != "unavailable" for slot in pack.slots))
        roles = ("amount", "bookings", "seats", *optional)
        values = (*pack.facts, *pack.grouped_facts)
    elif isinstance(pack, CompareAnalysisPack):
        roles, values = ROLES["compare"], (*pack.facts, *pack.derived_facts)
    else:
        roles = ROLES["breakdown"]
        values = (*pack.facts, *pack.grouped_facts, *pack.derived_facts)
    return dict(zip(roles, values))


def _exact(value):
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    return value


def _equal(actual, expected) -> bool:
    return canonical_json(actual) == canonical_json(expected)


def actual_signature(result: RecipeInterpretation, action: str | None) -> str | None:
    if action == "decline":
        return digest({"action": "decline"})
    if action == "clarify" and result.clarification is not None:
        return digest({"action": "clarify", **semantic_choices(result.clarification)})
    if action != "answer" or result.proposal is None:
        return None
    proposal = result.proposal
    payload = {"action": "answer", "recipe_id": proposal.recipe_id,
               "recipe_version": proposal.recipe_version,
               "request": recipe_smoke.canonical_request(proposal.request), "pack": None}
    pack = result.analysis_pack
    if isinstance(pack, _PACKS):
        facts = _facts(pack)
        role_for_id = {fact.fact_id: role for role, fact in facts.items()}
        meanings = {}
        for role, fact in facts.items():
            if role in _METRICS:
                item = {key: getattr(fact, key) for key in (
                    "metric_id", "catalog_id", "catalog_sha256", "unit", "grain", "population",
                    "time_basis", "start_utc", "end_utc",
                    "business_timezone", "filters", "empty_population",
                )}
                if isinstance(fact, Fact):
                    item.update(value=fact.value, excluded_anonymous_rows=fact.excluded_anonymous_rows)
                else:
                    item.update(dimension=fact.dimension, coverage=fact.coverage, top_k=fact.top_k,
                                rows=[{"key": row.key, "value": row.value} for row in fact.rows])
            else:
                if any(source not in role_for_id for source in fact.input_fact_ids):
                    return None
                item = {"derivation": fact.derivation, "unit": fact.unit, "state": fact.state,
                        "reason": fact.reason, "value": _exact(fact.value),
                        "input_roles": [role_for_id.get(source, "unknown") for source in fact.input_fact_ids]}
            meanings[role] = item
        if any(slot.state != "unavailable" and slot.fact_id not in role_for_id for slot in pack.slots):
            return None
        payload["pack"] = {
            "recipe_id": pack.recipe_id, "recipe_version": pack.recipe_version,
            "request": recipe_smoke.canonical_request(pack.request),
            "scope": normalized_request(pack.scope) if isinstance(
                pack, (OverviewAnalysisPack, BreakdownAnalysisPack)) else None,
            "status": pack.status, "facts": meanings,
            "slots": {slot.slot_id: {
                "fact_role": role_for_id.get(slot.fact_id), "state": slot.state, "reason": slot.reason,
                "role": "required" if isinstance(pack, CompareAnalysisPack) else slot.role,
            } for slot in pack.slots},
        }
    return digest(payload)


def _available_coverage(pack, oracle: AnswerOracle, expected: dict) -> bool:
    partial = isinstance(pack, OverviewAnalysisPack) and pack.status == "partial"
    coverage = expected["coverage"]
    if partial:
        gaps = [slot for slot in pack.slots if slot.state == "unavailable"]
        if not gaps or any(slot.role != "optional" or slot.fact_id is not None or slot.reason not in (
                "unsupported_source", "output_limit_exceeded", "component_timeout", "reconciliation_failed")
                for slot in gaps):
            return False
        coverage = {**coverage, "status": "partial", "states": [*coverage["states"], "unavailable"]}
    if pack.status == "failed" or not recipe_smoke.coverage_shape(pack, coverage):
        return False
    snapshot_id = pack.snapshot.get("id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return False
    if isinstance(pack, OverviewAnalysisPack):
        if (pack.binding.center_code != oracle.request.center_code
                or pack.binding.snapshot_id != snapshot_id or pack.binding.method != "exact_unique_code"):
            return False
    if isinstance(pack, (OverviewAnalysisPack, BreakdownAnalysisPack)):
        metrics = (("confirmed_booked_amount", "confirmed_booking_count", "booked_seats")
                   if isinstance(pack, OverviewAnalysisPack) else ("confirmed_booked_amount",))
        scope = FactRequest(metrics, oracle.request.start, oracle.request.end, oracle.request.timezone,
                            coverage["binding_center_id"] if isinstance(pack, OverviewAnalysisPack) else None)
        if normalized_request(pack.scope) != normalized_request(scope):
            return False
    for role, fact in _facts(pack).items():
        if fact.snapshot_id != snapshot_id:
            return False
        if role not in _METRICS:
            continue
        scope = (getattr(oracle.request, role) if isinstance(pack, CompareAnalysisPack)
                 and role in ("current", "baseline") else oracle.request)
        filters = {"center_id": coverage["binding_center_id"]} if isinstance(pack, OverviewAnalysisPack) else {}
        grain = "booking" if role == "bookings" else "booking_line"
        if (fact.catalog_id != "learningops-metrics-v1" or fact.catalog_sha256 != expected["catalog_sha256"]
                or fact.grain != grain
                or fact.population != "Current confirmed bookings within the explicit creation-time scope."
                or fact.time_basis != "bookings.created_at_utc"
                or (fact.start_utc, fact.end_utc) != (utc_text(scope.start), utc_text(scope.end))
                or fact.business_timezone != scope.timezone or fact.filters != filters):
            return False
        checks = kernel._CHECKS if isinstance(fact, Fact) else grouped._GROUP_CHECKS
        if not isinstance(fact.checks, tuple) or not set(checks) <= set(fact.checks):
            return False
        if isinstance(fact, Fact):
            if fact.completeness != "complete" or fact.excluded_anonymous_rows is not None:
                return False
        elif (fact.snapshot != pack.snapshot or fact.dimension_profile_id != grouped._DIMENSION_PROFILE
              or fact.ordering != grouped._ORDERING[_DIMENSIONS[role]]):
            return False
    return True


def _selection(pack) -> bool:
    if not recipe_smoke.selection_shape(pack, allow_optional_gaps=True):
        return False
    facts = _facts(pack)
    for role, fact in facts.items():
        if role in _METRICS and fact.metric_id != _METRICS[role]:
            return False
        if role in _DIMENSIONS:
            if fact.dimension != _DIMENSIONS[role]:
                return False
            if role != "top_courses" and (fact.coverage != "all_observed_groups" or fact.top_k is not None):
                return False
    if isinstance(pack, CompareAnalysisPack):
        return (
            facts["delta"].derivation == "difference"
            and facts["delta"].input_fact_ids == (facts["current"].fact_id, facts["baseline"].fact_id)
            and facts["growth"].derivation == "relative_change"
            and facts["growth"].input_fact_ids == (facts["delta"].fact_id, facts["baseline"].fact_id)
        )
    if isinstance(pack, BreakdownAnalysisPack):
        return (
            facts["top_subtotal"].derivation == "selected_subtotal"
            and facts["top_subtotal"].input_fact_ids == (facts["top_courses"].fact_id,)
            and facts["share"].derivation == "share_of_scope"
            and facts["share"].input_fact_ids == (facts["top_subtotal"].fact_id, facts["all_amount"].fact_id)
        )
    return True


def _values(pack, expected: dict) -> bool:
    if not _equal(recipe_smoke._values(pack), expected["values"]):
        return False
    facts = _facts(pack)
    for slot in pack.slots:
        if slot.state == "unavailable" and isinstance(pack, OverviewAnalysisPack) and pack.status == "partial":
            continue
        if slot.state != expected["slot_states"][slot.slot_id]:
            return False
    for role, fact in facts.items():
        if fact.unit != expected["units"][role]:
            return False
        if isinstance(fact, Fact):
            if (type(fact.population_rows) is not int or fact.population_rows < 0
                    or fact.empty_population is not (fact.population_rows == 0)
                    or fact.empty_population and not _equal(fact.value, 0 if role == "bookings" else None)
                    or not fact.empty_population and fact.value is None
                    or fact.value is not None and type(fact.value) is not int):
                return False
        elif role in _DIMENSIONS:
            if fact.empty_population is not (not fact.rows):
                return False
            if any(type(row.value) is not int for row in fact.rows):
                return False
            if role in expected["auxiliary_values"] and not _equal(
                    [{"key": row.key, "value": row.value} for row in fact.rows],
                    expected["auxiliary_values"][role]):
                return False
        else:
            if fact.state != expected["slot_states"][role]:
                return False
            if fact.state == "checked" and fact.reason is not None:
                return False
            if fact.state == "undefined" and (fact.value is not None or fact.reason != (
                    "zero_baseline" if role == "growth" else "zero_total")):
                return False
    return True


def grade(result: RecipeInterpretation | None, oracle: Oracle, *, attempted: bool = True) -> dict:
    layers = dict.fromkeys(LAYERS, "not_assessed")
    report = {"version": VERSION, "outcome": None, "actual_action": None, "layers": layers,
              "checked_wrong": False, "actual_signature": None, "operational_error": None,
              "pack_status": None, "missing_required_slots": [], "diagnostics": []}

    def observe(layer: str, operation: Callable[[], bool]) -> bool:
        try:
            passed = operation()
        except (AttributeError, TypeError, ValueError, KeyError, IndexError, KernelError):
            report["diagnostics"].append({"layer": layer, "reason": "invalid_native_shape"})
            passed = False
        layers[layer] = "passed" if passed else "failed"
        return passed

    if not attempted:
        if result is not None:
            raise ValueError("An unattempted input cannot contain a runtime result.")
        report["outcome"] = "not_run"
        return report
    if result is None:
        report["outcome"] = "operational_failure"
        report["operational_error"] = "missing_result"
        return report
    error = result.error
    pack, proposal, clarification = result.analysis_pack, result.proposal, result.clarification
    action = ("answer" if proposal is not None else "clarify" if clarification is not None else
              "decline" if error is not None and error.code == "model_declined" else None)
    report["actual_action"] = action
    if error is not None and error.code != "model_declined":
        report["operational_error"] = error.code
    if isinstance(pack, _PACKS):
        report["pack_status"] = pack.status
    if error is not None and error.code in _MALFORMED:
        report["outcome"] = "invalid_output"
        return report
    if action is None:
        report["outcome"] = "operational_failure"
        return report
    if (proposal is not None and clarification is not None
            or action != "answer" and pack is not None
            or action == "clarify" and error is not None):
        report["outcome"] = "invalid_output"
        return report
    try:
        report["actual_signature"] = actual_signature(result, action)
    except (AttributeError, TypeError, ValueError, KeyError, IndexError):
        report["diagnostics"].append({"layer": "agreement", "reason": "invalid_native_shape"})
    observe("action", lambda: action == oracle.branch)
    if isinstance(oracle, AnswerOracle) and proposal is not None:
        expected = oracle.to_dict()
        observe("recipe", lambda: (proposal.recipe_id, proposal.recipe_version) == (
            expected["recipe_id"], expected["recipe_version"]))
        observe("request", lambda: recipe_smoke.canonical_request(proposal.request) == expected["request"])
        observe("execution", lambda: error is None and isinstance(pack, _PACKS)
                and (pack.recipe_id, pack.recipe_version) == (proposal.recipe_id, proposal.recipe_version)
                and recipe_smoke.canonical_request(pack.request) == recipe_smoke.canonical_request(proposal.request))
        if isinstance(pack, _PACKS):
            observe("coverage", lambda: _available_coverage(pack, oracle, expected))
            observe("fact_selection", lambda: _selection(pack))
            observe("values", lambda: _values(pack, expected))
            report["missing_required_slots"] = [
                role for role in expected["required_slots"] if not any(
                    slot.slot_id == role and slot.state in ("checked", "undefined") for slot in pack.slots)]
    elif isinstance(oracle, ClarifyOracle) and clarification is not None:
        observe("clarification_kind", lambda: clarification.kind == oracle.clarification.kind)
        observe("semantic_choices", lambda: semantic_choices(clarification) == semantic_choices(oracle.clarification))

        def presentation_valid() -> bool:
            if result.presentation is None:
                return False
            ClarificationPresentation.from_mapping(result.presentation.to_dict(), clarification)
            return True

        observe("presentation", presentation_valid)
    elif isinstance(oracle, DeclineOracle) and action == "decline":
        observe("decline_eligibility", lambda: oracle.designated_control and oracle.capability_category != "D05")
        observe("no_substitution", lambda: proposal is None and pack is None and clarification is None
                and result.presentation is None)
    if action != oracle.branch:
        report["outcome"] = (
            "false_refusal" if oracle.branch == "answer" and action == "decline" else
            "false_clarification" if action == "clarify" and oracle.branch in ("answer", "decline") else
            "missed_clarification" if oracle.branch == "clarify" and action == "answer" else "wrong_action")
    elif isinstance(oracle, ClarifyOracle):
        report["outcome"] = "correct_clarification" if all(layers[key] == "passed" for key in (
            "clarification_kind", "semantic_choices", "presentation")) else "wrong_action"
    elif isinstance(oracle, DeclineOracle):
        report["outcome"] = "correct_decline" if all(layers[key] == "passed" for key in (
            "decline_eligibility", "no_substitution")) else "wrong_action"
    else:
        for layer, outcome in (
            ("recipe", "wrong_recipe"), ("request", "wrong_request"), ("execution", "operational_failure"),
            ("coverage", "wrong_coverage"), ("fact_selection", "wrong_fact_selection"), ("values", "wrong_value"),
        ):
            if layers[layer] != "passed":
                report["outcome"] = outcome
                break
        else:
            report["outcome"] = "partial" if report["pack_status"] == "partial" else "complete_correct"
    report["checked_wrong"] = bool(
        action == "answer" and error is None and report["pack_status"] == "complete"
        and report["outcome"] not in ("complete_correct", "partial"))
    return report
