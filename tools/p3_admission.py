"""Offline independent-author intake and freeze; never author fresh content or execute models."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit.model import canonical_json
from grepbit.contracts import KernelError
from tools import p3_assets as assets, p3_eval, p3_expectations, p3_formal_policy, p3_scoring, recipe_smoke, smoke
from tools.evaluation_evidence import commit_terminal, stage_terminal

INTAKE_VERSION = "p3-intake-v1"
FREEZE_VERSION = "p3-formal-freeze-v1"
POLICY_FREEZE_VERSION = "p3-formal-freeze-v2"
PROBE_VERSION = "p3-compatibility-preparation-v1"
FROZEN_CANDIDATE = "20abb5592262c77c98f9cabeaf7cf4854edb6fbe"
FREEZE_DECLARED_AT = "2026-09-21T06:32:04Z"
PROTOCOL = ROOT / "docs/p3-fresh-case-authoring.md"
CHECKLIST = (
    "distinct_requirements", "not_paraphrase_or_translation", "not_parameter_only",
    "supported_frozen_capability", "independent_gold", "ancestry_reviewed", "language_equivalence",
)
_FROZEN_TOOLS = (
    "tools/p3_assets.py", "tools/p3_grading.py", "tools/p3_scoring.py",
    "tools/p3_expectations.py", "tools/recipe_smoke.py", "tools/smoke.py",
    "tools/evaluation_evidence.py", "requirements.txt",
)
_SHA = re.compile(r"[0-9a-f]{64}")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise assets.P3Error("invalid_asset")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise assets.P3Error("invalid_asset") from None
    if parsed.tzinfo != timezone.utc:
        raise assets.P3Error("invalid_asset")
    return parsed


def _reference(value: object) -> str:
    name = assets.text(value, 128)
    if (Path(name).name != name or any(char in name for char in ("\x00", "/", "\\"))
            or not name.endswith(".json")
            or name in ("manifest.json", "report.json", "terminal-candidate.json", "terminal.next.json")
            or name.startswith(("checkpoint-", ".pending"))):
        raise assets.P3Error("invalid_asset")
    return name


def _nonblank(value: object, maximum: int) -> str:
    result = assets.text(value, maximum)
    if not result.strip():
        raise assets.P3Error("invalid_asset")
    return result


def _actor(value: object, roles: tuple[str, ...]) -> dict:
    actor = assets.object_fields(value, {"role", "reference"})
    if actor["role"] not in roles:
        raise assets.P3Error("invalid_asset")
    _nonblank(actor["reference"], 256)
    return actor


def validate_review_metadata(inputs: list[dict], reviews: list[dict], *, state: str,
                             candidate_freeze_sha: str, owner_review_reference: str | None,
                             now: datetime | None = None) -> dict:
    """Validate reviewer assertions and obvious duplicates, not human novelty or blindness."""
    if candidate_freeze_sha != FROZEN_CANDIDATE or state not in ("draft", "novelty_reviewed"):
        raise assets.P3Error("invalid_panel")
    if (not isinstance(inputs, list) or not 1 <= len(inputs) <= assets.MAX_INPUTS
            or not isinstance(reviews, list) or not 1 <= len(reviews) <= assets.MAX_INPUTS):
        raise assets.P3Error("invalid_panel")
    if owner_review_reference is not None:
        _nonblank(owner_review_reference, 512)
    now = now or datetime.now(timezone.utc)
    groups = p3_scoring._inputs_by_family(inputs, "invalid_panel")
    declared = [variants[0]["semantic_signature"] for variants in groups.values()]
    if len(set(declared)) != len(declared):
        raise assets.P3Error("invalid_panel")
    reviewed, signatures = set(), set()
    ready = owner_review_reference is not None
    eligible = True
    fresh_count = 0
    for review in reviews:
        item = assets.object_fields(review, {
            "family_id", "case_ids", "author", "reviewer", "authored_at", "reviewed_at",
            "ancestry", "novelty_rationale", "reviewed_signature", "checklist",
            "implementer_visible_before_run",
        })
        family = assets.text(item["family_id"], identifier=True)
        if family in reviewed or family not in groups:
            raise assets.P3Error("invalid_panel")
        reviewed.add(family)
        variants = groups[family]
        if set(assets.strings(item["case_ids"], maximum=assets.MAX_INPUTS)) != {
                row["case_id"] for row in variants}:
            raise assets.P3Error("invalid_panel")
        if len({row["exposure"] for row in variants}) != 1:
            raise assets.P3Error("invalid_panel")
        signature = _nonblank(item["reviewed_signature"], 1024)
        if signature in signatures:
            raise assets.P3Error("invalid_panel")
        signatures.add(signature)
        author = _actor(item["author"], ("independent_author", "historical_curator", "implementation_author"))
        reviewer = _actor(item["reviewer"], ("independent_reviewer",))
        if author["reference"] == reviewer["reference"]:
            raise assets.P3Error("invalid_asset")
        authored = _timestamp(item["authored_at"])
        reviewed_at = None if item["reviewed_at"] is None else _timestamp(item["reviewed_at"])
        if authored > now or reviewed_at is not None and not authored <= reviewed_at <= now:
            raise assets.P3Error("invalid_asset")
        ancestry = assets.strings(item["ancestry"])
        if not ancestry or any(not reference.strip() for reference in ancestry):
            raise assets.P3Error("invalid_asset")
        _nonblank(item["novelty_rationale"], 2048)
        checks = assets.object_fields(item["checklist"], set(CHECKLIST))
        if any(type(value) is not bool for value in checks.values()):
            raise assets.P3Error("invalid_asset")
        visible = item["implementer_visible_before_run"]
        if type(visible) is not bool:
            raise assets.P3Error("invalid_asset")
        for row in variants:
            provenance = assets.Provenance.from_mapping(row["provenance"], row["exposure"])
            if provenance.seen_by_implementer != visible:
                raise assets.P3Error("invalid_asset")
        fresh = variants[0]["exposure"] == "frozen_fresh"
        if fresh:
            fresh_count += 1
            if author["role"] != "independent_author" or visible or authored <= _timestamp(FREEZE_DECLARED_AT):
                raise assets.P3Error("formal_not_admitted")
        ready = ready and all(checks.values()) and reviewed_at is not None
        eligible = eligible and all(checks.values())
    if reviewed != set(groups):
        raise assets.P3Error("invalid_panel")
    if state == "novelty_reviewed" and not ready:
        raise assets.P3Error("formal_not_admitted")
    return {
        "state": state, "family_count": len(groups), "input_count": len(inputs),
        "proposed_fresh_families": fresh_count,
        "eligible_for_fresh_review": bool(eligible), "review_assertions_complete": bool(ready),
        "semantic_novelty": "requires_independent_reviewer_and_owner_acceptance",
    }


def _intake(path: Path) -> tuple[dict, tuple[assets.Case, ...], tuple[assets.Oracle, ...], dict]:
    data = assets.object_fields(assets.read_asset(path), {
        "version", "intake_id", "candidate_freeze_sha", "state", "cases", "oracles",
        "families", "owner_review_reference",
    })
    if data["version"] != INTAKE_VERSION:
        raise assets.P3Error("invalid_asset")
    assets.text(data["intake_id"], identifier=True)
    documents = []
    names = {_reference(path.name)}
    for field, version in (("cases", assets.CASE_VERSION), ("oracles", assets.ORACLE_VERSION)):
        reference = assets.object_fields(data[field], {"reference", "sha256"})
        name = _reference(reference["reference"])
        if name in names or not isinstance(reference["sha256"], str) or not _SHA.fullmatch(reference["sha256"]):
            raise assets.P3Error("invalid_asset")
        names.add(name)
        source = path.parent / name
        if p3_eval._pin(source)["sha256"] != reference["sha256"]:
            raise assets.P3Error("manifest_drift")
        document = assets.object_fields(assets.read_asset(source), {"version", field})
        if (document["version"] != version or not isinstance(document[field], list)
                or not 1 <= len(document[field]) <= assets.MAX_INPUTS):
            raise assets.P3Error("invalid_asset")
        documents.append(document[field])
    cases = tuple(assets.Case.from_mapping(item) for item in documents[0])
    oracles = tuple(assets.parse_oracle(item) for item in documents[1])
    by_oracle = {oracle.oracle_id: oracle for oracle in oracles}
    if (len({case.case_id for case in cases}) != len(cases) or len(by_oracle) != len(oracles)
            or {case.oracle_id for case in cases} != set(by_oracle)):
        raise assets.P3Error("invalid_panel")
    meanings: dict[str, str] = {}
    families: dict[str, tuple] = {}
    for case in cases:
        oracle = by_oracle[case.oracle_id]
        if oracle.branch != case.expected_branch or isinstance(oracle, assets.DeclineOracle) and not oracle.designated_control:
            raise assets.P3Error("invalid_panel")
        if isinstance(oracle, assets.ClarifyOracle):
            try:
                oracle.clarification.validate_question(case.question)
            except KernelError:
                raise assets.P3Error("invalid_panel") from None
        meaning = assets.digest(oracle.meaning)
        if meaning in meanings and meanings[meaning] != case.family_id:
            raise assets.P3Error("invalid_panel")
        meanings[meaning] = case.family_id
        family = (case.semantic_signature, case.exposure, case.cohort, case.expected_branch,
                  case.must_pass, case.observational, meaning)
        if case.family_id in families and families[case.family_id] != family:
            raise assets.P3Error("invalid_panel")
        families[case.family_id] = family
    inputs = [case.metadata(index, data["cases"]["reference"]) for index, case in enumerate(cases, 1)]
    summary = validate_review_metadata(
        inputs, data["families"], state=data["state"], candidate_freeze_sha=data["candidate_freeze_sha"],
        owner_review_reference=data["owner_review_reference"])
    return data, cases, oracles, summary


def audit_intake(path: Path) -> dict:
    _, _, _, summary = _intake(path)
    return {**summary, "intake": p3_eval._pin(path), "live_model_attempts": 0}


def candidate_identity() -> dict:
    """Compare current behavior sources to the declared Git snapshot without executing it."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "ls-tree", "-r", "--name-only", FROZEN_CANDIDATE, "--", "grepbit"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=5,
        )
        runtime_paths = tuple(result.stdout.splitlines())
        current_paths = tuple(sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "grepbit").rglob("*.py")))
        if not runtime_paths or tuple(sorted(runtime_paths)) != current_paths:
            raise assets.P3Error("source_identity_failure")
        hashes = {}
        for name in (*runtime_paths, *_FROZEN_TOOLS):
            accepted = subprocess.run(
                ["git", "--no-optional-locks", "show", f"{FROZEN_CANDIDATE}:{name}"],
                cwd=ROOT, capture_output=True, check=True, timeout=5,
            ).stdout
            expected = smoke._digest(accepted)
            if p3_eval._pin(ROOT / name)["sha256"] != expected:
                raise assets.P3Error("source_identity_failure")
            hashes[name] = expected
    except (OSError, subprocess.SubprocessError):
        raise assets.P3Error("source_identity_failure") from None
    return {
        "candidate_freeze_sha": FROZEN_CANDIDATE, "declared_at": FREEZE_DECLARED_AT,
        "declaration": "https://github.com/cinic0101/grepbit/issues/43",
        "files_sha256": hashes, "evidence_expectations": p3_expectations.identity(),
    }


