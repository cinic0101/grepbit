"""Explicit closed candidate admission; no credentials, transport or model execution."""
from dataclasses import asdict
from pathlib import Path

from grepbit import model
from grepbit.gateway import ExpectedModel, GEMMA_12B, ModelError
from tools import p3_assets as assets, smoke

SEMANTICS_SHA256 = "b5d919d0083abc5baecea7462a97e3edf024a1f3a5ae6cb1401a175156d5116d"


def admit_candidate(value: object) -> ExpectedModel:
    return ExpectedModel.from_candidate(value)


def identity() -> dict:
    return asdict(GEMMA_12B)


def load_identity(path: Path) -> ExpectedModel:
    smoke._no_symlinks(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(assets.MAX_ASSET_BYTES + 1)
    except OSError:
        raise ModelError("invalid_configuration") from None
    if len(raw) > assets.MAX_ASSET_BYTES or smoke._digest(raw) != GEMMA_12B.candidate_identity_sha256:
        raise ModelError("invalid_configuration")
    value = model.strict_json(raw)
    if (value.get("candidate_id") != GEMMA_12B.candidate_id
            or value.get("model", {}).get("alias", {}).get("value") != GEMMA_12B.model_alias):
        raise ModelError("invalid_configuration")
    return admit_candidate(identity())


def semantic_identity() -> dict:
    """The frozen P3.3 candidate's semantic identity, read from the candidate registry (#87).

    Historical route tools bind their packets to this identity. Whether the live
    runtime still equals it is checked where a packet is prepared or run
    (`p3_candidate_probe._checkout`), not here, so archives read back on any
    registered candidate while new packets for these routes fail closed.
    """
    from tools import candidate_registry
    try:
        entry = candidate_registry.load_entry(candidate_registry.FROZEN_CANDIDATE_ID)
    except candidate_registry.RegistryError:
        raise assets.P3Error("source_identity_failure") from None
    value = {key: entry[key] for key in ("recipe_context", "structured_output", "p1_context", "limits")}
    if assets.digest(value) != SEMANTICS_SHA256:
        raise assets.P3Error("source_identity_failure")
    return value


def live_is_frozen() -> None:
    """Refuse to prepare or run a frozen-candidate route on any other registered candidate."""
    from tools import candidate_registry
    try:
        current = candidate_registry.check()["candidate_id"]
    except candidate_registry.RegistryError:
        raise assets.P3Error("source_identity_failure") from None
    if current != candidate_registry.FROZEN_CANDIDATE_ID:
        raise assets.P3Error("source_identity_failure")
