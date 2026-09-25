#!/usr/bin/env python3
"""Fresh holdout observation runner (#79). Preparation/binding are offline; --live needs the owner's standing grant.

One observation of an independently authored, frozen holdout panel per candidate.
It is fresh evidence about the harness and the candidate, never promotion: the
panel is consumed by the run and becomes regression data afterwards.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import model
from grepbit.gateway import GatewayClient, GatewayConfig
from datetime import datetime, timezone

from tools import p3_admission as admission, p3_assets as assets, p3_eval as evaluator, p3_expectations
from tools import p3_formal_policy as allocation, p3_formal_run as formal, p3_grading, p3_live_evidence as live
from tools import recipe_smoke, smoke
from tools.evaluation_evidence import commit_terminal, stage_terminal

FREEZE_VERSION = "p3-holdout-freeze-v1"
PACKET_VERSION = "p3-holdout-live-packet-v1"
AUTHORIZATION_VERSION = "p3-holdout-live-authorization-v1"
MANIFEST_VERSION = "p3-holdout-live-manifest-v1"
REPORT_VERSION = "p3-holdout-live-report-v1"
STOP_VERSION = "p3-holdout-stops-v1"
PURPOSE = "one_fresh_holdout_observation_not_promotion"
EVIDENCE_CLASS = "fresh_holdout_observation"
POLICY = allocation.HOLDOUT_A
MAX_INPUTS = allocation._POLICIES[POLICY]["inputs"]
# The owner's standing grant lives on goal issue #79; each run binds one grant comment and one slot.
OWNER = re.compile(r"https://github\.com/cinic0101/grepbit/issues/79#issuecomment-[1-9][0-9]*")
_SLOT = re.compile(r"\.artifacts(?:/[A-Za-z0-9._-]+)+")
_TRANSPORT = formal._TRANSPORT
_PACKET_FIELDS = (formal._PACKET_FIELDS - {"preparation_assets"}) | {"evidence_class", "promotion_eligible",
                                                                     "authoring_baseline_sha"}


def settings() -> dict:
    return {**evaluator.settings(MAX_INPUTS), "execution": "owner_granted_holdout_observation_only",
            "client_fallback": 0, "resend": 0, "continuation": 0, "best_of": 0}


def stop_policy() -> dict:
    return {**evaluator.stop_policy(), "version": STOP_VERSION,
            "live": "Observed client sends count as live attempts; upstream inference attempts remain unknown.",
            "authorization": "Exact packet, Issue #79 grant reference and bound run slot required before credentials.",
            "consumption": "One observation per candidate; the panel becomes regression data after this run.",
            "replay": "No resume, retry, repair, fallback or automatic second run."}


def data_boundary() -> dict:
    return {"source": "synthetic_learningops_only", "wire": "individual_question_and_unchanged_runtime_only",
            "evaluator_metadata_on_wire": False, "raw_completion_or_reasoning_persisted": False,
            "quality_claim": "one_fresh_holdout_observation_not_promotion_or_P3_exit"}


def command_template(accepted_commit: str, policies: dict) -> list[str]:
    return [".venv/bin/python", "tools/p3_holdout_run.py", "--live",
            "--packet", "<EXACT_ACCEPTED_PACKET>", "--authorization", "<EXACT_AUTHORIZATION_ENVELOPE>",
            "--db", "<EXACT_ACCEPTED_DB>", "--accepted-commit", accepted_commit,
            "--env-file", "<EXPLICIT_LOCAL_ENV_FILE>",
            "--gateway-retries", policies["retries"], "--gateway-fallback", policies["fallback"],
            "--gateway-cache", policies["cache"], "--output-dir", "<BOUND_HOLDOUT_RUN_SLOT>"]


_same = formal._same
_hash = formal._hash


def _run_slot(path: Path) -> str:
    if not isinstance(path, Path):
        raise assets.P3Error("invalid_manifest")
    try:
        slot = path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        raise assets.P3Error("invalid_manifest") from None
    if _SLOT.fullmatch(slot) is None or any(part in (".", "..") for part in slot.split("/")):
        raise assets.P3Error("invalid_manifest")
    smoke._no_symlinks(path)
    return slot


def _reference(value) -> str:
    if not isinstance(value, str) or OWNER.fullmatch(value) is None:
        raise assets.P3Error("invalid_manifest")
    return value


def candidate_identity(accepted_commit: str, authoring_baseline_sha: str) -> dict:
    """The behavior under observation is the accepted dev commit; the P3.3 baseline is the authoring semantics."""
    return {"kind": "accepted_dev_behavior", "accepted_commit": accepted_commit,
            "authoring_baseline_sha": authoring_baseline_sha,
            "runtime_entry": "grepbit.recipe_model.interpret_recipe_and_execute"}


def _packet_contract(packet: dict) -> None:
    """Archived structural validation; never consults credentials or the current checkout."""
    assets.object_fields(packet, _PACKET_FIELDS)
    if (packet["version"] != PACKET_VERSION or packet["purpose"] != PURPOSE
            or packet["evidence_class"] != EVIDENCE_CLASS or packet["promotion_eligible"] is not False
            or packet["panel_kind"] != "holdout" or packet["evaluator_version"] != p3_grading.VERSION
            or not isinstance(packet["accepted_commit"], str) or not formal._COMMIT.fullmatch(packet["accepted_commit"])
            or packet["authoring_baseline_sha"] != admission.FROZEN_CANDIDATE
            or packet["candidate"] != candidate_identity(packet["accepted_commit"], packet["authoring_baseline_sha"])
            or packet["runtime_entry"] != "grepbit.recipe_model.interpret_recipe_and_execute"
            or packet["transport_security"] not in _TRANSPORT or packet["upstream_inference_attempts"] is not None
            or not _same(packet["settings"], settings()) or not _same(packet["stop_policy"], stop_policy())
            or packet["settings_sha256"] != assets.digest(settings())
            or packet["stop_policy_sha256"] != assets.digest(stop_policy())
            or packet["data_boundary"] != data_boundary()
            or packet["command_template"] != command_template(packet["accepted_commit"], packet["gateway_policy"])
            or packet["allocation_policy"] != allocation.identity(POLICY)):
        raise assets.P3Error("invalid_manifest")
    recipe_smoke._accepted(packet["identities"], packet["accepted_commit"])
    allocation.validate_allocation(packet["inputs"], POLICY)
    if packet["order"] != [row["case_id"] for row in packet["inputs"]] or len(packet["inputs"]) != MAX_INPUTS:
        raise assets.P3Error("invalid_manifest")
    for row in packet["inputs"]:
        assets.object_fields(row, evaluator._INPUT_FIELDS)
        _hash(row["question_sha256"])
        if row["exposure"] != "frozen_fresh":
            raise assets.P3Error("invalid_manifest")
        assets.Provenance.from_mapping(row["provenance"], row["exposure"])
    formal._pin_fields(packet["freeze"])
    for pin in assets.object_fields(packet["assets"], {"cases", "oracles", "panel"}, "invalid_manifest").values():
        formal._pin_fields(pin)
    locations = assets.object_fields(packet["locations"], {"freeze"}, "invalid_manifest")
    if any(not isinstance(value, str) or not value for value in locations.values()):
        raise assets.P3Error("invalid_manifest")
    _hash(packet["database_sha256"])
    if not isinstance(packet["gateway_policy"], dict) or packet["gateway_policy"] != smoke.policy_attestation(
            {key: packet["gateway_policy"].get(key) for key in smoke.POLICY_KEYS}, required=True):
        raise assets.P3Error("invalid_manifest")


def _freeze_payload(database: Path, intake_path: Path, panel_path: Path, *, accepted_commit: str,
                    frozen_at: str) -> tuple[dict, assets.Panel]:
    """Holdout freeze bound to the accepted dev commit; the P3.3 formal freeze pins an older candidate snapshot."""
    panel, intake = admission._policy_materials(intake_path, panel_path, POLICY)
    frozen_time = admission._timestamp(frozen_at)
    if frozen_time > datetime.now(timezone.utc) or any(
            admission._timestamp(item["reviewed_at"]) > frozen_time for item in intake["families"]):
        raise assets.P3Error("invalid_asset")
    source = evaluator._source_identity(panel, None)
    recipe_smoke._accepted(source, accepted_commit)
    inputs = panel.inputs()
    allocation.validate_allocation(inputs, POLICY)
    representatives = {item["family_id"]: item for item in inputs}
    payload = {
        "version": FREEZE_VERSION, "state": "frozen", "frozen_at": frozen_at,
        "purpose": "holdout_observation_freeze", "allocation_policy": allocation.identity(POLICY),
        "authoring_baseline_sha": intake["candidate_freeze_sha"], "accepted_commit": accepted_commit,
        "candidate": candidate_identity(accepted_commit, intake["candidate_freeze_sha"]),
        "panel_id": panel.panel_id, "panel_version": assets.PANEL_VERSION,
        "assets": {name: evaluator._pin(path) for name, path in {
            "intake": intake_path, "panel": panel_path,
            "cases": panel.cases_path, "oracles": panel.oracles_path,
        }.items()},
        "order": [case.case_id for case in panel.cases], "inputs": inputs,
        "families": [{**review, "semantic_signature": representatives[review["family_id"]]["semantic_signature"],
                      "provenance": [item["provenance"] for item in inputs
                                     if item["family_id"] == review["family_id"]]}
                     for review in intake["families"]],
        "owner_review_reference": intake["owner_review_reference"],
        "source_identity": source, "database_sha256": smoke._fixture_identity(database),
        "evaluator_version": p3_grading.VERSION, "evidence_expectations": p3_expectations.identity(),
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "execution": "not_admitted", "live_model_attempts": 0,
    }
    return payload, panel


def freeze_holdout(database: Path, intake_path: Path, panel_path: Path, output_dir: Path, *,
                   accepted_commit: str) -> dict:
    started = time.monotonic()
    frozen_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload, panel = _freeze_payload(database, intake_path, panel_path,
                                     accepted_commit=accepted_commit, frozen_at=frozen_at)
    sources = {"intake": intake_path, "panel": panel_path, "cases": panel.cases_path, "oracles": panel.oracles_path}
    if len({admission._reference(path.name) for path in sources.values()}) != len(sources):
        raise assets.P3Error("invalid_asset")
    artifacts = smoke._Artifacts(output_dir, {
        "version": FREEZE_VERSION, "state": "incomplete", "planned_sha256": assets.digest(payload),
    })
    artifacts.persist({"version": FREEZE_VERSION, "state": "incomplete",
                       "planned_sha256": assets.digest(payload), "live_model_attempts": 0})
    for name, source in sources.items():
        admission._snapshot(artifacts, source, payload["assets"][name])

    def validate() -> None:
        for pin in payload["assets"].values():
            if evaluator._pin(output_dir / pin["reference"]) != pin:
                raise assets.P3Error("manifest_drift")
        current, _ = _freeze_payload(database, intake_path, panel_path,
                                     accepted_commit=accepted_commit, frozen_at=frozen_at)
        if current != payload:
            raise assets.P3Error("manifest_drift")

    pending, target = stage_terminal(
        artifacts, payload, validate=validate, remaining=lambda: 60.0 - (time.monotonic() - started))
    commit_terminal(pending, target)
    return payload


def load_holdout_freeze(freeze_path: Path, database: Path, *, accepted_commit: str) -> tuple[dict, assets.Panel]:
    """Recompute the frozen payload from the snapshotted assets on the accepted dev commit."""
    payload = assets.read_asset(freeze_path)
    header = assets.object_fields(assets.read_asset(freeze_path.parent / "manifest.json"),
                                  {"version", "state", "planned_sha256"})
    if (payload.get("version") != FREEZE_VERSION or payload.get("state") != "frozen"
            or header != {"version": FREEZE_VERSION, "state": "incomplete", "planned_sha256": assets.digest(payload)}
            or payload.get("accepted_commit") != accepted_commit):
        raise assets.P3Error("invalid_manifest")
    try:
        pins = assets.object_fields(payload["assets"], {"intake", "panel", "cases", "oracles"})
        for pin in pins.values():
            assets.object_fields(pin, {"reference", "sha256"})
            if evaluator._pin(freeze_path.parent / admission._reference(pin["reference"])) != pin:
                raise assets.P3Error("manifest_drift")
        expected, panel = _freeze_payload(
            database, freeze_path.parent / pins["intake"]["reference"],
            freeze_path.parent / pins["panel"]["reference"],
            accepted_commit=accepted_commit, frozen_at=payload["frozen_at"])
    except (LookupError, TypeError):
        raise assets.P3Error("invalid_manifest") from None
    if expected != payload:
        raise assets.P3Error("manifest_drift")
    return payload, panel


def build_packet(database: Path, *, freeze_path: Path, accepted_commit: str,
                 gateway_policies: dict, transport_security: str) -> tuple[dict, assets.Panel]:
    """Exact offline preparation from a frozen holdout panel; no execution admission."""
    if transport_security not in _TRANSPORT:
        raise assets.P3Error("invalid_configuration")
    frozen, panel = load_holdout_freeze(freeze_path, database, accepted_commit=accepted_commit)
    packet = {
        "version": PACKET_VERSION, "purpose": PURPOSE, "evidence_class": EVIDENCE_CLASS,
        "promotion_eligible": False, "accepted_commit": accepted_commit,
        "authoring_baseline_sha": frozen["authoring_baseline_sha"],
        "candidate": candidate_identity(accepted_commit, frozen["authoring_baseline_sha"]),
        "locations": {"freeze": str(freeze_path.absolute())},
        "freeze": evaluator._pin(freeze_path),
        "assets": {key: frozen["assets"][key] for key in ("cases", "oracles", "panel")},
        "panel_id": panel.panel_id, "panel_kind": "holdout", "order": frozen["order"], "inputs": frozen["inputs"],
        "allocation_policy": frozen["allocation_policy"], "evaluator_version": p3_grading.VERSION,
        "identities": frozen["source_identity"], "database_sha256": frozen["database_sha256"],
        "runtime_entry": "grepbit.recipe_model.interpret_recipe_and_execute",
        "settings": settings(), "settings_sha256": assets.digest(settings()),
        "stop_policy": stop_policy(), "stop_policy_sha256": assets.digest(stop_policy()),
        "gateway_policy": smoke.policy_attestation(gateway_policies, required=True),
        "transport_security": transport_security, "data_boundary": data_boundary(),
        "upstream_inference_attempts": None,
        "command_template": command_template(accepted_commit, gateway_policies),
    }
    _packet_contract(packet)
    return packet, panel


def validate_packet(path: Path, database: Path, *, accepted_commit: str) -> tuple[dict, assets.Panel]:
    packet = assets.read_asset(path)
    _packet_contract(packet)
    if packet["accepted_commit"] != accepted_commit:
        raise assets.P3Error("accepted_commit_required")
    current, panel = build_packet(database, freeze_path=Path(packet["locations"]["freeze"]),
                                 accepted_commit=accepted_commit,
                                 gateway_policies={key: packet["gateway_policy"][key] for key in smoke.POLICY_KEYS},
                                 transport_security=packet["transport_security"])
    if not _same(packet, current):
        raise assets.P3Error("manifest_drift")
    return packet, panel


def prepare(database: Path, output_dir: Path, **options) -> dict:
    packet, _ = build_packet(database, **options)
    artifacts = smoke._Artifacts(output_dir, packet)
    report = {"version": PACKET_VERSION, "state": "incomplete", "packet_sha256": evaluator._pin(
        output_dir / "manifest.json")["sha256"], "client_http_attempts": 0, "live_model_attempts": 0}
    artifacts.persist(report)
    validate_packet(output_dir / "manifest.json", database, accepted_commit=packet["accepted_commit"])
    report["state"] = "prepared_not_authorized"
    artifacts.persist(report)
    return report


def _authorization(value: dict, packet_sha: str) -> dict:
    """The envelope binds the packet, the owner's #79 grant comment and exactly one run slot."""
    assets.object_fields(value, {"version", "packet_sha256", "owner_authorization_reference", "run_slot"})
    if value["version"] != AUTHORIZATION_VERSION or value["packet_sha256"] != packet_sha:
        raise assets.P3Error("invalid_manifest")
    _hash(packet_sha)
    _reference(value["owner_authorization_reference"])
    slot = value["run_slot"]
    if (not isinstance(slot, str) or _SLOT.fullmatch(slot) is None
            or any(part in (".", "..") for part in slot.split("/"))):
        raise assets.P3Error("invalid_manifest")
    return value