def _formal_materials(intake_path: Path, panel_path: Path) -> tuple[assets.Panel, dict]:
    data, cases, _, summary = _intake(intake_path)
    if data["state"] != "novelty_reviewed" or not summary["review_assertions_complete"]:
        raise assets.P3Error("formal_not_admitted")
    panel = assets.load_panel(panel_path)
    if (panel.kind != "formal" or {case.case_id for case in panel.cases} != {case.case_id for case in cases}
            or p3_eval._pin(panel.cases_path) != data["cases"]
            or p3_eval._pin(panel.oracles_path) != data["oracles"]):
        raise assets.P3Error("invalid_panel")
    p3_scoring.validate_formal_allocation(panel.inputs())
    return panel, data


def _policy_materials(intake_path: Path, panel_path: Path, allocation_policy: str | None) -> tuple[assets.Panel, dict]:
    if allocation_policy is None:
        return _formal_materials(intake_path, panel_path)
    p3_formal_policy.identity(allocation_policy)
    if allocation_policy == p3_formal_policy.V1:
        return _formal_materials(intake_path, panel_path)
    # Native intake is the shared oracle/meaning/branch/review validator. Do not
    # rewrite a formal payload as development or modify the frozen asset loader.
    data, cases, oracles, summary = _intake(intake_path)
    if data["state"] != "novelty_reviewed" or not summary["review_assertions_complete"]:
        raise assets.P3Error("formal_not_admitted")
    item = assets.object_fields(assets.read_asset(panel_path),
                                {"version", "panel_id", "kind", "cases", "oracles", "order"}, "invalid_panel")
    if item["version"] != assets.PANEL_VERSION or item["kind"] != "formal":
        raise assets.P3Error("invalid_panel")
    paths = [panel_path.parent / _reference(item[name]) for name in ("cases", "oracles")]
    if any(p3_eval._pin(path) != data[name] for name, path in zip(("cases", "oracles"), paths)):
        raise assets.P3Error("manifest_drift")
    order = assets.strings(item["order"], maximum=assets.MAX_INPUTS)
    by_id = {case.case_id: case for case in cases}
    if len(order) != len(cases) or set(order) != set(by_id):
        raise assets.P3Error("invalid_panel")
    panel = assets.Panel(assets.text(item["panel_id"], identifier=True), "formal",
                         tuple(by_id[name] for name in order), oracles, panel_path, *paths)
    p3_formal_policy.validate_allocation(panel.inputs(), allocation_policy)
    return panel, data


