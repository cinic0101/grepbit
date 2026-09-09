"""Provider-neutral grounding classification boundary (spec §7 step 5)."""

from __future__ import annotations

from typing import Protocol

from grepbit.domain.grounding import (
    GROUNDING_PROMPT_SCHEMA_REVISION,
    GroundingProposal,
    GroundingRequest,
)

__all__ = [
    "GROUNDING_PROMPT_SCHEMA_REVISION",
    "GroundingModelError",
    "GroundingModelPort",
    "GroundingProposal",
    "GroundingRequest",
]

_GROUNDING_MODEL_ERROR_CODES = frozenset(
    {
        "credential_unavailable",
        "model_settings_missing",
        "model_call_failed",
        "invalid_structured_output",
        "openai_sdk_unavailable",
        "prompt_schema_revision_mismatch",
    }
)


class GroundingModelError(RuntimeError):
    def __init__(self, code: str, model_call_count: int) -> None:
        if code not in _GROUNDING_MODEL_ERROR_CODES:
            raise ValueError("grounding_model_error_code_invalid")
        super().__init__(code)
        self.code = code
        self.model_call_count = model_call_count


class GroundingModelPort(Protocol):
    def classify(self, request: GroundingRequest) -> GroundingProposal: ...
