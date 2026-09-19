#!/usr/bin/env python3
"""Prepare the pinned P1.2 panel offline; --live requires separate owner authorization.

Preparation: python tools/smoke.py --db FIXTURE --output-dir NEW_DIRECTORY
Future live execution additionally requires --live --manifest PREPARED/manifest.json
and explicit --gateway-retries, --gateway-fallback and --gateway-cache attestations.
Prefer all three disabled; attestations are not independently verified.
Mock panels use run_panel(..., client=GatewayClient(..., transport=MockTransport(...))).
Neither preparation nor mock results constitute live model-quality evidence.
Only the exact synthetic seed is admitted, with a fixed 16 MiB database size bound.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Callable, Mapping
from contextlib import closing
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit.contracts import FactRequest, KernelError
from grepbit.gateway import (
    CALL_TIMEOUT_SECONDS, MAX_INPUT_BYTES, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES,
    MODEL, GatewayClient, GatewayConfig, ModelError,
)
from grepbit.model import (
    AS_OF, BUSINESS_TIMEZONE, STAGES, Interpretation, canonical_json, context_identity,
    interpret_and_execute, normalized_request, strict_json,
)
from tools import fixture

FAMILIES = {
    "Q01_booked_amount": "confirmed_booked_amount",
    "Q02_booking_count": "confirmed_booking_count",
    "Q03_booked_seats": "booked_seats",
    "Q04_known_learners": "known_booking_accounts",
}
LANGUAGES = ("zh-TW", "en", "ja")
ASSETS = (
    "evals/cases/learningops.json", "evals/cases/learningops-languages.json",
    "evals/oracles/learningops.json", "evals/fixtures/learningops/schema.sql",
    "evals/fixtures/learningops/seed.json",
)
MAX_ATTEMPTS = 12
PANEL_SECONDS = 900.0
MAX_DATABASE_BYTES = 16 * 1024 * 1024
POLICY_KEYS = ("retries", "fallback", "cache")
GRADING_STAGES = ("json_parse", "request_validation", "interpretation", "kernel", "value_agreement")
SAFE_CODES = {
    "artifact_conflict", "artifact_io", "source_identity_failure", "invalid_manifest",
    "missing_manifest", "manifest_drift", "unstable_database", "unsupported_database",
    "database_drift", "gateway_policy_required", "invalid_configuration", "invalid_arguments",
    "configuration_failure", "budget_exhausted", "panel_budget", "attempt_budget",
    "consecutive_transport_failures", "interrupted", "internal_failure",
}


class SmokeError(Exception):
    def __init__(self, code: str):
        self.code = code if code in SAFE_CODES else "internal_failure"
        super().__init__(self.code)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _no_symlinks(path: Path) -> None:
    if any(part.is_symlink() for part in (path.absolute(), *path.absolute().parents)):
        raise SmokeError("artifact_conflict")


def _stable_database(database: Path) -> str:
    _no_symlinks(database)
    if any(database.with_name(database.name + suffix).exists()
           or database.with_name(database.name + suffix).is_symlink()
           for suffix in ("-journal", "-wal", "-shm")):
        raise SmokeError("unstable_database")
    try:
        info = database.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_DATABASE_BYTES:
            raise SmokeError("unsupported_database")
        with database.open("rb") as stream:
            data = stream.read(MAX_DATABASE_BYTES + 1)
        if len(data) > MAX_DATABASE_BYTES:
            raise SmokeError("unsupported_database")
        return _digest(data)
    except OSError:
        raise SmokeError("unsupported_database") from None


def _fixture_identity(database: Path) -> str:
    before = _stable_database(database)
    try:
        with closing(sqlite3.connect(":memory:")) as expected, closing(sqlite3.connect(
            database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True,
        )) as actual:
            fixture.populate(expected)
            actual.execute("PRAGMA query_only=ON")
            schema = "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
            expected_schema = expected.execute(schema).fetchall()
            if actual.execute(schema).fetchmany(len(expected_schema) + 1) != expected_schema:
                raise SmokeError("unsupported_database")
            for table in fixture.TABLES:
                expected_rows = expected.execute(f'SELECT * FROM "{table}"').fetchall()
                if actual.execute(f'SELECT * FROM "{table}"').fetchmany(
                    len(expected_rows) + 1,
                ) != expected_rows:
                    raise SmokeError("unsupported_database")
    except (sqlite3.Error, OSError, ValueError):
        raise SmokeError("unsupported_database") from None
    if _stable_database(database) != before:
        raise SmokeError("database_drift")
    return before


def settings() -> dict[str, object]:
    return {
        "model": MODEL, "response_mode": "json_content", "max_client_http_attempts": MAX_ATTEMPTS,
        "concurrency": 1, "client_retries": 0, "repairs": 0, "stream": False,
        "temperature": 0, "max_tokens": 2048, "call_timeout_seconds": CALL_TIMEOUT_SECONDS,
        "panel_timeout_seconds": PANEL_SECONDS, "max_input_bytes": MAX_INPUT_BYTES,
        "max_request_bytes": MAX_REQUEST_BYTES, "max_response_bytes": MAX_RESPONSE_BYTES,
        "max_database_bytes": MAX_DATABASE_BYTES,
        "constraints": None, "raw_diagnostics": False, "as_of": AS_OF,
        "business_timezone": BUSINESS_TIMEZONE,
    }


def policy_attestation(policies: Mapping[str, str] | None = None, *,
                       required: bool = False) -> dict[str, object]:
    if policies is None and not required:
        return {**dict.fromkeys(POLICY_KEYS, "unknown"), "attestation": None}
    if (not isinstance(policies, Mapping) or set(policies) != set(POLICY_KEYS)
            or any(value not in ("disabled", "enabled") for value in policies.values())):
        raise SmokeError("gateway_policy_required")
    return {**policies, "attestation": "operator_cli_attestation_not_independently_verified"}


def _source_identity() -> dict[str, object]:
    if sys.version_info < (3, 11) or sqlite3.sqlite_version_info < (3, 37):
        raise SmokeError("source_identity_failure")
    paths = sorted((ROOT / "grepbit").glob("*.py"))
    paths += [ROOT / "tools/smoke.py", ROOT / "tools/fixture.py", ROOT / "requirements.txt"]
    if (ROOT / "requirements.in").is_file():
        paths.append(ROOT / "requirements.in")
    paths += [ROOT / name for name in ASSETS]
    try:
        dependencies = {}
        for line in (ROOT / "requirements.txt").read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, pinned = line.partition("==")
            if not separator or not name or not pinned or name in dependencies:
                raise SmokeError("source_identity_failure")
            installed = metadata.version(name)
            if installed != pinned:
                raise SmokeError("source_identity_failure")
            dependencies[name] = installed
        hashes = {str(path.relative_to(ROOT)): _digest(path.read_bytes()) for path in paths}
        commit = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"], cwd=ROOT,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout)
    except (OSError, subprocess.SubprocessError, metadata.PackageNotFoundError, ValueError):
        raise SmokeError("source_identity_failure") from None
    return {
        "git_commit": commit, "worktree_dirty": dirty, "files_sha256": hashes,
        "runtime": {"python": sys.version.split()[0], "implementation": sys.implementation.name,
                    "sqlite": sqlite3.sqlite_version, "dependencies": dependencies},
        "context": context_identity(),
    }


def _panel_inputs() -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        base = fixture.load(ROOT / ASSETS[0])
        languages = fixture.load(ROOT / ASSETS[1])
        references = {item["id"]: item for item in fixture.load(ROOT / ASSETS[2])}
        cases = {item["id"]: item for item in base["cases"]}
        variants = {item["case_id"]: item for item in languages["variants"]}
        if (languages["base_catalog_sha256"] != _digest((ROOT / ASSETS[0]).read_bytes())
                or languages["comparison_languages"] != list(LANGUAGES)
                or base["as_of_utc"] != AS_OF or base["timezone"] != BUSINESS_TIMEZONE):
            raise SmokeError("source_identity_failure")
        oracle = {
            family: {
                "request": normalized_request(FactRequest.from_mapping({
                    "metrics": [metric], **references[family]["params"],
                    "timezone": base["timezone"], "center_id": None,
                })),
                "expected": references[family]["expected"][0][0],
            }
            for family, metric in FAMILIES.items()
        }
        entries = []
        for round_index in range(3):
            for family_index, family in enumerate(FAMILIES):
                language = LANGUAGES[(round_index + family_index) % 3]
                question = (cases[family]["question"] if language == "zh-TW"
                            else variants[family][language])
                entries.append({
                    "order": len(entries) + 1, "family": family, "language": language,
                    "question": question, "question_sha256": _digest(question.encode("utf-8")),
                    "question_reference": {
                        "asset": ASSETS[0] if language == "zh-TW" else ASSETS[1],
                        "case_id": family, "field": "question" if language == "zh-TW" else language,
                    },
                })
        return entries, oracle
    except (OSError, ValueError, KeyError, TypeError, IndexError, KernelError):
        raise SmokeError("source_identity_failure") from None


def build_manifest(database: Path) -> dict[str, object]:
    inputs, oracle = _panel_inputs()
    return {
        "manifest_version": "p1.2-smoke-v1", "identities": _source_identity(),
        "database_sha256": _fixture_identity(database), "settings": settings(),
        "order": "three_rounds_family_order_language=(round+family_index)%3",
        "inputs": inputs, "oracle": oracle,
        "gateway_policy": policy_attestation(),
        "live_policy_binding": "separate_operator_cli_attestation_required_not_repinning",
        "upstream_inference_attempts": None,
    }


def validate_manifest(path: Path | None, current: dict[str, object]) -> None:
    if path is None:
        raise SmokeError("missing_manifest")
    _no_symlinks(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(1_048_577)
        if len(raw) > 1_048_576:
            raise SmokeError("invalid_manifest")
        prepared = strict_json(raw)
        if canonical_json(prepared) != canonical_json(current):
            raise SmokeError("manifest_drift")
    except (OSError, ModelError, ValueError):
        raise SmokeError("invalid_manifest") from None


def live_preflight(
    manifest_path: Path | None, current: dict[str, object], *,
    gateway_policies: Mapping[str, str] | None, environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> GatewayConfig:
    """Validate pins and attestations before explicitly loading live configuration; no HTTP."""
    validate_manifest(manifest_path, current)
    policy_attestation(gateway_policies, required=True)
    return GatewayConfig.from_env(environ=environ, env_file=env_file)


class _Artifacts:
    """Immutable, exclusive checkpoints plus an atomically updated owned report link."""

    def __init__(self, directory: Path, manifest: dict[str, object]):
        _no_symlinks(directory)
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            raise SmokeError("artifact_conflict") from None
        except OSError:
            raise SmokeError("artifact_io") from None
        self.directory = directory
        self.sequence = 0
        self.report_inode: tuple[int, int] | None = None
        self._write("manifest.json", manifest)

    def _write(self, name: str, data: dict[str, object]) -> Path:
        path = self.directory / name
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise SmokeError("artifact_conflict") from None
        except OSError:
            raise SmokeError("artifact_io") from None
        return path

    def persist(self, report: dict[str, object]) -> None:
        _no_symlinks(self.directory)
        snapshot = self._write(f"checkpoint-{self.sequence:04d}.json", report)
        self.sequence += 1
        target = self.directory / "report.json"
        try:
            if self.report_inode is None:
                os.link(snapshot, target)
            else:
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode)
                        or (info.st_dev, info.st_ino) != self.report_inode):
                    raise SmokeError("artifact_conflict")
                next_report = self.directory / "report.next.json"
                os.link(snapshot, next_report)
                os.replace(next_report, target)
            info = target.lstat()
            self.report_inode = (info.st_dev, info.st_ino)
        except FileExistsError:
            raise SmokeError("artifact_conflict") from None
        except OSError:
            raise SmokeError("artifact_io") from None


def _empty_evidence() -> dict[str, object]:
    return {
        "requested_model": MODEL, "returned_model": None, "response_mode": "json_content",
        "finish_reason": None,
        "usage": dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens")),
        "http_status": None, "transport_security": None, "stages": dict.fromkeys(STAGES, "not_run"),
        "kernel_error_code": None, "client_http_attempts": 0, "elapsed_seconds": None,
        "error_code": None, "stop_reason": None, "transport_failure": False,
        "request": None, "fact_pack": None,
    }


def _new_report(manifest: dict[str, object], origin: str) -> dict[str, object]:
    return {
        "report_version": "p1.2-smoke-v1", "status": "incomplete", "stop_reason": None,
        "error_code": None, "stop_classification": None,
        "mode": "dry_run" if origin == "preparation" else "panel", "origin": origin,
        "manifest_sha256": _digest(canonical_json(manifest).encode()),
        "gateway_policy": policy_attestation(), "client_http_attempts": 0,
        "completed_client_http_attempts": 0,
        "possible_in_flight_attempts": 0, "attempt_budget_used": 0,
        "live_model_attempts": 0, "upstream_inference_attempts": None,
        "elapsed_seconds": 0.0,
        "results": [
            {**entry, "status": "pending", "outcome": "unassessed", "not_run_reason": None,
             "client_http_attempts": 0, "attempt_may_be_in_flight": False,
             "evidence": _empty_evidence(), "error_code": None,
             "grading": dict.fromkeys(GRADING_STAGES, "not_run")}
            for entry in manifest["inputs"]
        ],
        "scope": "Four paired synthetic regression families, not twelve independent cases; "
                 "mock and prepared artifacts are not live model evidence.",
    }


def _summarize(report: dict[str, object]) -> None:
    results = report["results"]
    # Finalized local failures count here too; this says nothing about upstream completion.
    report["completed_client_http_attempts"] = sum(
        entry["client_http_attempts"] for entry in results if entry["status"] == "completed"
    )

    def counts(entries: list[dict[str, object]]) -> dict[str, object]:
        return {
            "total": len(entries), "correct": sum(e["outcome"] == "correct" for e in entries),
            "outcomes": dict(Counter(e["outcome"] for e in entries)),
            "statuses": dict(Counter(e["status"] for e in entries)),
        }

    families = {}
    for family in FAMILIES:
        entries = [e for e in results if e["family"] == family]
        families[family] = {
            **counts(entries), "all_three_correct": all(e["outcome"] == "correct" for e in entries),
        }
    report["summary"] = {
        **counts(results), "semantic_families": 4, "paired_inputs": 12,
        "all_three_correct_families": sum(f["all_three_correct"] for f in families.values()),
        "per_family": families,
        "per_language": {language: counts([e for e in results if e["language"] == language])
                         for language in LANGUAGES},
    }


def _not_run(report: dict[str, object], reason: str) -> None:
    for entry in report["results"]:
        if entry["status"] == "pending":
            entry.update(status="not_run", outcome="not_run", not_run_reason=reason)
    _summarize(report)


def prepare(database: Path, output_dir: Path) -> dict[str, object]:
    manifest = build_manifest(database)
    artifacts = _Artifacts(output_dir, manifest)
    report = _new_report(manifest, "preparation")
    _summarize(report)
    artifacts.persist(report)
    report["status"] = "prepared"
    _not_run(report, "dry_run")
    artifacts.persist(report)
    return report


def grade(result: Interpretation, oracle: dict[str, object]) -> tuple[str, dict[str, str]]:
    """Compare values only after exact interpretation; a matching number cannot rescue scope."""
    stages = result.evidence["stages"]
    grading = {
        "json_parse": stages["json_parse"], "request_validation": stages["request_validation"],
        "interpretation": "not_run", "kernel": stages["kernel_execution"],
        "value_agreement": "not_run",
    }
    if result.request is not None:
        grading["interpretation"] = (
            "passed" if normalized_request(result.request) == oracle["request"] else "failed"
        )
    if grading["interpretation"] == "failed":
        return "wrong", grading
    if result.error:
        if result.error.code == "model_declined":
            return "false_refusal", grading
        if result.error.code in (
            "invalid_response", "unsupported_output", "invalid_json", "invalid_request",
            "constraint_conflict", "truncated_output",
        ):
            return "invalid_output", grading
        return "operational_failure", grading
    if result.fact_pack is None:
        return "unassessed", grading
    if grading["interpretation"] != "passed":
        return "wrong", grading
    facts = result.fact_pack.facts
    correct = (
        result.fact_pack.status == "complete" and len(facts) == 1
        and facts[0].metric_id == oracle["request"]["metrics"][0]
        and type(facts[0].value) is type(oracle["expected"])
        and facts[0].value == oracle["expected"]
    )
    grading["value_agreement"] = "passed" if correct else "failed"
    return "correct" if correct else "wrong", grading


def _remaining(started: float, clock: Callable[[], float]) -> float:
    elapsed = clock() - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise SmokeError("invalid_configuration")
    return PANEL_SECONDS - elapsed


def _timeout_result(client: GatewayClient, attempts_before: int, elapsed: float) -> Interpretation:
    error = ModelError("timeout")
    evidence = _empty_evidence()
    evidence["stages"].update(configuration="passed", transport="failed")
    evidence.update(
        transport_security=client.config.transport_security,
        client_http_attempts=client.http_attempts - attempts_before,
        elapsed_seconds=round(elapsed, 6), error_code="timeout", transport_failure=True,
    )
    return Interpretation(None, None, error, evidence)


async def run_panel(
    database: Path, output_dir: Path, *, manifest_path: Path | None,
    client: GatewayClient | None = None, clock: Callable[[], float] = time.monotonic,
    origin: str = "mock", gateway_policies: Mapping[str, str] | None = None,
    env_file: Path | None = None, environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """One pass, no repairs or retries. Only the explicit CLI live branch loads configuration."""
    if origin not in ("mock", "live"):
        raise SmokeError("invalid_configuration")
    started = clock()
    manifest = build_manifest(database)
    artifacts = _Artifacts(output_dir, manifest)
    report = _new_report(manifest, origin)
    _summarize(report)
    artifacts.persist(report)
    active = None
    attempts_before = 0
    try:
        if origin == "live":
            if client is not None:
                raise SmokeError("invalid_configuration")
            config = live_preflight(
                manifest_path, manifest, gateway_policies=gateway_policies,
                environ=environ, env_file=env_file,
            )
            client = GatewayClient(config)
        else:
            validate_manifest(manifest_path, manifest)
        report["gateway_policy"] = policy_attestation(gateway_policies, required=origin == "live")
        if client is None or client.http_attempts != 0:
            raise SmokeError("invalid_configuration")
        consecutive_transport = 0
        for entry in report["results"]:
            if client.http_attempts >= MAX_ATTEMPTS:
                raise SmokeError("attempt_budget")
            remaining = _remaining(started, clock)
            if remaining <= 0:
                raise SmokeError("panel_budget")
            if _stable_database(database) != manifest["database_sha256"]:
                raise SmokeError("database_drift")
            active = entry
            attempts_before = client.http_attempts
            active.update(status="in_progress", attempt_may_be_in_flight=True)
            report.update(possible_in_flight_attempts=1, attempt_budget_used=attempts_before + 1)
            _summarize(report)
            artifacts.persist(report)  # Durable reservation before the only possible send.
            remaining = _remaining(started, clock)
            if remaining <= 0:
                active.update(status="pending", attempt_may_be_in_flight=False)
                active = None
                report.update(possible_in_flight_attempts=0, attempt_budget_used=client.http_attempts)
                raise SmokeError("panel_budget")
            timeout = min(CALL_TIMEOUT_SECONDS, remaining)
            call_started = clock()
            try:
                async with asyncio.timeout(timeout):
                    result = await interpret_and_execute(
                        entry["question"], database, client, constraints=None,
                        timeout_seconds=timeout, clock=clock,
                    )
            except TimeoutError:
                result = _timeout_result(client, attempts_before, max(0.0, clock() - call_started))
            active.update(
                status="completed", attempt_may_be_in_flight=False,
                client_http_attempts=client.http_attempts - attempts_before,
                evidence=client.safe_export(result.evidence),
                error_code=result.error.code if result.error else None,
            )
            report.update(
                client_http_attempts=client.http_attempts, possible_in_flight_attempts=0,
                attempt_budget_used=client.http_attempts,
                live_model_attempts=client.http_attempts if origin == "live" else 0,
                elapsed_seconds=round(max(0.0, clock() - started), 6),
            )
            if _stable_database(database) != manifest["database_sha256"]:
                raise SmokeError("database_drift")
            active["outcome"], active["grading"] = grade(result, manifest["oracle"][entry["family"]])
            _summarize(report)
            artifacts.persist(report)
            active = None
            if client.http_attempts - attempts_before not in (0, 1):
                raise SmokeError("attempt_budget")
            if result.error and result.error.stop_reason:
                raise SmokeError(result.error.stop_reason)
            consecutive_transport = (
                consecutive_transport + 1 if result.error and result.error.transport_failure else 0
            )
            if consecutive_transport >= 2:
                raise SmokeError("consecutive_transport_failures")
            if _remaining(started, clock) <= 0:
                raise SmokeError("panel_budget")
        report["status"] = "complete"
    except (KeyboardInterrupt, asyncio.CancelledError):
        report.update(status="incomplete", stop_reason="interrupted", error_code="interrupted")
    except (SmokeError, ModelError) as exc:
        reason = (
            exc.code if isinstance(exc, SmokeError) else "configuration_failure"
        )
        classification = ("budget_exhausted" if reason in (
            "budget_exhausted", "panel_budget", "attempt_budget",
        ) else "operational_failure" if reason == "consecutive_transport_failures"
            else "configuration_failure")
        report.update(status="stopped", stop_reason=reason, error_code=exc.code,
                      stop_classification=classification)
    except (RuntimeError, TypeError, LookupError, ArithmeticError, AttributeError,
            OSError, ValueError, sqlite3.Error):
        # A CLI/report boundary must preserve evidence without exporting arbitrary exception text.
        report.update(status="incomplete", stop_reason="internal_failure", error_code="internal_failure")
    finally:
        if active is not None and client is not None:
            active["client_http_attempts"] = client.http_attempts - attempts_before
            active["evidence"]["client_http_attempts"] = active["client_http_attempts"]
            report["client_http_attempts"] = client.http_attempts
            report["live_model_attempts"] = client.http_attempts if origin == "live" else 0
            report["attempt_budget_used"] = max(
                client.http_attempts, attempts_before + int(active["attempt_may_be_in_flight"]),
            )
        elapsed = clock() - started
        if math.isfinite(elapsed) and elapsed >= 0:
            report["elapsed_seconds"] = round(elapsed, 6)
        _not_run(report, report["stop_reason"] or "panel_complete")
        artifacts.persist(client.safe_export(report) if client else report)
    return client.safe_export(report) if client else report


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SmokeError("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--env-file", type=Path)
    for key in POLICY_KEYS:
        parser.add_argument(f"--gateway-{key}", choices=("disabled", "enabled"))
    try:
        args = parser.parse_args(argv)
        policies = {key: getattr(args, f"gateway_{key}") for key in POLICY_KEYS}
        if not args.live:
            if args.manifest is not None or args.env_file is not None or any(policies.values()):
                raise SmokeError("invalid_arguments")
            report = prepare(args.db, args.output_dir)
        else:
            report = asyncio.run(run_panel(
                args.db, args.output_dir, manifest_path=args.manifest, origin="live",
                gateway_policies=policies, env_file=args.env_file,
            ))
        print(canonical_json({
            key: report[key] for key in (
                "status", "origin", "stop_reason", "client_http_attempts", "live_model_attempts",
            )
        }))
        return 0 if (report["status"] == "prepared" or report["status"] == "complete"
                     and report["summary"]["all_three_correct_families"] == 4) else 1
    except (SmokeError, ModelError) as exc:
        print(canonical_json({"status": "stopped", "error_code": exc.code}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"status":"incomplete","error_code":"interrupted"}', file=sys.stderr)
        return 130
    except (RuntimeError, TypeError, LookupError, ArithmeticError, AttributeError,
            OSError, ValueError, sqlite3.Error):
        print('{"status":"incomplete","error_code":"internal_failure"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
