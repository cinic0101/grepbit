"""Explicit closed candidate admission; no credentials, transport or model execution."""
from dataclasses import asdict
from pathlib import Path

from grepbit import gateway, model, recipe_model
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
    value = {"recipe_context": recipe_model.context_identity(),
             "structured_output": recipe_model.structured_output_identity(),
             "p1_context": model.context_identity(),
             "limits": {"input": gateway.MAX_INPUT_BYTES, "request": gateway.MAX_REQUEST_BYTES,
                        "response": gateway.MAX_RESPONSE_BYTES, "timeout": gateway.CALL_TIMEOUT_SECONDS}}
    if assets.digest(value) != SEMANTICS_SHA256:
        raise assets.P3Error("source_identity_failure")
    return value