def _validate_run_slot(authorization: dict, output_dir: Path) -> None:
    if authorization["run_slot"] != _run_slot(output_dir):
        raise assets.P3Error("invalid_manifest")


def bind_authorization(packet_path: Path, reference: str, output_path: Path, run_output_dir: Path) -> dict:
    packet = assets.read_asset(packet_path)
    _packet_contract(packet)
    digest = evaluator._pin(packet_path)["sha256"]
    value = _authorization({"version": AUTHORIZATION_VERSION, "packet_sha256": digest,
                            "owner_authorization_reference": reference,
                            "run_slot": _run_slot(run_output_dir)}, digest)
    live._write_authorization(output_path, value)
    return value


def _manifest(packet: dict, packet_sha: str, authorization: dict, authorization_sha: str) -> dict:
    return {
        "manifest_version": MANIFEST_VERSION, "packet_sha256": packet_sha,
        "authorization_sha256": authorization_sha,
        "owner_authorization_reference": authorization["owner_authorization_reference"],
        "run_slot": authorization["run_slot"],
        "accepted_commit": packet["accepted_commit"], "evaluator_version": p3_grading.VERSION,
        "panel_id": packet["panel_id"], "panel_kind": "holdout", "inputs": packet["inputs"],
        "order": packet["order"], "allocation_policy": packet["allocation_policy"],
        "settings": packet["settings"], "settings_sha256": packet["settings_sha256"],
        "stop_policy": packet["stop_policy"], "stop_policy_sha256": packet["stop_policy_sha256"],
        "evidence_class": EVIDENCE_CLASS, "promotion_eligible": False,
        "preparation": {"kind": "accepted", "accepted_commit": packet["accepted_commit"]},
    }


