"""OpenAI-compatible Chat Completions transport for grounding classification."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from grepbit.ports.grounding import (
    GROUNDING_PROMPT_SCHEMA_REVISION,
    GroundingModelError,
    GroundingModelPort,
    GroundingProposal,
    GroundingRequest,
)

BASE_URL_ENV = "GREPBIT_MODEL_BASE_URL"
MODEL_NAME_ENV = "GREPBIT_MODEL_NAME"
CREDENTIAL_ENV_NAME_ENV = "GREPBIT_MODEL_CREDENTIAL_ENV"
TIMEOUT_ENV = "GREPBIT_MODEL_TIMEOUT_SECONDS"
TEMPERATURE_ENV = "GREPBIT_MODEL_TEMPERATURE"
MAX_TOKENS_ENV = "GREPBIT_MODEL_MAX_TOKENS"
OUTPUT_MODE_ENV = "GREPBIT_MODEL_OUTPUT_MODE"
REPAIR_TURNS_ENV = "GREPBIT_MODEL_REPAIR_TURNS"
DEFAULT_CREDENTIAL_ENV = "LITELLM_API_KEY"

_SYSTEM_RULES = (
    "You are the grounding classifier of a governed analytics agent. Map the "
    "user's question to exactly one structured query over the supplied catalog, "
    "or decline. Rules: "
    "(1) metric_id must be one of the candidate metric ids; dimension_ids, "
    "filters and time_field_id may only use candidate ids and value_ids. "
    "(2) Never write SQL, never invent identifiers, never compute dates. Express "
    'an explicit month as {"kind":"month","month":"YYYY-MM"}, a date '
    'window as {"kind":"range","start":"YYYY-MM-DD",'
    '"end_exclusive":"YYYY-MM-DD"}, a relative period such as last month as '
    '{"kind":"relative","unit":"month","offset":-1}, and a comparison '
    'of named months as {"kind":"periods","periods":[{"kind":"month",'
    '"month":"YYYY-MM"}, ...]}. '
    "(3) shape: metric_scalar for one number; metric_by_dimension for a breakdown "
    "by one dimension; metric_over_time for a trend with grain day or month over "
    "a month, range or relative scope; compare_periods for two or more named "
    "months; top_n for a ranking with dimension_ids and limit. "
    "(4) Candidates come from similarity search and may be merely related. If "
    "the question asks for a concept that no candidate defines, such as profit "
    "or margin when only revenue metrics are offered, an average, a count, "
    "inventory, or headcount, return decision none with reason semantic_gap. "
    "Never answer a different metric than the one asked. "
    "(5) If it asks for something other than an aggregate over the catalog, "
    "such as a forecast, a data change, free text, or several unrelated "
    "questions, return decision none with reason unsupported. "
    "(6) If two or more candidate metrics fit equally and the question does not "
    "say which, return decision none with reason ambiguous and list "
    "ambiguous_metric_ids. Candidate disambiguators tell you which words select "
    "each metric. "
    "(7) Apply an enum filter only when the question names a value_id; "
    "defaults are already applied by the server. "
    "(8) Return only one JSON object that conforms to the schema."
)


@dataclass(frozen=True)
class GroundingModelSettings:
    base_url: str
    model: str
    credential_env_var: str = DEFAULT_CREDENTIAL_ENV
    timeout_seconds: float = 20.0
    temperature: float = 0.0
    max_tokens: int = 512
    structured_output_mode: Literal["json_object", "json_schema"] = "json_object"
    # follow-up calls allowed when the plan fails validation: the validation
    # errors go back to the model once (0 disables, for the ablation)
    repair_turns: int = 1

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> GroundingModelSettings:
        source = os.environ if environ is None else environ
        base_url = source.get(BASE_URL_ENV, "").strip()
        model = source.get(MODEL_NAME_ENV, "").strip()
        if not base_url or not model:
            raise GroundingModelError("model_settings_missing", 0)
        mode = source.get(OUTPUT_MODE_ENV, "json_object").strip()
        if mode not in {"json_object", "json_schema"}:
            raise GroundingModelError("model_settings_missing", 0)
        try:
            return cls(
                base_url=base_url,
                model=model,
                credential_env_var=source.get(
                    CREDENTIAL_ENV_NAME_ENV, DEFAULT_CREDENTIAL_ENV
                ).strip()
                or DEFAULT_CREDENTIAL_ENV,
                timeout_seconds=float(source.get(TIMEOUT_ENV, "20")),
                temperature=float(source.get(TEMPERATURE_ENV, "0")),
                max_tokens=int(source.get(MAX_TOKENS_ENV, "512")),
                structured_output_mode=mode,  # type: ignore[arg-type]
                repair_turns=int(source.get(REPAIR_TURNS_ENV, "1")),
            )
        except ValueError:
            raise GroundingModelError("model_settings_missing", 0) from None


ClientFactory = Callable[[GroundingModelSettings], Any]


class ChatCompletionsGroundingClient(GroundingModelPort):
    """One strict Chat Completions call per grounding request."""

    def __init__(
        self,
        settings: GroundingModelSettings,
        *,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._client_factory = client_factory

    @property
    def settings(self) -> GroundingModelSettings:
        return self._settings

    def build_messages(self, request: GroundingRequest) -> list[dict[str, str]]:
        schema = json.dumps(GroundingProposal.model_json_schema(), sort_keys=True)
        return [
            {"role": "system", "content": _SYSTEM_RULES},
            {
                "role": "system",
                "content": "Conform exactly to this JSON Schema: " + schema,
            },
            {
                "role": "user",
                "content": json.dumps(request.model_dump(mode="json"), sort_keys=True),
            },
        ]

    def classify(self, request: GroundingRequest) -> GroundingProposal:
        if request.prompt_schema_revision != GROUNDING_PROMPT_SCHEMA_REVISION:
            raise GroundingModelError("prompt_schema_revision_mismatch", 0)
        client = self._client or self._create_client()
        try:
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=self.build_messages(request),
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens,
                response_format=self._response_format(),
            )
        except Exception:
            raise GroundingModelError("model_call_failed", 1) from None
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError):
            raise GroundingModelError("invalid_structured_output", 1) from None
        if not isinstance(content, str):
            raise GroundingModelError("invalid_structured_output", 1)
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            raise GroundingModelError("invalid_structured_output", 1) from None
        try:
            return GroundingProposal.model_validate(payload)
        except ValidationError:
            raise GroundingModelError("invalid_structured_output", 1) from None

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(self._settings)
        credential = os.environ.get(self._settings.credential_env_var)
        if not credential:
            raise GroundingModelError("credential_unavailable", 0)
        try:
            from openai import OpenAI
        except ImportError:
            raise GroundingModelError("openai_sdk_unavailable", 0) from None
        return OpenAI(
            api_key=credential,
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
            max_retries=0,
        )

    def _response_format(self) -> dict[str, Any]:
        if self._settings.structured_output_mode == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "grounding_proposal",
                "strict": True,
                "schema": GroundingProposal.model_json_schema(),
            },
        }
