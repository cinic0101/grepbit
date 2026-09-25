#!/usr/bin/env python3
"""Candidate registry (#87): the semantic identity of every runtime candidate, recorded once.

A candidate is what the runtime submits and enforces: the recipe instruction and
context, the structured-output schema, the P1 context, the gateway limits and
the exact wire bytes for fixed witness questions. Entries are append-only; the
index names the current candidate and each entry's ancestor. Rulers assert that
registered entries are byte-stable and that the live identity is registered;
no test asserts that the live checkout equals a historical candidate.
Offline only: mock transport, no credentials, no network, no database.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grepbit import gateway, model, recipe_model

REGISTRY_VERSION = "candidate-registry-v1"
DIRECTORY = ROOT / "evals/candidates"
INDEX = DIRECTORY / "index.json"
FROZEN_CANDIDATE_ID = "p33-frozen-20abb559"
_ID = "[a-z0-9][a-z0-9-]{2,63}"
_MOCK_BASE = "https://candidate-registry.invalid/v1"
_MOCK_KEY = "candidate-registry-offline-key"
# Fixed witness questions: exposed synthetic E01 English (the P3.10 witness) and
# the development wire witness used by the evaluator rulers. Never fresh text.
WITNESS_QUESTIONS = (
    ("p310_e01_en", "How were bookings at CTR-A01 in March 2026?"),
    ("development_wire", "March 2026 bookings; 三月預訂."),
)
RUNTIME_FILES = tuple(sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "grepbit").glob("*.py")))
_ENTRY_FIELDS = {
    "registry_version", "candidate_id", "ancestor", "registered_commit", "registered_at", "note",
    "recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
    "wire_witnesses", "runtime_files_sha256",
}


class RegistryError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _digest(value: object) -> str:
    return hashlib.sha256(model.canonical_json(value).encode()).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_identity() -> dict:
    """The four surfaces whose change makes a new candidate; same shape as p3_candidate_model."""
    return {"recipe_context": recipe_model.context_identity(),
            "structured_output": recipe_model.structured_output_identity(),
            "p1_context": model.context_identity(),
            "limits": {"input": gateway.MAX_INPUT_BYTES, "request": gateway.MAX_REQUEST_BYTES,
                       "response": gateway.MAX_RESPONSE_BYTES, "timeout": gateway.CALL_TIMEOUT_SECONDS}}


async def _capture(question: str, *, scalar: bool) -> bytes:
    sent: list[bytes] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(bytes(request.content))
        return httpx.Response(200, json={"model": gateway.MODEL, "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"outcome":"declined"}' if not scalar else "declined"}}]})

    client = gateway.GatewayClient(gateway.GatewayConfig(_MOCK_BASE, _MOCK_KEY),
                                   transport=httpx.MockTransport(handle))
    entry = model.interpret_and_execute if scalar else recipe_model.interpret_recipe_and_execute
    await entry(question, Path("candidate-registry-unused-db"), client, clock=lambda: 0.0)
    if len(sent) != 1:
        raise RegistryError("witness_capture_failed")
    return sent[0]


def wire_witnesses() -> list[dict]:
    """Exact request bodies for the fixed witness questions; the P3.10 witness also records P1."""
    witnesses = []
    for label, question in WITNESS_QUESTIONS:
        body = asyncio.run(_capture(question, scalar=False))
        witness = {"label": label, "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
                   "recipe_body_sha256": hashlib.sha256(body).hexdigest(), "recipe_body_bytes": len(body)}
        if label == "p310_e01_en":
            p1 = asyncio.run(_capture(question, scalar=True))
            witness.update(p1_body_sha256=hashlib.sha256(p1).hexdigest(), p1_body_bytes=len(p1))
        witnesses.append(witness)
    return witnesses


def live_identity() -> dict:
    semantic = semantic_identity()
    return {**semantic, "semantic_identity_sha256": _digest(semantic), "wire_witnesses": wire_witnesses(),
            "runtime_files_sha256": {name: _file_digest(ROOT / name) for name in RUNTIME_FILES}}


def _head() -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=ROOT,
                                         timeout=5).decode().strip()
        status = subprocess.check_output(["git", "--no-optional-locks", "status", "--porcelain",
                                          "--untracked-files=no"], cwd=ROOT, timeout=5).decode()
    except (OSError, subprocess.SubprocessError):
        raise RegistryError("git_unavailable") from None
    return commit, bool(status.strip())


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise RegistryError("invalid_registry") from None
    if not isinstance(value, dict):
        raise RegistryError("invalid_registry")
    return value


def load_index(index_path: Path | None = None) -> dict:
    index_path = INDEX if index_path is None else index_path
    index = _read(index_path)
    if (set(index) != {"registry_version", "current", "entries"} or index["registry_version"] != REGISTRY_VERSION
            or not isinstance(index["entries"], list) or not index["entries"]):
        raise RegistryError("invalid_registry")
    ids = []
    for row in index["entries"]:
        if (not isinstance(row, dict) or set(row) != {"candidate_id", "path", "sha256", "ancestor"}
                or not isinstance(row["candidate_id"], str) or row["candidate_id"] in ids
                or row["ancestor"] not in (None, *ids)):
            raise RegistryError("invalid_registry")
        ids.append(row["candidate_id"])
    if index["entries"][0]["ancestor"] is not None or index["current"] != ids[-1]:
        raise RegistryError("invalid_registry")
    return index


def load_entry(candidate_id: str, index_path: Path | None = None) -> dict:
    index_path = INDEX if index_path is None else index_path
    index = load_index(index_path)
    row = next((row for row in index["entries"] if row["candidate_id"] == candidate_id), None)
    if row is None:
        raise RegistryError("unknown_candidate")
    path = index_path.parent / row["path"]
    if not path.is_file() or path.is_symlink() or _file_digest(path) != row["sha256"]:
        raise RegistryError("registry_drift")
    entry = _read(path)
    if (set(entry) != _ENTRY_FIELDS or entry["registry_version"] != REGISTRY_VERSION
            or entry["candidate_id"] != candidate_id or entry["ancestor"] != row["ancestor"]
            or entry["semantic_identity_sha256"] != _digest({key: entry[key] for key in (
                "recipe_context", "structured_output", "p1_context", "limits")})):
        raise RegistryError("registry_drift")
    return entry


def current(index_path: Path | None = None) -> dict:
    index_path = INDEX if index_path is None else index_path
    return load_entry(load_index(index_path)["current"], index_path)


def witness(entry: dict, question: str) -> dict:
    digest = hashlib.sha256(question.encode()).hexdigest()
    for item in entry["wire_witnesses"]:
        if item["question_sha256"] == digest:
            return item
    raise RegistryError("unknown_witness")


def check(index_path: Path | None = None) -> dict:
    """The live runtime must be the registered current candidate, byte for byte on the wire."""
    entry = current(index_path)
    live = live_identity()
    for key in ("recipe_context", "structured_output", "p1_context", "limits", "semantic_identity_sha256",
                "wire_witnesses"):
        if live[key] != entry[key]:
            raise RegistryError("unregistered_candidate")
    return {"candidate_id": entry["candidate_id"], "semantic_identity_sha256": entry["semantic_identity_sha256"],
            "runtime_files_changed": sorted(name for name, sha in live["runtime_files_sha256"].items()
                                            if entry["runtime_files_sha256"].get(name) != sha)}


def register(candidate_id: str, note: str, *, index_path: Path | None = None, now: str | None = None) -> dict:
    """Append the live identity as a new candidate; refuses a duplicate identity or id."""
    index_path = INDEX if index_path is None else index_path
    if re.fullmatch(_ID, candidate_id) is None or not isinstance(note, str) or not note.strip():
        raise RegistryError("invalid_candidate_id")
    live = live_identity()
    if index_path.exists():
        index = load_index(index_path)
        head = current(index_path)
        if any(row["candidate_id"] == candidate_id for row in index["entries"]):
            raise RegistryError("duplicate_candidate_id")
        if head["semantic_identity_sha256"] == live["semantic_identity_sha256"]:
            raise RegistryError("identity_unchanged")
        ancestor = head["candidate_id"]
    else:
        index = {"registry_version": REGISTRY_VERSION, "current": None, "entries": []}
        ancestor = None
    commit, dirty = _head()
    entry = {"registry_version": REGISTRY_VERSION, "candidate_id": candidate_id, "ancestor": ancestor,
             "registered_commit": commit + ("+dirty" if dirty else ""),
             "registered_at": now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
             "note": note.strip(), **live}
    path = index_path.parent / f"{candidate_id}.json"
    if path.exists():
        raise RegistryError("duplicate_candidate_id")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    index["entries"].append({"candidate_id": candidate_id, "path": path.name, "sha256": _file_digest(path),
                             "ancestor": ancestor})
    index["current"] = candidate_id
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return check(index_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    registration = modes.add_parser("register", help="append the live identity as a new candidate")
    registration.add_argument("--id", required=True)
    registration.add_argument("--note", required=True)
    modes.add_parser("check", help="verify the live runtime is the registered current candidate")
    modes.add_parser("show", help="print the current candidate's identity")
    args = parser.parse_args(argv)
    try:
        if args.mode == "register":
            result = register(args.id, args.note)
        elif args.mode == "check":
            result = check()
        else:
            entry = current()
            result = {key: entry[key] for key in ("candidate_id", "ancestor", "registered_commit", "registered_at",
                                                  "note", "semantic_identity_sha256")}
            result["recipe_context"] = entry["recipe_context"]
            result["wire_witnesses"] = entry["wire_witnesses"]
    except RegistryError as exc:
        print(json.dumps({"error_code": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
