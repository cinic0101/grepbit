"""Closed evaluator-only assets; none of this metadata is a runtime input."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from typing import NoReturn

from grepbit.breakdown import BreakdownRequest
from grepbit.clarification import Clarification, CountBasis, MetricMeaning
from grepbit.contracts import KernelError
from grepbit.gateway import ModelError
from grepbit.model import canonical_json, strict_json
from tools import recipe_smoke

CASE_VERSION = "p3-cases-v1"
ORACLE_VERSION = "p3-oracles-v1"
PANEL_VERSION = "p3-panel-v1"
EXPOSURES = ("exposed_regression", "design_seen", "frozen_fresh")
LANGUAGES = ("zh-TW", "en", "ja")
BRANCHES = ("answer", "clarify", "decline")
COHORTS = ("answer", "clarify", "decline", "anchor")
OUTCOMES = (
    "complete_correct", "false_refusal", "false_clarification", "missed_clarification",
    "wrong_action", "correct_clarification", "correct_decline", "wrong_recipe",
    "wrong_request", "wrong_coverage", "wrong_fact_selection", "wrong_value",
    "partial", "invalid_output", "operational_failure", "not_run", "synthesis_error",
)
ROLES = {
    "overview": ("amount", "bookings", "seats", "daily_amount", "category_amounts"),
    "compare": ("current", "baseline", "delta", "growth"),
    "breakdown": ("all_amount", "top_courses", "top_subtotal", "share"),
}
MAX_ASSET_BYTES = 1_048_576
MAX_INPUTS = 64
CATALOG_SHA256 = "9027e2af35e49a790fd4c3e985ccff12e92868946f9398506ccfa7e623c897c5"
SAFE_CODES = recipe_smoke.SAFE_CODES | {
    "invalid_asset", "invalid_oracle", "invalid_panel", "invalid_scoring",
    "formal_not_admitted", "live_not_admitted", "invalid_fake_script",
}


class P3Error(Exception):
    def __init__(self, code: str):
        self.code = code if code in SAFE_CODES else "internal_failure"
        super().__init__(self.code)


def invalid(code: str = "invalid_asset") -> NoReturn:
    raise P3Error(code)


def object_fields(value: object, fields: set[str], code: str = "invalid_asset") -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        invalid(code)
    return value


def text(value: object, maximum: int = 1024, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        invalid()
    try:
        if len(value.encode("utf-8")) > maximum:
            invalid()
    except UnicodeError:
        invalid()
    if identifier and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,95}", value) is None:
        invalid()
    return value


def strings(value: object, *, maximum: int = 16, unique: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        invalid()
    result = tuple(text(item) for item in value)
    if unique and len(set(result)) != len(result):
        invalid()
    return result


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def read_asset(path: Path) -> dict:
    try:
        recipe_smoke.smoke._no_symlinks(path)
        with path.open("rb") as stream:
            raw = stream.read(MAX_ASSET_BYTES + 1)
        if len(raw) > MAX_ASSET_BYTES:
            invalid()
        result = strict_json(raw)
        if not isinstance(result, dict):
            invalid()
        return result
    except (OSError, ValueError, ModelError, recipe_smoke.smoke.SmokeError):
        raise P3Error("invalid_asset") from None


@dataclass(frozen=True, repr=False)
class Provenance:
    origin: str
    references: tuple[str, ...]
    seen_by_implementer: bool
    exposure_history: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: object, exposure: str) -> Provenance:
        item = object_fields(data, {"origin", "references", "seen_by_implementer", "exposure_history"})
        origin = text(item["origin"])
        references = strings(item["references"])
        history = strings(item["exposure_history"], unique=False)
        seen = item["seen_by_implementer"]
        if (origin not in ("historical", "development", "independent") or not references
                or type(seen) is not bool or not history or history[-1] != exposure
                or any(label not in EXPOSURES for label in history)):
            invalid()
        if origin == "historical" and exposure != "exposed_regression":
            invalid()
        if exposure == "frozen_fresh" and (
                origin != "independent" or seen or any(label != "frozen_fresh" for label in history)):
            invalid()
        if exposure == "design_seen" and "exposed_regression" in history:
            invalid()
        exposure_rank = {"frozen_fresh": 0, "design_seen": 1, "exposed_regression": 2}
        if any(exposure_rank[later] < exposure_rank[earlier] for earlier, later in zip(history, history[1:])):
            invalid()
        return cls(origin, references, seen, history)

    def to_dict(self) -> dict:
        return {"origin": self.origin, "references": list(self.references),
                "seen_by_implementer": self.seen_by_implementer,
                "exposure_history": list(self.exposure_history)}


@dataclass(frozen=True, repr=False)
class Case:
    case_id: str
    family_id: str
    question: str
    language: str
    expected_branch: str
    cohort: str
    exposure: str
    provenance: Provenance
    semantic_signature: str
    must_pass: bool
    observational: bool
    oracle_id: str

    @classmethod
    def from_mapping(cls, data: object) -> Case:
        fields = set(cls.__dataclass_fields__)
        item = object_fields(data, fields)
        for name in ("case_id", "family_id", "oracle_id"):
            text(item[name], identifier=True)
        text(item["question"], 4096)
        text(item["semantic_signature"])
        for name, allowed in (("language", LANGUAGES), ("expected_branch", BRANCHES),
                              ("cohort", COHORTS), ("exposure", EXPOSURES)):
            if not isinstance(item[name], str) or item[name] not in allowed:
                invalid()
        if (type(item["must_pass"]) is not bool or type(item["observational"]) is not bool
                or item["must_pass"] == item["observational"]
                or item["expected_branch"] != ("answer" if item["cohort"] == "anchor" else item["cohort"])):
            invalid()
        provenance = Provenance.from_mapping(item["provenance"], item["exposure"])
        return cls(**{**item, "provenance": provenance})

    def metadata(self, order: int, reference: str) -> dict:
        return {
            "order": order, "case_id": self.case_id, "family_id": self.family_id,
            "language": self.language, "expected_branch": self.expected_branch, "cohort": self.cohort,
            "exposure": self.exposure, "provenance": self.provenance.to_dict(),
            "semantic_signature": self.semantic_signature, "must_pass": self.must_pass,
            "observational": self.observational, "oracle_id": self.oracle_id,
            "question_sha256": hashlib.sha256(self.question.encode()).hexdigest(),
            "question_reference": {"asset": reference, "case_id": self.case_id, "field": "question"},
        }


def _number(value: object, *, rational: bool = False) -> None:
    if value is None or not rational and type(value) is int and -(2**63) <= value < 2**63:
        return
    if rational and isinstance(value, dict) and set(value) == {"numerator", "denominator"}:
        numerator, denominator = value["numerator"], value["denominator"]
        if type(numerator) is int and type(denominator) is int and denominator > 0:
            exact = Fraction(numerator, denominator)
            if (exact.numerator, exact.denominator) == (numerator, denominator):
                return
    invalid("invalid_oracle")


def _rows(value: object) -> None:
    if not isinstance(value, list) or len(value) > 200:
        invalid("invalid_oracle")
    keys = []
    for row in value:
        row = object_fields(row, {"key", "value"}, "invalid_oracle")
        if row["key"] is not None:
            text(row["key"], 256)
        if type(row["value"]) is not int or not 0 <= row["value"] < 2**63:
            invalid("invalid_oracle")
        keys.append(row["key"])
    if len(set(keys)) != len(keys):
        invalid("invalid_oracle")


@dataclass(frozen=True, repr=False)
class AnswerOracle:
    oracle_id: str
    revision: int
    payload: str
    request: recipe_smoke._Request
    branch: str = "answer"

    def to_dict(self) -> dict:
        return json.loads(self.payload)

    @property
    def meaning(self) -> dict:
        data = self.to_dict()
        return {key: value for key, value in data.items()
                if key not in ("oracle_id", "revision", "provenance")}


@dataclass(frozen=True, repr=False)
class ClarifyOracle:
    oracle_id: str
    revision: int
    payload: str
    clarification: Clarification
    branch: str = "clarify"

    def to_dict(self) -> dict:
        return json.loads(self.payload)

    @property
    def meaning(self) -> dict:
        return {"branch": self.branch, "clarification": semantic_choices(self.clarification)}


@dataclass(frozen=True, repr=False)
class DeclineOracle:
    oracle_id: str
    revision: int
    payload: str
    designated_control: bool
    capability_category: str
    branch: str = "decline"

    def to_dict(self) -> dict:
        return json.loads(self.payload)

    @property
    def meaning(self) -> dict:
        return {"branch": self.branch, "designated_control": self.designated_control,
                "capability_category": self.capability_category}


Oracle = AnswerOracle | ClarifyOracle | DeclineOracle


def semantic_choices(clarification: Clarification) -> dict:
    alternatives = []
    for choice in clarification.choices:
        value = choice.semantic_value
        raw = value.to_dict()
        if isinstance(value, (CountBasis, MetricMeaning)):
            raw["scope"] = recipe_smoke.canonical_request(value.scope)
        else:
            raw["request"] = recipe_smoke.canonical_request(value.request)
        alternatives.append(canonical_json(raw))
    return {"kind": clarification.kind, "alternatives": sorted(alternatives)}


def parse_oracle(data: object) -> Oracle:
    if not isinstance(data, dict):
        invalid("invalid_oracle")
    common = {"oracle_id", "revision", "branch", "provenance"}
    try:
        name = text(data.get("oracle_id"), identifier=True)
        revision = data.get("revision")
        if type(revision) is not int or revision < 1:
            invalid("invalid_oracle")
        if not strings(data.get("provenance")):
            invalid("invalid_oracle")
        branch = data.get("branch")
        if branch == "clarify":
            object_fields(data, common | {"clarification"}, "invalid_oracle")
            clarification = Clarification.from_mapping(data["clarification"])
            return ClarifyOracle(name, revision, canonical_json(data), clarification)
        if branch == "decline":
            object_fields(data, common | {"designated_control", "capability_category"}, "invalid_oracle")
            control, category = data["designated_control"], data["capability_category"]
            if (type(control) is not bool or not isinstance(category, str)
                    or category not in ("D01", "D02", "D03", "D04", "D05", "D06")
                    or category == "D05" and control):
                invalid("invalid_oracle")
            return DeclineOracle(name, revision, canonical_json(data), control, category)
        if branch != "answer":
            invalid("invalid_oracle")
        object_fields(data, common | {
            "recipe_id", "recipe_version", "request", "coverage", "values", "required_slots",
            "auxiliary_slots", "auxiliary_values", "slot_states", "units", "catalog_sha256",
        }, "invalid_oracle")
        recipe = data["recipe_id"]
        if not isinstance(recipe, str) or recipe not in ROLES or data["recipe_version"] != "0.1":
            invalid("invalid_oracle")
        request = recipe_smoke._expected_request(recipe, data["request"])
        expected = {**data, "request": recipe_smoke.canonical_request(request)}
        roles = set(ROLES[recipe])
        required, auxiliary = strings(data["required_slots"]), strings(data["auxiliary_slots"])
        if not required or set(required) & set(auxiliary) or set(required) | set(auxiliary) != roles:
            invalid("invalid_oracle")
        coverage = object_fields(data["coverage"], {"status", "slots", "states"} | (
            {"binding_center_id"} if recipe == "overview" else {"group"} if recipe == "breakdown" else set()),
            "invalid_oracle")
        if (coverage["status"] not in ("complete", "partial", "failed")
                or not isinstance(coverage["slots"], dict) or set(coverage["slots"]) != roles
                or coverage["slots"] != {role: "optional" if recipe == "overview" and role in (
                    "daily_amount", "category_amounts") else "required" for role in ROLES[recipe]}
                or not isinstance(coverage["states"], list) or not coverage["states"]
                or any(state not in ("checked", "undefined", "unavailable") for state in coverage["states"])):
            invalid("invalid_oracle")
        if recipe == "overview":
            text(coverage["binding_center_id"], 64)
        if recipe == "breakdown":
            group = object_fields(coverage["group"], {"dimension", "coverage", "top_k"}, "invalid_oracle")
            if not isinstance(request, BreakdownRequest) or type(group["top_k"]) is not int or group != {
                    "dimension": "course", "coverage": "top_k", "top_k": request.top_k}:
                invalid("invalid_oracle")
        slot_states = object_fields(data["slot_states"], roles, "invalid_oracle")
        if any(not isinstance(value, str) or value not in ("checked", "undefined", "unavailable")
               for value in slot_states.values()):
            invalid("invalid_oracle")
        units = object_fields(data["units"], roles, "invalid_oracle")
        for value in units.values():
            text(value, 64)
        if data["catalog_sha256"] != CATALOG_SHA256:
            invalid("invalid_oracle")
        value_keys = ({"amount", "bookings", "seats"} if recipe == "overview" else
                      {"current", "baseline", "delta", "growth"} if recipe == "compare" else
                      {"rows", "all_amount", "top_subtotal", "share"})
        values = object_fields(data["values"], value_keys, "invalid_oracle")
        for key, value in values.items():
            if key == "rows":
                _rows(value)
            else:
                _number(value, rational=key in ("growth", "share"))
        auxiliary_values = object_fields(data["auxiliary_values"], {
            "daily_amount", "category_amounts"} if recipe == "overview" else set(), "invalid_oracle")
        for value in auxiliary_values.values():
            _rows(value)
        return AnswerOracle(name, revision, canonical_json(expected), request)
    except (P3Error, KernelError, recipe_smoke.RecipeSmokeError, TypeError, ValueError):
        raise P3Error("invalid_oracle") from None


@dataclass(frozen=True, repr=False)
class Panel:
    panel_id: str
    kind: str
    cases: tuple[Case, ...]
    oracles: tuple[Oracle, ...]
    path: Path
    cases_path: Path
    oracles_path: Path

    def oracle_for(self, case: Case) -> Oracle:
        for oracle in self.oracles:
            if oracle.oracle_id == case.oracle_id:
                return oracle
        invalid("invalid_panel")

    def inputs(self) -> list[dict]:
        return [case.metadata(index, self.cases_path.name) for index, case in enumerate(self.cases, 1)]


def load_panel(path: Path) -> Panel:
    item = object_fields(read_asset(path), {"version", "panel_id", "kind", "cases", "oracles", "order"},
                         "invalid_panel")
    if item["version"] != PANEL_VERSION or item["kind"] not in ("development", "formal"):
        invalid("invalid_panel")
    name = text(item["panel_id"], identifier=True)
    files = []
    for key in ("cases", "oracles"):
        relative = text(item[key], 128)
        if (Path(relative).name != relative or any(char in relative for char in ("\x00", "/", "\\"))
                or relative in (".", "..") or not relative.endswith(".json")):
            invalid("invalid_panel")
        files.append(path.parent / relative)
    cases_path, oracles_path = files
    raw_cases = object_fields(read_asset(cases_path), {"version", "cases"})
    raw_oracles = object_fields(read_asset(oracles_path), {"version", "oracles"})
    if (raw_cases["version"] != CASE_VERSION or raw_oracles["version"] != ORACLE_VERSION
            or not isinstance(raw_cases["cases"], list) or not 1 <= len(raw_cases["cases"]) <= MAX_INPUTS
            or not isinstance(raw_oracles["oracles"], list) or not 1 <= len(raw_oracles["oracles"]) <= MAX_INPUTS):
        invalid("invalid_panel")
    cases = tuple(Case.from_mapping(case) for case in raw_cases["cases"])
    oracles = tuple(parse_oracle(oracle) for oracle in raw_oracles["oracles"])
    order = strings(item["order"], maximum=MAX_INPUTS)
    if (len({case.case_id for case in cases}) != len(cases) or len(order) != len(cases)
            or set(order) != {case.case_id for case in cases}
            or len({oracle.oracle_id for oracle in oracles}) != len(oracles)
            or {case.oracle_id for case in cases} != {oracle.oracle_id for oracle in oracles}):
        invalid("invalid_panel")
    by_id = {case.case_id: case for case in cases}
    panel = Panel(name, item["kind"], tuple(by_id[name] for name in order), oracles,
                  path, cases_path, oracles_path)
    families, signatures = {}, {}
    for case in panel.cases:
        oracle = panel.oracle_for(case)
        if (oracle.branch != case.expected_branch
                or isinstance(oracle, DeclineOracle) and not oracle.designated_control
                or panel.kind == "development" and case.exposure == "frozen_fresh"):
            invalid("invalid_panel")
        if isinstance(oracle, ClarifyOracle):
            try:
                oracle.clarification.validate_question(case.question)
            except KernelError:
                raise P3Error("invalid_panel") from None
        family = (case.expected_branch, case.cohort, case.exposure, case.semantic_signature,
                  case.must_pass, case.observational, digest(oracle.meaning))
        if case.family_id in families and families[case.family_id] != family:
            invalid("invalid_panel")
        families[case.family_id] = family
        if case.semantic_signature in signatures and signatures[case.semantic_signature] != case.family_id:
            invalid("invalid_panel")
        signatures[case.semantic_signature] = case.family_id
    if panel.kind == "formal":
        from tools.p3_scoring import validate_formal_allocation
        validate_formal_allocation(panel.inputs())
    return panel