def _report(manifest: dict, packet: dict) -> dict:
    report = evaluator._new_report(manifest, "live")
    report.update(report_version=REPORT_VERSION, runtime_invocations=0, transport_security=None,
                  gateway_policy=packet["gateway_policy"],
                  owner_authorization_reference=manifest["owner_authorization_reference"],
                  run_slot=manifest["run_slot"], evidence_class=EVIDENCE_CLASS, promotion_eligible=False,
                  scope="One fresh holdout observation of the frozen holdout panel; the panel is regression "
                        "data afterwards. Not promotion, stability or P3 exit evidence.")
    for row in report["results"]:
        row["phase"] = "not_started"
    return report


class _LiveEvidence(live._LiveEvidence):
    maximum = MAX_INPUTS


def _entries(panel, packet):
    return evaluator._panel_entries(panel)


def _expected_model(packet):
    """The holdout runner keeps the default 31B LiteLLM identity, like the formal runner."""
    _packet_contract(packet)
    return None


async def run_live(database: Path, output_dir: Path, *, packet_path: Path, authorization_path: Path,
                   accepted_commit: str, env_file: Path, gateway_policies: dict,
                   clock=time.monotonic) -> dict:
    return await live._run_live(database, output_dir, packet_path=packet_path, authorization_path=authorization_path,
                                accepted_commit=accepted_commit, env_file=env_file,
                                gateway_policies=gateway_policies, clock=clock, contract=sys.modules[__name__])