def _freeze_payload(database: Path, intake_path: Path, panel_path: Path, *,
                    accepted_commit: str, frozen_at: str, allocation_policy: str | None = None) -> dict:
    panel, intake = _policy_materials(intake_path, panel_path, allocation_policy)
    frozen_time = _timestamp(frozen_at)
    if frozen_time > datetime.now(timezone.utc) or any(
            _timestamp(item["reviewed_at"]) > frozen_time for item in intake["families"]):
        raise assets.P3Error("invalid_asset")
    source = p3_eval._source_identity(panel, None)
    recipe_smoke._accepted(source, accepted_commit)
    inputs = panel.inputs()
    representatives = {item["family_id"]: item for item in inputs}
    limits, policy = p3_eval.settings(len(inputs)), p3_eval.stop_policy()
    payload = {
        "version": FREEZE_VERSION if allocation_policy is None else POLICY_FREEZE_VERSION,
        "state": "frozen", "frozen_at": frozen_at,
        "candidate": candidate_identity(), "accepted_tooling_commit": accepted_commit,
        "panel_id": panel.panel_id, "panel_version": assets.PANEL_VERSION,
        "assets": {name: p3_eval._pin(path) for name, path in {
            "intake": intake_path, "panel": panel_path,
            "cases": panel.cases_path, "oracles": panel.oracles_path,
        }.items()},
        "order": [case.case_id for case in panel.cases],
        "allocation": {
            "families": len(representatives), "inputs": len(inputs),
            "family_cohorts": dict(Counter(item["cohort"] for item in representatives.values())),
            "input_cohorts": dict(Counter(item["cohort"] for item in inputs)),
            "family_exposures": dict(Counter(item["exposure"] for item in representatives.values())),
            "input_exposures": dict(Counter(item["exposure"] for item in inputs)),
            "languages": dict(Counter(item["language"] for item in inputs)),
        },
        "families": [{**review, "semantic_signature": representatives[review["family_id"]]["semantic_signature"],
                      "provenance": [item["provenance"] for item in inputs
                                     if item["family_id"] == review["family_id"]]}
                     for review in intake["families"]],
        "owner_review_reference": intake["owner_review_reference"],
        "source_identity": source, "database_sha256": smoke._fixture_identity(database),
        "evaluator_version": p3_eval.p3_grading.VERSION,
        "evidence_expectations": p3_expectations.identity(), "authoring_protocol": p3_eval._pin(PROTOCOL),
        "settings": limits, "settings_sha256": assets.digest(limits),
        "stop_policy": policy, "stop_policy_sha256": assets.digest(policy),
        "execution": "not_admitted", "live_model_attempts": 0,
    }
    if allocation_policy is not None:
        payload["allocation_policy"] = p3_formal_policy.identity(allocation_policy)
    return payload


