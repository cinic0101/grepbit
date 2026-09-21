"""Shared terminal staging/commit mechanics; grading and stop policy stay with callers."""
from collections.abc import Callable
import os
from pathlib import Path
import stat

from tools import smoke


def stage_terminal(
    artifacts: smoke._Artifacts, candidate: dict, *,
    validate: Callable[[], None], remaining: Callable[[], float],
) -> tuple[Path, Path]:
    target = artifacts.directory / "report.json"
    pending = artifacts.directory / "terminal.next.json"
    smoke._no_symlinks(artifacts.directory)
    snapshot = artifacts._write("terminal-candidate.json", candidate)
    info = snapshot.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise smoke.SmokeError("artifact_conflict")
    candidate_inode = (info.st_dev, info.st_ino)
    os.link(snapshot, pending)
    validate()
    smoke._no_symlinks(artifacts.directory)
    for path, expected_inode in ((target, artifacts.report_inode), (pending, candidate_inode)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != expected_inode:
            raise smoke.SmokeError("artifact_conflict")
    if remaining() <= 0:
        raise smoke.SmokeError("panel_budget")
    return pending, target


def commit_terminal(pending: Path, target: Path) -> None:
    try:
        os.replace(pending, target)
    except OSError:
        raise smoke.SmokeError("artifact_io") from None