def read_report(path: Path) -> dict:
    """Offline archive verification; no current checkout, DB or configuration access."""
    packet = assets.read_asset(path.parent / "packet.json")
    _packet_contract(packet)
    packet_sha = evaluator._pin(path.parent / "packet.json")["sha256"]
    authorization = _authorization(assets.read_asset(path.parent / "authorization.json"), packet_sha)
    _validate_run_slot(authorization, path.parent)
    expected_manifest = _manifest(packet, packet_sha, authorization,
                                  evaluator._pin(path.parent / "authorization.json")["sha256"])
    manifest = assets.read_asset(path.parent / "manifest.json")
    if not _same(manifest, expected_manifest):
        raise assets.P3Error("invalid_manifest")
    report = evaluator._document(path, evaluator.MAX_REPORT_BYTES, "invalid_asset")
    expected = _report(manifest, packet)
    live._validate_report(report, manifest, expected, packet["inputs"], maximum=MAX_INPUTS,
                          transport_security=packet["transport_security"])
    for key in ("run_slot", "evidence_class", "promotion_eligible"):
        if not _same(report[key], expected[key]):
            raise assets.P3Error("invalid_asset")
    if report["summary"]["panel_kind"] != "holdout" or report["summary"]["promotion"]["eligible"] is not False:
        raise assets.P3Error("invalid_asset")
    return report