def _snapshot(artifacts, source: Path, expected: dict) -> None:
    """Retain submitted bytes; the existing JSON writer would change their hashes."""
    name = _reference(expected["reference"])
    try:
        smoke._no_symlinks(source)
        with source.open("rb") as stream:
            raw = stream.read(assets.MAX_ASSET_BYTES + 1)
        if len(raw) > assets.MAX_ASSET_BYTES or smoke._digest(raw) != expected["sha256"]:
            raise assets.P3Error("manifest_drift")
        fd = os.open(artifacts.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise assets.P3Error("artifact_conflict") from None
    except OSError:
        raise assets.P3Error("artifact_io") from None


def freeze_panel(database: Path, intake_path: Path, panel_path: Path, output_dir: Path, *,
                 accepted_commit: str, allocation_policy: str | None = None) -> dict:
    started = time.monotonic()
    frozen_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _freeze_payload(database, intake_path, panel_path,
                              accepted_commit=accepted_commit, frozen_at=frozen_at, allocation_policy=allocation_policy)
    panel = (_policy_materials(intake_path, panel_path, allocation_policy)[0]
             if allocation_policy is not None else assets.load_panel(panel_path))
    sources = {"intake": intake_path, "panel": panel_path,
               "cases": panel.cases_path, "oracles": panel.oracles_path}
    if len({_reference(path.name) for path in sources.values()}) != len(sources):
        raise assets.P3Error("invalid_asset")
    artifacts = smoke._Artifacts(output_dir, {
        "version": payload["version"], "state": "incomplete", "planned_sha256": assets.digest(payload),
    })
    artifacts.persist({"version": payload["version"], "state": "incomplete",
                       "planned_sha256": assets.digest(payload), "live_model_attempts": 0})
    for name, source in sources.items():
        _snapshot(artifacts, source, payload["assets"][name])

    def validate() -> None:
        for pin in payload["assets"].values():
            if p3_eval._pin(output_dir / pin["reference"]) != pin:
                raise assets.P3Error("manifest_drift")
        current = _freeze_payload(database, intake_path, panel_path,
                                  accepted_commit=accepted_commit, frozen_at=frozen_at, allocation_policy=allocation_policy)
        if current != payload:
            raise assets.P3Error("manifest_drift")

    pending, target = stage_terminal(
        artifacts, payload, validate=validate, remaining=lambda: 60.0 - (time.monotonic() - started))
    commit_terminal(pending, target)
    return payload


def _frozen_policy(payload: dict) -> str | None:
    if payload.get("version") == FREEZE_VERSION and "allocation_policy" not in payload:
        return None  # Historical envelope means v1, never inferred from its row count.
    if payload.get("version") == POLICY_FREEZE_VERSION:
        return p3_formal_policy.validate_identity(payload.get("allocation_policy"))
    raise assets.P3Error("invalid_manifest")


def validate_freeze(path: Path, database: Path, panel_path: Path, *, accepted_commit: str) -> dict:
    payload = assets.read_asset(path)
    allocation_policy = _frozen_policy(payload)
    header = assets.object_fields(assets.read_asset(path.parent / "manifest.json"),
                                  {"version", "state", "planned_sha256"})
    if (payload.get("state") != "frozen"
            or header != {"version": payload["version"], "state": "incomplete",
                          "planned_sha256": assets.digest(payload)}):
        raise assets.P3Error("invalid_manifest")
    try:
        pins = assets.object_fields(payload["assets"], {"intake", "panel", "cases", "oracles"})
        for pin in pins.values():
            assets.object_fields(pin, {"reference", "sha256"})
            if p3_eval._pin(path.parent / _reference(pin["reference"])) != pin:
                raise assets.P3Error("manifest_drift")
        if p3_eval._pin(panel_path) != pins["panel"]:
            raise assets.P3Error("manifest_drift")
        expected = _freeze_payload(
            database, path.parent / pins["intake"]["reference"],
            path.parent / pins["panel"]["reference"], accepted_commit=accepted_commit,
            frozen_at=payload["frozen_at"], allocation_policy=allocation_policy)
        if expected != payload:
            raise assets.P3Error("manifest_drift")
        result = {"version": payload["version"], "sha256": assets.digest(payload),
                  "candidate_freeze_sha": FROZEN_CANDIDATE}
        if allocation_policy is not None:
            result["allocation_policy"] = p3_formal_policy.identity(allocation_policy)
        return result
    except (LookupError, TypeError):
        raise assets.P3Error("invalid_manifest") from None


def load_frozen_panel(path: Path, database: Path, panel_path: Path, *, accepted_commit: str) -> tuple[assets.Panel, dict | None]:
    verified = validate_freeze(path, database, panel_path, accepted_commit=accepted_commit)
    pin = verified.get("allocation_policy")
    if pin is None:
        return assets.load_panel(panel_path), None
    payload = assets.read_asset(path)
    panel, _ = _policy_materials(path.parent / _reference(payload["assets"]["intake"]["reference"]),
                                 panel_path, p3_formal_policy.validate_identity(pin))
    return panel, pin


def prepare_probe(database: Path, output_dir: Path, *, accepted_commit: str | None = None) -> dict:
    panel = assets.load_panel(p3_eval.DEFAULT_PANEL)
    source = p3_eval._source_identity(panel, None)
    if accepted_commit is not None:
        recipe_smoke._accepted(source, accepted_commit)
    candidates = [case for case in panel.cases if case.family_id == "E01_overview" and case.language == "en"]
    if len(candidates) != 1 or candidates[0].exposure != "exposed_regression":
        raise assets.P3Error("invalid_panel")
    case = candidates[0]
    limits = p3_eval.settings(1)
    payload = {
        "version": PROBE_VERSION, "state": "prepared", "candidate": candidate_identity(),
        "source_identity": source, "authoring_protocol": p3_eval._pin(PROTOCOL),
        "preparation": {"kind": "accepted" if accepted_commit is not None else "candidate",
                        "accepted_commit": accepted_commit},
        "database_sha256": smoke._fixture_identity(database),
        "question_sha256": case.metadata(1, panel.cases_path.name)["question_sha256"],
        "question_reference": {"asset": panel.cases_path.as_posix(), "case_id": case.case_id, "field": "question"},
        "exposure": case.exposure, "future_provider_route": "owner-local LiteLLM / gemma-4-31b",
        "runtime_entry": "grepbit.recipe_model.interpret_recipe_and_execute",
        "settings": limits, "settings_sha256": assets.digest(limits),
        "max_future_client_http_attempts": 1, "retries": 0, "repairs": 0, "fallbacks": 0,
        "purpose": "Provider/structured-output compatibility only; not quality or promotion.",
        "stop_conditions": [
            "After the single attempt, whether success or failure; never resend.",
            "Configuration, source/DB/schema drift, privacy, deadline or resource failure.",
            "HTTP/provider envelope, strict JSON or typed action incompatibility.",
        ],
        "execution": "not_admitted", "owner_authorization_required": True,
        "upstream_inference_attempts": None, "upstream_retry_policy": "requires_owner_attestation_before_live",
        "scored_run_authorization": "Separate gate after compatibility-probe review.",
        "client_http_attempts": 0, "live_model_attempts": 0,
    }
    artifacts = smoke._Artifacts(output_dir, payload)
    if (p3_eval._source_identity(panel, None) != source
            or candidate_identity() != payload["candidate"]
            or assets.load_panel(p3_eval.DEFAULT_PANEL) != panel
            or p3_eval._pin(PROTOCOL) != payload["authoring_protocol"]
            or smoke._fixture_identity(database) != payload["database_sha256"]):
        raise assets.P3Error("manifest_drift")
    artifacts._write("report.json", {"version": PROBE_VERSION, "state": "prepared",
                                   "manifest_sha256": assets.digest(payload),
                                   "client_http_attempts": 0, "live_model_attempts": 0})
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = p3_eval._Parser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "freeze", "probe-prepare"))
    parser.add_argument("--intake", type=Path)
    parser.add_argument("--panel", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--allocation-policy", choices=p3_formal_policy.VERSIONS)
    try:
        args = parser.parse_args(argv)
        if args.mode == "audit":
            if args.intake is None or args.panel or args.db or args.output_dir or args.accepted_commit or args.allocation_policy:
                raise assets.P3Error("invalid_arguments")
            result = audit_intake(args.intake)
        elif args.mode == "freeze":
            if any(value is None for value in (args.intake, args.panel, args.db, args.output_dir, args.accepted_commit)):
                raise assets.P3Error("invalid_arguments")
            result = freeze_panel(args.db, args.intake, args.panel, args.output_dir,
                                  accepted_commit=args.accepted_commit,
                                  allocation_policy=args.allocation_policy or p3_formal_policy.V1)
        else:
            if args.db is None or args.output_dir is None or args.intake or args.panel or args.allocation_policy:
                raise assets.P3Error("invalid_arguments")
            result = prepare_probe(args.db, args.output_dir, accepted_commit=args.accepted_commit)
        print(canonical_json({key: result[key] for key in (
            "state", "family_count", "input_count", "proposed_fresh_families",
            "eligible_for_fresh_review", "review_assertions_complete", "live_model_attempts",
        ) if key in result}))
        return 0
    except (assets.P3Error, smoke.SmokeError, recipe_smoke.RecipeSmokeError) as exc:
        print(canonical_json({"state": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt,):
        print('{"state":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, LookupError, RecursionError):
        print('{"state":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
