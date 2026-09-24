"""One-shot compatibility only. --live needs separate owner authorization; default never sends."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import math
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from grepbit import model
from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError, _ERRORS
from grepbit.recipe_model import interpret_recipe_and_execute
from tools import p3_admission as admission, p3_assets as assets, p3_eval, recipe_smoke, smoke
from tools.evaluation_evidence import commit_terminal, stage_terminal

VERSION = "p3-compatibility-probe-v1"
CASE_ID = "E01_overview.en"
QUESTION_SHA256 = "634a6e868a355af50ee7ca122282776aab6159573b16b5bd19f0277b4c67e57a"
CALL_SECONDS = 60.0
PUBLICATION_SECONDS = 180.0
_CODES = assets.SAFE_CODES | set(_ERRORS) | {
    "invalid_probe", "attempt_limit", "invalid_evidence", "single_attempt_complete",
}
_SAFE_ERRORS = (assets.P3Error, smoke.SmokeError, recipe_smoke.RecipeSmokeError, ModelError)
_INTERNAL = recipe_smoke._INTERNAL_ERRORS
_STATES = ("not_run", "passed", "failed")
_COMPAT_STATES = (*_STATES, "unknown")
_COMPATIBILITY = ("transport", "envelope", "response_format", "strict_json", "typed_action", "request_size")


class ProbeError(Exception):
    def __init__(self, code: str):
        self.code = code if code in _CODES else "internal_failure"
        super().__init__(self.code)


def runner_identity() -> dict:
    return {"version": VERSION, "sha256": p3_eval._pin(Path(__file__))["sha256"]}


def validate_plan(path: Path, database: Path, *, accepted_commit: str) -> tuple[dict, str]:
    """Exact reconstruction, not permissive field/row-count admission. No config access."""
    try:
        if not isinstance(accepted_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", accepted_commit):
            raise ProbeError("accepted_commit_required")
        prepared = assets.read_asset(path)
        current = admission.build_probe_plan(database, accepted_commit=accepted_commit)
        # Canonical comparison also distinguishes bool/int values and unknown fields.
        if model.canonical_json(prepared) != model.canonical_json(current):
            raise ProbeError("manifest_drift")
        if (current["preparation"] != {"kind": "accepted", "accepted_commit": accepted_commit}
                or current["question_reference"]["case_id"] != CASE_ID
                or current["question_sha256"] != QUESTION_SHA256
                or current["source_identity"]["files_sha256"].get("tools/p3_probe.py")
                != runner_identity()["sha256"]):
            raise ProbeError("invalid_probe")
        panel = assets.load_panel(p3_eval.DEFAULT_PANEL)
        cases = [case for case in panel.cases if case.case_id == CASE_ID]
        if (len(cases) != 1 or cases[0].family_id != "E01_overview" or cases[0].language != "en"
                or cases[0].exposure != "exposed_regression"
                or smoke._digest(cases[0].question.encode()) != current["question_sha256"]):
            raise ProbeError("manifest_drift")
        return current, cases[0].question
    except _SAFE_ERRORS as exc:
        raise ProbeError(exc.code) from None
    except _INTERNAL:
        raise ProbeError("invalid_probe") from None


def live_client(env_file: Path | None) -> GatewayClient:
    if not isinstance(env_file, Path):
        raise ProbeError("invalid_configuration")
    smoke._no_symlinks(env_file)
    return GatewayClient(GatewayConfig.from_env(env_file=env_file))


class _SingleAttempt:
    """One-use delegation guard, not another transport/config/runtime implementation."""
    def __init__(self, client: GatewayClient, before_send=None):
        self.client = client
        self.used = False
        self.before_send = before_send

    @property
    def config(self):
        return self.client.config

    @property
    def http_attempts(self):
        return self.client.http_attempts

    def safe_export(self, data):
        return self.client.safe_export(data)

    async def complete(self, *args, **kwargs):
        if self.used or self.http_attempts != 0:
            raise ProbeError("attempt_limit")
        self.used = True
        if self.before_send is not None:
            self.before_send()
        return await self.client.complete(*args, **kwargs)


def _report(manifest: dict, origin: str) -> dict:
    return {
        "version": VERSION, "manifest_sha256": assets.digest(manifest),
        "status": "incomplete", "origin": origin, "identity": None,
        "gateway_policy": smoke.policy_attestation(), "transport_security": None,
        "reservation": "not_reserved", "possible_in_flight_attempts": 0,
        "attempt_budget_used": 0, "runtime_invocations": 0,
        "client_http_attempts": 0, "live_model_attempts": 0, "upstream_inference_attempts": None,
        "compatibility": dict.fromkeys(_COMPATIBILITY, "not_run"),
        "runtime_stages": dict.fromkeys(model.STAGES, "not_run"),
        "requested_model": MODEL, "observed_model": None, "http_status": None, "http_class": "not_run",
        "usage": dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens")),
        "elapsed_seconds": None, "error_code": None, "stop_reason": None,
        "compatibility_passed": False,
    }


def _safe(report: dict, client: GatewayClient | None) -> dict:
    if client is not None and client.safe_export(report) != report:
        raise ProbeError("leakage_risk")
    return report


def _result(report: dict, result, client: GatewayClient, *, expected_alias: str = MODEL) -> None:
    """Project only closed interface evidence. Never persist actions, packs or diagnostics."""
    evidence = result.evidence
    stages = evidence.get("stages")
    if (not isinstance(stages, dict) or set(stages) != set(model.STAGES)
            or any(value not in _STATES for value in stages.values())
            or type(evidence.get("client_http_attempts")) is not int
            or evidence["client_http_attempts"] != client.http_attempts):
        raise ProbeError("invalid_evidence")
    status = evidence.get("http_status")
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ProbeError("invalid_evidence")
    code = result.error.code if result.error else None
    if code is not None and code not in _CODES:
        raise ProbeError("invalid_evidence")
    report["runtime_stages"] = dict(stages)
    report["http_status"] = status
    report["http_class"] = "http_success" if status == 200 else "http_failure" if status else "no_response"
    report["observed_model"] = expected_alias if evidence.get("returned_model") == expected_alias else None
    usage = evidence.get("usage")
    if isinstance(usage, dict):
        for key in report["usage"]:
            value = usage.get(key)
            if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
                raise ProbeError("invalid_evidence")
            report["usage"][key] = value
    compat = report["compatibility"]
    for target, source in (("transport", "transport"), ("envelope", "response_validation"),
                           ("strict_json", "json_parse"), ("typed_action", "request_validation")):
        compat[target] = stages[source]
    # A 200 response demonstrates route acceptance, not provider schema enforcement.
    compat["response_format"] = "passed" if status == 200 else "unknown" if client.http_attempts else "not_run"
    compat["request_size"] = ("passed" if status == 200 else "failed" if code == "input_too_large" or status == 413
                              else "unknown" if client.http_attempts else "not_run")
    report["error_code"] = code
    report["stop_reason"] = code or "single_attempt_complete"
    report["compatibility_passed"] = code is None and client.http_attempts == 1 and all(v == "passed" for v in compat.values())


class _LegacyProbe:
    """Private caller policy; the new candidate caller supplies its own admission."""
    def __init__(self, plan_path, accepted_commit):
        self.path, self.accepted_commit = plan_path, accepted_commit

    def budgets(self):
        return CALL_SECONDS, PUBLICATION_SECONDS

    def manifest(self):
        manifest = {"version": VERSION, "runner": runner_identity(), "plan_sha256": None,
                    "accepted_commit": self.accepted_commit if isinstance(self.accepted_commit, str)
                    and re.fullmatch(r"[0-9a-f]{40}", self.accepted_commit) else None}
        try:
            manifest["plan_sha256"] = p3_eval._pin(self.path)["sha256"]
        except _SAFE_ERRORS + _INTERNAL:
            pass
        return manifest

    def report(self, manifest, origin):
        return _report(manifest, origin)

    def validate(self, database):
        return validate_plan(self.path, database, accepted_commit=self.accepted_commit)

    def identity(self, plan):
        return {
            "candidate_freeze_sha": plan["candidate"]["candidate_freeze_sha"],
            "source_identity": plan["source_identity"], "database_sha256": plan["database_sha256"],
            "case_id": CASE_ID, "question_sha256": plan["question_sha256"],
            "question_reference": plan["question_reference"], "runtime_entry": plan["runtime_entry"],
            "settings_sha256": plan["settings_sha256"],
        }

    def snapshot(self, artifacts, plan):
        pass

    def client(self, env_file):
        return live_client(env_file)

    def check_client(self, client, policies):
        if client.config.model != MODEL or client.config.expected_model is not None:
            raise ProbeError("invalid_configuration")

    def project(self, report, result, client):
        _result(report, result, client)

    def unchanged(self, manifest, plan, database):
        current, _ = self.validate(database)
        if current != plan or self.manifest() != manifest:
            raise ProbeError("manifest_drift")


async def _run_probe(database: Path, output_dir: Path, *, contract,
                     origin: str, client: GatewayClient | None,
                     gateway_policies: dict | None, env_file: Path | None, clock) -> dict:
    """Private one-shot lifecycle shared by two closed admission callers, never a CLI."""
    if origin not in ("mock", "live"):
        raise ProbeError("invalid_configuration")
    call_seconds, publication_seconds = contract.budgets()
    started = clock()
    # Do not copy unvalidated plan/config values into evidence, including path strings.
    manifest = contract.manifest()
    artifacts = smoke._Artifacts(output_dir, manifest)
    report = contract.report(manifest, origin)
    artifacts.persist(report)
    active_client = None

    def unchanged():
        if assets.read_asset(output_dir / "manifest.json") != manifest:
            raise ProbeError("manifest_drift")
        contract.unchanged(manifest, plan, database)

    def elapsed():
        value = clock() - started
        if not math.isfinite(value) or value < 0:
            raise ProbeError("invalid_configuration")
        return value

    def before_send():
        unchanged()
        if elapsed() >= publication_seconds - call_seconds:
            raise ProbeError("panel_budget")

    try:
        plan, question = contract.validate(database)
        unchanged()
        contract.snapshot(artifacts, plan)
        report["identity"] = contract.identity(plan)
        report["gateway_policy"] = smoke.policy_attestation(gateway_policies, required=True)
        unchanged()  # Snapshot/identity drift must stop before any env/config access.
        if origin == "live":
            if client is not None:
                raise ProbeError("invalid_configuration")
            active_client = contract.client(env_file)
        else:
            if (env_file is not None or not isinstance(client, GatewayClient)
                    or not isinstance(client._transport, httpx.MockTransport)):
                raise ProbeError("invalid_configuration")
            if client.http_attempts != 0:
                raise ProbeError("attempt_limit")
            active_client = client
        if active_client.http_attempts != 0:
            raise ProbeError("attempt_limit")
        contract.check_client(active_client, report["gateway_policy"])
        report["transport_security"] = active_client.config.transport_security
        unchanged()
        if elapsed() >= publication_seconds - call_seconds:
            raise ProbeError("panel_budget")
        report.update(status="running", reservation="in_progress", possible_in_flight_attempts=1,
                      attempt_budget_used=1)
        artifacts.persist(_safe(report, active_client))
        unchanged()
        if elapsed() >= publication_seconds - call_seconds:
            raise ProbeError("panel_budget")
        report["runtime_invocations"] = 1
        artifacts.persist(_safe(report, active_client))
        async with asyncio.timeout(call_seconds):
            result = await interpret_recipe_and_execute(
                question, database, _SingleAttempt(active_client, before_send), timeout_seconds=call_seconds, clock=clock)
        if type(active_client.http_attempts) is not int or active_client.http_attempts not in (0, 1):
            raise ProbeError("attempt_limit")
        contract.project(report, result, active_client)
        report.update(reservation="settled", possible_in_flight_attempts=0)
        unchanged()
    except (KeyboardInterrupt, asyncio.CancelledError):
        report.update(status="incomplete", error_code="interrupted", stop_reason="interrupted",
                      compatibility_passed=False)
    except TimeoutError:
        report.update(status="stopped", error_code="timeout", stop_reason="timeout", compatibility_passed=False)
    except (ProbeError, *_SAFE_ERRORS) as exc:
        report.update(status="stopped", error_code=exc.code, stop_reason=exc.code, compatibility_passed=False)
    except _INTERNAL:
        report.update(status="incomplete", error_code="internal_failure", stop_reason="internal_failure",
                      compatibility_passed=False)
    else:
        report["status"] = "complete" if report["compatibility_passed"] else "stopped"
    if active_client is not None:
        report["client_http_attempts"] = active_client.http_attempts
        report["live_model_attempts"] = active_client.http_attempts if origin == "live" else 0
    try:
        report["elapsed_seconds"] = round(elapsed(), 6)
        if report["status"] != "complete":
            artifacts.persist(_safe(report, active_client))
            return report
        terminal = deepcopy(report)
        # A complete report becomes visible only at the terminal commit point.
        report.update(status="incomplete", compatibility_passed=False)
        artifacts.persist(_safe(report, active_client))
        pending, target = stage_terminal(
            artifacts, _safe(terminal, active_client), validate=unchanged,
            remaining=lambda: publication_seconds - elapsed())
    except (KeyboardInterrupt, asyncio.CancelledError):
        report.update(status="incomplete", error_code="interrupted", stop_reason="interrupted", compatibility_passed=False)
    except (ProbeError, *_SAFE_ERRORS) as exc:
        report.update(status="incomplete", error_code=exc.code, stop_reason=exc.code, compatibility_passed=False)
    except _INTERNAL:
        report.update(status="incomplete", error_code="artifact_io", stop_reason="artifact_io", compatibility_passed=False)
    else:
        # No validation, checkpoint or compensating write after publication.
        commit_terminal(pending, target)
        return terminal
    artifacts.persist(_safe(report, active_client))
    return report


async def run_probe(database: Path, output_dir: Path, *, plan_path: Path, accepted_commit: str,
                    origin: str = "mock", client: GatewayClient | None = None,
                    gateway_policies: dict | None = None, env_file: Path | None = None,
                    clock=time.monotonic) -> dict:
    return await _run_probe(database, output_dir, contract=_LegacyProbe(plan_path, accepted_commit),
                            origin=origin, client=client, gateway_policies=gateway_policies,
                            env_file=env_file, clock=clock)


def read_report(path: Path) -> dict:
    """Archived, bounded, allowlisted inspection; never loads config/current sources."""
    try:
        report = assets.read_asset(path)
        manifest = assets.read_asset(path.parent / "manifest.json")
        if (set(manifest) != {"version", "runner", "plan_sha256", "accepted_commit"}
                or manifest["version"] != VERSION
                or set(manifest["runner"]) != {"version", "sha256"}
                or manifest["runner"]["version"] != VERSION
                or not re.fullmatch(r"[0-9a-f]{64}", manifest["runner"]["sha256"])
                or set(report) != set(_report(manifest, "mock"))
                or report["manifest_sha256"] != assets.digest(manifest)
                or report["version"] != VERSION or report["origin"] not in ("mock", "live")
                or report["status"] not in ("incomplete", "running", "complete", "stopped")
                or report["reservation"] not in ("not_reserved", "in_progress", "settled")
                or report["upstream_inference_attempts"] is not None):
            raise ProbeError("invalid_evidence")
        for field, length in (("plan_sha256", 64), ("accepted_commit", 40)):
            if manifest[field] is not None and not re.fullmatch(r"[0-9a-f]{%d}" % length, manifest[field]):
                raise ProbeError("invalid_evidence")
        for field in ("client_http_attempts", "live_model_attempts", "possible_in_flight_attempts",
                      "attempt_budget_used", "runtime_invocations"):
            if type(report[field]) is not int or report[field] not in (0, 1):
                raise ProbeError("invalid_evidence")
        for field in ("error_code", "stop_reason"):
            if report[field] is not None and report[field] not in _CODES:
                raise ProbeError("invalid_evidence")
        for field, keys, values in (("compatibility", _COMPATIBILITY, _COMPAT_STATES),
                                    ("runtime_stages", model.STAGES, _STATES)):
            if set(report[field]) != set(keys) or any(v not in values for v in report[field].values()):
                raise ProbeError("invalid_evidence")
        if (report["live_model_attempts"] != (report["client_http_attempts"] if report["origin"] == "live" else 0)
                or report["attempt_budget_used"] != int(report["reservation"] != "not_reserved")
                or report["possible_in_flight_attempts"] != int(report["reservation"] == "in_progress")
                or report["client_http_attempts"] > report["runtime_invocations"]
                or report["runtime_invocations"] > report["attempt_budget_used"]
                or report["reservation"] == "settled" and report["runtime_invocations"] != 1):
            raise ProbeError("invalid_evidence")
        if (type(report["compatibility_passed"]) is not bool
                or report["compatibility_passed"] != (report["status"] == "complete")
                or report["compatibility_passed"] and (report["client_http_attempts"] != 1
                    or report["possible_in_flight_attempts"] != 0
                    or report["error_code"] is not None or report["stop_reason"] != "single_attempt_complete"
                    or not all(v == "passed" for v in report["compatibility"].values()))):
            raise ProbeError("invalid_evidence")
        if (report["requested_model"] != MODEL or report["observed_model"] not in (None, MODEL)
                or report["transport_security"] not in (None, "tls_verification_enabled", "unencrypted_http")
                or report["http_class"] not in ("not_run", "http_success", "http_failure", "no_response")):
            raise ProbeError("invalid_evidence")
        if report["http_status"] is not None and (type(report["http_status"]) is not int
                                                   or not 100 <= report["http_status"] <= 599):
            raise ProbeError("invalid_evidence")
        latency = report["elapsed_seconds"]
        if latency is not None and (type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0):
            raise ProbeError("invalid_evidence")
        if (set(report["usage"]) != {"prompt_tokens", "completion_tokens", "total_tokens"}
                or any(v is not None and (type(v) is not int or not 0 <= v <= 2**63 - 1)
                       for v in report["usage"].values())):
            raise ProbeError("invalid_evidence")
        policy = report["gateway_policy"]
        if policy != smoke.policy_attestation():
            if policy != smoke.policy_attestation({key: policy[key] for key in smoke.POLICY_KEYS}, required=True):
                raise ProbeError("invalid_evidence")
        fields = ("version", "status", "origin", "reservation", "possible_in_flight_attempts",
                  "client_http_attempts", "live_model_attempts", "upstream_inference_attempts",
                  "attempt_budget_used", "runtime_invocations", "compatibility", "runtime_stages",
                  "error_code", "stop_reason", "compatibility_passed", "gateway_policy",
                  "transport_security", "requested_model", "observed_model", "http_status", "http_class",
                  "usage", "elapsed_seconds")
        return {**{field: report[field] for field in fields}, "runner": manifest["runner"],
                "accepted_commit": manifest["accepted_commit"], "plan_sha256": manifest["plan_sha256"],
                "report_sha256": p3_eval._pin(path)["sha256"]}
    except (ProbeError,):
        raise
    except (*_SAFE_ERRORS, *_INTERNAL):
        raise ProbeError("invalid_evidence") from None


def main(argv: list[str] | None = None) -> int:
    parser = smoke._Parser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    for name in ("plan", "db", "env-file", "output-dir", "report"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--accepted-commit")
    for name in smoke.POLICY_KEYS:
        parser.add_argument(f"--gateway-{name}", choices=("enabled", "disabled"))
    try:
        args = parser.parse_args(argv)
        policies = {name: getattr(args, f"gateway_{name}") for name in smoke.POLICY_KEYS}
        if args.report is not None:
            if args.live or any((args.plan, args.db, args.env_file, args.output_dir, args.accepted_commit)) or any(policies.values()):
                raise ProbeError("invalid_arguments")
            result = read_report(args.report)
        else:
            if (not args.live or any(value is None for value in
                    (args.plan, args.db, args.env_file, args.output_dir, args.accepted_commit, *policies.values()))):
                raise ProbeError("invalid_arguments")
            asyncio.run(run_probe(args.db, args.output_dir, plan_path=args.plan,
                                  accepted_commit=args.accepted_commit, origin="live",
                                  env_file=args.env_file, gateway_policies=policies))
            result = read_report(args.output_dir / "report.json")
        print(model.canonical_json(result))
        return 0 if result["status"] == "complete" else 1
    except (ProbeError, *_SAFE_ERRORS) as exc:
        print(model.canonical_json({"status": "incomplete", "error_code": exc.code}), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, asyncio.CancelledError):
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except _INTERNAL:
        print('{"status":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
