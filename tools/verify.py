#!/usr/bin/env python3
"""Run bounded Grepbit validation profiles and persist their evidence.

This runner is intentionally limited to local test and static-analysis commands.
It neither creates infrastructure nor loads environment files, credentials, or
model clients. PostgreSQL profiles require an already-running fixture and the
explicit ``--allow-postgres`` scope assertion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as element_tree
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
RUFF = ROOT / ".venv" / "bin" / "ruff"
POSTGRES_FLAG_NAMES = (
    "GREPBIT_G1_POSTGRES",
    "GREPBIT_G2_POSTGRES",
    "GREPBIT_G3_POSTGRES",
)
POSTGRES_ENVIRONMENT = {name: "1" for name in POSTGRES_FLAG_NAMES}
POSTGRES_PROFILES = frozenset({"postgres"})


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    exit_code: int | None
    elapsed_seconds: float
    classification: str
    log_path: str


def _git_output(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode:
        return None
    return completed.stdout.strip()


def _is_relevant_source_path(candidate: Path) -> bool:
    return (
        candidate.suffix == ".py"
        or candidate.as_posix() in {"pyproject.toml", "uv.lock", "compose.g1.yaml"}
        or candidate.parts[:1] == ("spec",)
        or candidate.parts[:2] == ("evals", "cases")
        or candidate.parts[:2] == ("evals", "fixtures")
        or candidate.parts[:1] == ("semantic",)
        or candidate.parts[:2] == ("tests", "fixtures")
    )


def _is_environment_path(candidate: Path) -> bool:
    return any(part == ".env" or part.startswith(".env.") for part in candidate.parts)


def _source_paths(
    *, artifact_root: Path | None = None
) -> tuple[list[Path], str | None] | None:
    tracked = _git_output("ls-files", "-z")
    untracked = _git_output("ls-files", "--others", "--exclude-standard", "-z")
    if tracked is None or untracked is None:
        return None
    paths: set[Path] = set()
    excluded = artifact_root.absolute() if artifact_root is not None else None
    for value in (tracked + "\0" + untracked).split("\0"):
        if not value:
            continue
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            return None
        path = ROOT / candidate
        if not _is_relevant_source_path(candidate):
            continue
        if _is_environment_path(candidate):
            return [], "environment_path"
        if path.is_symlink() or any(
            parent.is_symlink() for parent in path.parents if parent != ROOT.parent
        ):
            return [], "symlink_source"
        absolute = path.absolute()
        if excluded is not None and absolute.is_relative_to(excluded):
            continue
        if not path.is_file() or not os.access(path, os.R_OK):
            return [], "unreadable_or_missing_source"
        paths.add(candidate)
    return sorted(paths), None


def _source_snapshot(*, artifact_root: Path | None = None) -> dict[str, Any]:
    head = _git_output("rev-parse", "HEAD")
    sources = _source_paths(artifact_root=artifact_root)
    if head is None or sources is None:
        return {
            "available": False,
            "identity_error": "missing_git_baseline",
            "head": head,
            "tracked_source_hashes": {},
        }
    paths, source_error = sources
    if source_error is not None:
        return {
            "available": False,
            "identity_error": source_error,
            "head": head,
            "tracked_source_hashes": {},
        }
    digests: dict[str, str] = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_file():
            digests[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    status = _git_output("status", "--porcelain=v1", "-uno")
    if status is None:
        return {
            "available": False,
            "identity_error": "missing_git_baseline",
            "head": head,
            "tracked_source_hashes": {},
        }
    return {
        "available": True,
        "head": head,
        "tracked_source_hashes": digests,
        "tracked_source_digest": _canonical_digest(digests),
        "tracked_worktree_status_digest": _canonical_digest(status),
    }


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _environment(*, postgres: bool) -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}:
            environment.pop(name)
        elif name.startswith("GREPBIT_") and name.endswith("_POSTGRES"):
            environment.pop(name)
        elif name.upper().endswith(
            ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIAL")
        ):
            environment.pop(name)
    if postgres:
        environment.update(POSTGRES_ENVIRONMENT)
    return environment


def _validate_test_paths(test_paths: Iterable[str]) -> list[str]:
    validated: list[str] = []
    tests_root = (ROOT / "tests").resolve()
    for value in test_paths:
        source_path, separator, node_id = value.partition("::")
        candidate = (ROOT / source_path).resolve()
        if candidate.suffix != ".py" or tests_root not in candidate.parents:
            raise ValueError("focused_test_path_must_be_a_python_file_under_tests")
        suffix = f"{separator}{node_id}" if separator else ""
        validated.append(f"{candidate.relative_to(ROOT).as_posix()}{suffix}")
    if not validated:
        raise ValueError("focused_profile_requires_explicit_test_paths")
    return validated


def _profile_commands(
    profile: str, test_paths: list[str], output: Path
) -> list[list[str]]:
    if profile == "focused":
        return [
            [
                str(PYTHON),
                "-m",
                "pytest",
                "-q",
                *test_paths,
                f"--junitxml={output / 'junit.xml'}",
            ]
        ]
    if profile == "offline":
        return [
            [str(PYTHON), "-m", "pytest", "-q", f"--junitxml={output / 'junit.xml'}"]
        ]
    if profile == "postgres":
        return [
            [str(PYTHON), "-m", "pytest", "-q", f"--junitxml={output / 'junit.xml'}"]
        ]
    if profile == "static":
        return [
            [str(RUFF), "check", "."],
            [str(RUFF), "format", "--check", "."],
            ["git", "diff", "--check"],
        ]
    raise ValueError("unknown_validation_profile")


def _run_command(
    command: list[str],
    *,
    output: Path,
    index: int,
    environment: dict[str, str],
    timeout: float | None,
) -> CommandResult:
    log_path = output / f"command-{index:02d}.log"
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        except OSError:
            log.write("start_failed\n")
            return CommandResult(
                command=command,
                exit_code=None,
                elapsed_seconds=round(time.monotonic() - started, 6),
                classification="start_failed",
                log_path=log_path.name,
            )
        classification = "completed"
        exit_code: int | None
        try:
            exit_code = process.wait(timeout=timeout)
            if exit_code < 0:
                classification = "interrupted"
            elif exit_code:
                classification = "failed"
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            exit_code = None
            classification = "timeout"
    return CommandResult(
        command=command,
        exit_code=exit_code,
        elapsed_seconds=round(time.monotonic() - started, 6),
        classification=classification,
        log_path=log_path.name,
    )


def _junit_counts(path: Path) -> dict[str, int]:
    try:
        root = element_tree.parse(path).getroot()
    except (FileNotFoundError, element_tree.ParseError) as error:
        raise ValueError("missing_or_malformed_junit") from error
    suites: list[element_tree.Element]
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = [
            suite
            for suite in root.iter("testsuite")
            if not any(child.tag == "testsuite" for child in suite)
        ]
    else:
        raise ValueError("missing_or_malformed_junit")
    if not suites:
        raise ValueError("missing_or_malformed_junit")
    values: dict[str, int] = {}
    for name in ("tests", "failures", "errors", "skipped"):
        values[name] = 0
        for suite in suites:
            raw = suite.attrib.get(name)
            if raw is None:
                raise ValueError("missing_or_malformed_junit")
            try:
                value = int(raw)
            except ValueError as error:
                raise ValueError("missing_or_malformed_junit") from error
            if value < 0:
                raise ValueError("missing_or_malformed_junit")
            values[name] += value
    testcases = [case for suite in suites for case in suite.findall("testcase")]
    actual_counts = {
        "tests": len(testcases),
        "failures": sum(case.find("failure") is not None for case in testcases),
        "errors": sum(case.find("error") is not None for case in testcases),
        "skipped": sum(case.find("skipped") is not None for case in testcases),
    }
    if values != actual_counts:
        raise ValueError("inconsistent_junit_counts")
    return values


def _result_status(
    *, commands: list[CommandResult], junit_counts: dict[str, int] | None
) -> str:
    if any(command.classification == "start_failed" for command in commands):
        return "start_failed"
    if any(command.classification == "timeout" for command in commands):
        return "timeout"
    if any(command.classification == "interrupted" for command in commands):
        return "interrupted"
    if any(command.classification == "failed" for command in commands):
        return "failed"
    if junit_counts is None:
        return "pass"
    if junit_counts["tests"] == 0:
        return "invalid_junit"
    if junit_counts["skipped"] == junit_counts["tests"]:
        return "all_skipped"
    if junit_counts["failures"] or junit_counts["errors"]:
        return "failed"
    return "pass"


def run_profile(
    *,
    profile: str,
    output: Path,
    test_paths: Iterable[str] = (),
    allow_postgres: bool = False,
    timeout: float | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("validation_output_already_exists")
    if profile in POSTGRES_PROFILES and not allow_postgres:
        raise PermissionError("postgres_profile_requires_allow_postgres")
    paths = _validate_test_paths(test_paths) if profile == "focused" else []
    output.mkdir(parents=True, exist_ok=False)
    start_snapshot = _source_snapshot(artifact_root=output)
    commands = _profile_commands(profile, paths, output)
    environment = _environment(postgres=profile in POSTGRES_PROFILES)
    command_results = [
        _run_command(
            command,
            output=output,
            index=index,
            environment=environment,
            timeout=timeout,
        )
        for index, command in enumerate(commands, start=1)
    ]
    junit_counts: dict[str, int] | None = None
    junit_error: str | None = None
    if profile != "static":
        try:
            junit_counts = _junit_counts(output / "junit.xml")
        except ValueError as error:
            junit_error = str(error)
    end_snapshot = _source_snapshot(artifact_root=output)
    source_available = bool(
        start_snapshot.get("available") and end_snapshot.get("available")
    )
    source_stable = source_available and (
        start_snapshot["head"] == end_snapshot["head"]
        and start_snapshot["tracked_source_digest"]
        == end_snapshot["tracked_source_digest"]
    )
    status = _result_status(commands=command_results, junit_counts=junit_counts)
    if junit_error is not None and status == "pass":
        status = "invalid_junit"
    if not source_available and status == "pass":
        status = "source_identity_unavailable"
    elif not source_stable and status == "pass":
        status = "source_changed_during_run"
    result = {
        "profile": profile,
        "status": status,
        "passed": status == "pass",
        "commands": [asdict(command) for command in command_results],
        "junit_counts": junit_counts,
        "junit_error": junit_error,
        "source": {
            "start": start_snapshot,
            "end": end_snapshot,
            "available": source_available,
            "stable": source_stable,
        },
        "allow_postgres_scope_assertion": allow_postgres,
        "timeout_seconds": timeout,
    }
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=("focused", "offline", "static", "postgres"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new directory for immutable run artifacts",
    )
    parser.add_argument(
        "--tests", nargs="+", default=(), help="required Python test paths for focused"
    )
    parser.add_argument(
        "--allow-postgres",
        action="store_true",
        help=(
            "assert an already-authorized, already-running disposable PostgreSQL "
            "scope; this does not grant permission or start Docker"
        ),
    )
    parser.add_argument("--timeout", type=float, help="per-command timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.timeout is not None and arguments.timeout <= 0:
        _parser().error("--timeout must be positive")
    try:
        result = run_profile(
            profile=arguments.profile,
            output=arguments.output,
            test_paths=arguments.tests,
            allow_postgres=arguments.allow_postgres,
            timeout=arguments.timeout,
        )
    except (FileExistsError, PermissionError, ValueError) as error:
        print(f"VERIFY_BLOCKED code={error}", file=sys.stderr)
        return 2
    counts = result["junit_counts"]
    count_text = (
        ""
        if counts is None
        else f" tests={counts['tests']} skipped={counts['skipped']}"
    )
    summary = f"VERIFY_{result['status'].upper()} profile={result['profile']}"
    print(f"{summary}{count_text} output={arguments.output}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