def main(argv=None) -> int:
    parser = evaluator._Parser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("freeze-holdout", "prepare", "bind-authorization", "live", "report"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("packet", "authorization", "db", "env-file", "output-dir", "output", "run-output-dir",
                 "freeze", "intake", "panel", "report-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--accepted-commit")
    parser.add_argument("--owner-authorization-reference")
    parser.add_argument("--transport-security", choices=_TRANSPORT)
    for name in smoke.POLICY_KEYS:
        parser.add_argument("--gateway-" + name, choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        present = {key for key, value in vars(args).items() if value is not None and value is not False}
        common = {"db", "accepted_commit", "gateway_retries", "gateway_fallback", "gateway_cache", "output_dir"}
        allowed = ({"freeze_holdout", "intake", "panel", "db", "output_dir", "accepted_commit"} if args.freeze_holdout
                   else {"prepare", "freeze", "transport_security"} | common if args.prepare else
                   {"bind_authorization", "packet", "owner_authorization_reference", "output", "run_output_dir"}
                   if args.bind_authorization else {"live", "packet", "authorization", "env_file"} | common
                   if args.live else {"report", "report_path"})
        if present != allowed:
            raise assets.P3Error("invalid_arguments")
        policies = {key: getattr(args, "gateway_" + key) for key in smoke.POLICY_KEYS}
        if args.freeze_holdout:
            payload = freeze_holdout(args.db, args.intake, args.panel, args.output_dir,
                                     accepted_commit=args.accepted_commit)
            result = {key: payload[key] for key in ("version", "state", "panel_id", "accepted_commit",
                                                    "authoring_baseline_sha", "database_sha256")}
            result["inputs"] = len(payload["inputs"])
        elif args.prepare:
            result = prepare(args.db, args.output_dir, freeze_path=args.freeze,
                             accepted_commit=args.accepted_commit, gateway_policies=policies,
                             transport_security=args.transport_security)
        elif args.bind_authorization:
            result = bind_authorization(args.packet, args.owner_authorization_reference, args.output,
                                        args.run_output_dir)
        else:
            if args.live:
                asyncio.run(run_live(args.db, args.output_dir, packet_path=args.packet,
                                     authorization_path=args.authorization, accepted_commit=args.accepted_commit,
                                     env_file=args.env_file, gateway_policies=policies))
            report = read_report(args.output_dir / "report.json" if args.live else args.report_path)
            result = {key: report[key] for key in (
                "report_version", "status", "stop_reason", "error_code", "client_http_attempts",
                "live_model_attempts", "runtime_invocations", "possible_in_flight_attempts",
                "upstream_inference_attempts", "transport_security", "evidence_class", "promotion_eligible",
                "summary")}
        print(model.canonical_json(result))
        return 0 if result.get("status") in (None, "complete") else 1
    except evaluator._SAFE_ERRORS as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (OSError, *evaluator._INTERNAL_ERRORS):
        print('{"status":"incomplete","error_code":"invalid_manifest"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
