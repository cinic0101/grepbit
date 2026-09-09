"""Provider-neutral, serializable G0 contracts.

These models intentionally contain no execution, persistence, adapter, or API
integration. They make the legal states from the POC specification executable.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError


def domain_contract_error(code: str, message: str) -> PydanticCustomError:
    """Create a stable validation code without leaking rejected input values."""

    return PydanticCustomError(code, message)


class DomainModel(BaseModel):
    """Base configuration shared by all public domain contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnalysisShape(StrEnum):
    DIRECT_METRIC = "direct_metric"
    GROUP_AND_RANK = "group_and_rank"
    COMPARE_PERIODS = "compare_periods"
    FILTER_THEN_DRILL_DOWN = "filter_then_drill_down"
    DIAGNOSE_COUNT_VS_AVERAGE = "diagnose_count_vs_average"


class SnapshotConsistency(StrEnum):
    STATEMENT = "statement"
    REPEATABLE_READ = "repeatable_read"
    BEST_EFFORT = "best_effort"
    UNACCEPTABLE = "unacceptable"


class EvidenceCompleteness(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"


class SemanticAttestationStatus(StrEnum):
    """The only outcomes a structural semantic attestor may publish."""

    PASSED = "passed"
    INCONCLUSIVE = "inconclusive"


class SemanticAttestationReasonCode(StrEnum):
    MATCH = "attestation_match"
    CONTRACT_SQL_PARSE_FAILED = "contract_sql_parse_failed"
    CANDIDATE_SQL_PARSE_FAILED = "candidate_sql_parse_failed"
    SQL_STRUCTURE_MISMATCH = "sql_structure_mismatch"
    OUTPUT_SCHEMA_MISMATCH = "output_schema_mismatch"
    PARAMETER_NAMES_MISMATCH = "parameter_names_mismatch"
    SEMANTIC_REFS_MISMATCH = "semantic_refs_mismatch"


class SemanticContractPackReviewState(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"


class PublicVerificationState(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"


class TaskStatus(StrEnum):
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class RequestStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class QueryStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class ParameterMode(StrEnum):
    PRESERVED_BINDING = "preserved_binding"
    APPROVED_LITERALIZATION = "approved_literalization"


class SemanticRefSource(StrEnum):
    COMPILER_RESOLVED = "compiler_resolved"
    SEMANTIC_SQL_AST = "semantic_sql_ast"
    REQUESTED = "requested"


class ObservationAction(StrEnum):
    COMPLETE = "complete"
    REPAIR_QUERY = "repair_query"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"
    BLOCKED = "blocked"


class ReplanReasonCode(StrEnum):
    """Sanitized nonterminal triggers that may cross the G5 model boundary."""

    VALIDATION_INCONCLUSIVE = "validation_inconclusive"
    EXECUTION_FAILED = "execution_failed"
    RESULT_INCOMPLETE = "result_incomplete"
    FOLLOW_UP_REQUIRED = "follow_up_required"


class CompletedStepSummary(DomainModel):
    """Value-free terminal state supplied to the bounded replanning loop."""

    step_id: str = Field(min_length=1)
    status: Literal[TaskStatus.COMPLETED]


class PlanRevisionRecord(DomainModel):
    """Append-only, server-owned record of one accepted G5 query horizon."""

    plan_revision_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    parent_plan_revision_id: str | None = Field(default=None, min_length=1)
    trigger_reason_codes: list[str] = Field(min_length=1)
    accepted_query_step: QueryStep
    unmet_requirement_ids: list[str] = Field(min_length=1)
    normalized_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def stable_identity_matches_revision(self) -> PlanRevisionRecord:
        expected = f"{self.task_id}:plan:{self.revision_number}"
        if self.plan_revision_id != expected:
            raise ValueError("plan_revision_id must match task ID and revision")
        if self.revision_number == 1 and self.parent_plan_revision_id is not None:
            raise ValueError("initial plan revision cannot have a parent")
        if self.revision_number > 1 and self.parent_plan_revision_id is None:
            raise ValueError("later plan revisions require a parent")
        if self.revision_number > 1 and self.parent_plan_revision_id != (
            f"{self.task_id}:plan:{self.revision_number - 1}"
        ):
            raise ValueError("plan revision parent must be the preceding stable ID")
        if len(set(self.trigger_reason_codes)) != len(self.trigger_reason_codes):
            raise ValueError("plan revision reasons must be unique")
        if len(set(self.unmet_requirement_ids)) != len(self.unmet_requirement_ids):
            raise ValueError("plan revision unmet IDs must be unique")
        bound_ids = self.accepted_query_step.evidence_requirement_ids
        if not bound_ids or len(set(bound_ids)) != len(bound_ids):
            raise ValueError("accepted query step must bind evidence requirements")
        if not set(bound_ids) <= set(self.unmet_requirement_ids):
            raise ValueError("accepted query step may bind only unmet requirements")
        allowed_reasons = {
            "initial_plan",
            *(reason.value for reason in ReplanReasonCode),
        }
        if not set(self.trigger_reason_codes) <= allowed_reasons:
            raise ValueError("plan revision trigger reasons must be sanitized")
        return self


class DiagnosticExplanation(DomainModel):
    """G5 may describe association but never assert causal evidence."""

    classification: Literal["association", "correlation"]
    causal_claim: Literal[False]
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def disclaims_causation(self) -> DiagnosticExplanation:
        if "does not establish causation" not in self.text.lower():
            raise ValueError("diagnostic explanation must disclaim causation")
        if "causes" in self.text.lower():
            raise ValueError("diagnostic explanation cannot use causal language")
        return self


class QueryBudget(DomainModel):
    max_tasks_per_request: int = Field(default=5, ge=1)
    max_steps_per_task: int = Field(default=6, ge=1)
    max_queries_per_task: int = Field(default=10, ge=1)
    max_query_repairs_per_step: int = Field(default=1, ge=0)
    max_replans_per_task: int = Field(default=2, ge=0)
    max_llm_calls_per_task: int = Field(default=8, ge=0)
    statement_timeout_seconds: int = Field(default=30, ge=1)
    idle_in_transaction_timeout_seconds: int = Field(default=60, ge=1)
    max_task_wall_clock_seconds: int = Field(default=180, ge=1)
    max_request_wall_clock_seconds: int = Field(default=600, ge=1)
    max_result_rows: int = Field(default=5000, ge=1)
    preview_rows: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def preview_fits_result_limit(self) -> QueryBudget:
        if self.preview_rows > self.max_result_rows:
            raise ValueError("preview_rows must not exceed max_result_rows")
        return self


class RunContext(DomainModel):
    run_id: str = Field(min_length=1)
    datasource_id: str = Field(min_length=1)
    original_question: str = Field(min_length=1)
    as_of: datetime
    business_timezone: str = Field(min_length=1)
    semantic_revision: str = Field(min_length=1)
    semantic_digest: str = Field(min_length=1)
    catalog_revision: str = Field(min_length=1)
    catalog_digest: str = Field(min_length=1)
    validation_policy_revision: str = Field(min_length=1)
    prompt_schema_revision: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    structured_output_settings: dict[str, JsonValue] = Field(default_factory=dict)
    fixture_revision: str | None = Field(default=None, min_length=1)
    snapshot_consistency: SnapshotConsistency
    budgets: QueryBudget = Field(default_factory=QueryBudget)

    @field_validator("as_of")
    @classmethod
    def as_of_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value

    @field_validator("business_timezone")
    @classmethod
    def business_timezone_must_be_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                "business_timezone must be a valid IANA timezone"
            ) from error
        return value


class TaskIntent(DomainModel):
    task_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    analysis_shape: AnalysisShape
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    time_scope: str | None = Field(default=None, min_length=1)
    comparison_scope: str | None = Field(default=None, min_length=1)
    requested_limit: int | None = Field(default=None, ge=1)
    requires_relation_dependency: bool = False
    ambiguities: list[str] = Field(default_factory=list)


class RelationSchema(DomainModel):
    relation_name: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)

    @field_validator("columns")
    @classmethod
    def columns_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("relation schema columns must be unique")
        if any(not column.strip() for column in value):
            raise ValueError("relation schema columns must be non-empty")
        return value


class EvidenceRequirement(DomainModel):
    id: str = Field(min_length=1)
    claim_or_question: str = Field(min_length=1)
    required_relation_schema: RelationSchema
    required_validations: list[str] = Field(default_factory=list)
    completion_rule_id: str = Field(min_length=1)
    criticality: Literal["critical", "standard"]


class ResultRef(DomainModel):
    """A relation-filter dependency with producer-column -> consumer-key mapping."""

    producer_step_id: str = Field(min_length=1)
    relation_name: str = Field(min_length=1)
    required_columns: list[str] = Field(min_length=1)
    key_mapping: dict[str, str] = Field(min_length=1)
    use_mode: Literal["semi_join_filter"] = "semi_join_filter"

    @field_validator("required_columns")
    @classmethod
    def required_columns_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("result reference columns must be unique")
        if any(not column.strip() for column in value):
            raise ValueError("result reference columns must be non-empty")
        return value

    @model_validator(mode="after")
    def key_mapping_uses_declared_producer_columns(self) -> ResultRef:
        if any(not key.strip() for key in self.key_mapping):
            raise ValueError("result reference key mapping keys must be non-empty")
        if any(not value.strip() for value in self.key_mapping.values()):
            raise ValueError("result reference key mapping values must be non-empty")
        undeclared = set(self.key_mapping) - set(self.required_columns)
        if undeclared:
            raise ValueError(
                "result reference key mapping keys must be required producer columns: "
                + ", ".join(sorted(undeclared))
            )
        if set(self.key_mapping) != set(self.required_columns):
            raise ValueError(
                "result reference key mapping must cover every required producer column"
            )
        return self


class QueryStep(DomainModel):
    kind: Literal["query"] = "query"
    id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    input_refs: list[ResultRef] = Field(default_factory=list)
    control_dependencies: list[str] = Field(default_factory=list)
    semantic_refs_requested: list[str] = Field(default_factory=list)
    expected_output: RelationSchema | None = None
    evidence_requirement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def control_dependencies_are_not_data_dependencies(self) -> QueryStep:
        data_dependencies = {
            reference.producer_step_id for reference in self.input_refs
        }
        overlap = data_dependencies.intersection(self.control_dependencies)
        if overlap:
            raise ValueError(
                "control_dependencies may not duplicate data dependencies: "
                + ", ".join(sorted(overlap))
            )
        if len(self.control_dependencies) != len(set(self.control_dependencies)):
            raise ValueError("control_dependencies must be unique")
        return self


class SynthesisStep(DomainModel):
    kind: Literal["synthesis"] = "synthesis"
    id: str = Field(min_length=1)
    control_dependencies: list[str] = Field(default_factory=list)
    evidence_requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("control_dependencies")
    @classmethod
    def control_dependencies_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("control_dependencies must be unique")
        return value


PlanStep = Annotated[QueryStep | SynthesisStep, Field(discriminator="kind")]


class AnalysisPlan(DomainModel):
    task_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)

    @model_validator(mode="after")
    def references_must_be_declared_ancestor_outputs(self) -> AnalysisPlan:
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("plan step IDs must be unique")

        prior_steps: dict[str, QueryStep | SynthesisStep] = {}
        for step in self.steps:
            for dependency in step.control_dependencies:
                if dependency not in prior_steps:
                    raise ValueError(
                        f"control dependency {dependency!r} is missing, forward, "
                        "or cyclic"
                    )

            if isinstance(step, QueryStep):
                for reference in step.input_refs:
                    producer = prior_steps.get(reference.producer_step_id)
                    if producer is None:
                        raise ValueError(
                            f"result reference producer {reference.producer_step_id!r} "
                            "is missing, forward, or cyclic"
                        )
                    if not isinstance(producer, QueryStep):
                        raise ValueError("result references must point to query steps")
                    if producer.expected_output is None:
                        raise ValueError(
                            f"producer {producer.id!r} has no declared expected output"
                        )
                    if (
                        reference.relation_name
                        != producer.expected_output.relation_name
                    ):
                        raise ValueError(
                            "result reference relation name must match producer output"
                        )
                    declared_columns = set(producer.expected_output.columns)
                    missing_columns = set(reference.required_columns) - declared_columns
                    if missing_columns:
                        raise ValueError(
                            "result reference requires undeclared producer columns: "
                            + ", ".join(sorted(missing_columns))
                        )
            prior_steps[step.id] = step
        return self


class SingleQueryAnalysisPlan(AnalysisPlan):
    """A provider-neutral plan constrained to exactly one query step."""

    steps: tuple[QueryStep] = Field(min_length=1, max_length=1)


class QueryParameter(DomainModel):
    name: str = Field(min_length=1)
    type_name: str = Field(min_length=1)
    value: JsonValue
    sensitive: bool = False


class SemanticQueryDraft(DomainModel):
    semantic_sql: str = Field(min_length=1)
    typed_parameters: list[QueryParameter] = Field(default_factory=list)
    requested_semantic_refs: list[str] = Field(default_factory=list)
    expected_output: RelationSchema
    input_relation_uses: list[ResultRef] = Field(default_factory=list)


class ReviewedSemanticQueryContract(DomainModel):
    """A server-owned semantic SQL definition eligible for attestation."""

    contract_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    semantic_sql: str = Field(min_length=1)
    expected_output: RelationSchema
    parameter_names: list[str] = Field(default_factory=list)
    semantic_refs: list[str] = Field(default_factory=list)

    @field_validator("parameter_names", "semantic_refs")
    @classmethod
    def names_are_unique_and_nonempty(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("semantic contract names must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("semantic contract names must be non-empty")
        return value


class SemanticAttestationResult(DomainModel):
    """Sanitized evidence from a provider-neutral semantic attestation port."""

    status: SemanticAttestationStatus
    reason_code: SemanticAttestationReasonCode
    contract_id: str = Field(min_length=1)
    contract_revision: str = Field(min_length=1)


class SemanticContractReference(DomainModel):
    """The server-only identity of one reviewed semantic contract."""

    pack_id: str = Field(min_length=1)
    pack_revision: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    contract_revision: str = Field(min_length=1)


class ReviewedSemanticQueryContractEntry(DomainModel):
    """A reviewed contract bound to the G3 case and fixed-query identities."""

    case_id: str = Field(min_length=1)
    fixed_query_id: str = Field(min_length=1)
    contract: ReviewedSemanticQueryContract


class ReviewedSemanticQueryContractPack(DomainModel):
    """Versioned, server-owned semantic authority for a fixture revision."""

    schema_version: Literal["semantic_contract_pack-v1"]
    pack_id: str = Field(min_length=1)
    pack_revision: str = Field(min_length=1)
    review_state: SemanticContractPackReviewState
    fixture_revision: str = Field(min_length=1)
    semantic_revision: str = Field(min_length=1)
    contracts: list[ReviewedSemanticQueryContractEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def contract_identities_are_unique(self) -> ReviewedSemanticQueryContractPack:
        case_ids = [entry.case_id for entry in self.contracts]
        fixed_query_ids = [entry.fixed_query_id for entry in self.contracts]
        contract_identities = [
            (entry.contract.contract_id, entry.contract.revision)
            for entry in self.contracts
        ]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("semantic contract pack case IDs must be unique")
        if len(fixed_query_ids) != len(set(fixed_query_ids)):
            raise ValueError("semantic contract pack fixed query IDs must be unique")
        if len(contract_identities) != len(set(contract_identities)):
            raise ValueError(
                "semantic contract pack contract identities must be unique"
            )
        return self


class ReviewedSemanticQueryContractPackV2(DomainModel):
    """Additive semantic authority that inherits one exact verified v1 pack."""

    schema_version: Literal["semantic_contract_pack-v2"]
    pack_id: str = Field(min_length=1)
    pack_revision: str = Field(min_length=1)
    review_state: SemanticContractPackReviewState
    fixture_revision: str = Field(min_length=1)
    semantic_revision: str = Field(min_length=1)
    base_contract_pack: str = Field(min_length=1)
    base_contract_pack_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    contracts: list[ReviewedSemanticQueryContractEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def contract_identities_are_unique(
        self,
    ) -> ReviewedSemanticQueryContractPackV2:
        fixed_query_ids = [entry.fixed_query_id for entry in self.contracts]
        contract_identities = [
            (entry.contract.contract_id, entry.contract.revision)
            for entry in self.contracts
        ]
        if len(fixed_query_ids) != len(set(fixed_query_ids)):
            raise ValueError("semantic contract pack fixed query IDs must be unique")
        if len(contract_identities) != len(set(contract_identities)):
            raise ValueError(
                "semantic contract pack contract identities must be unique"
            )
        return self


class CompiledQuery(DomainModel):
    physical_sql: str = Field(min_length=1)
    execution_parameters: list[QueryParameter] = Field(default_factory=list)
    parameter_mode: ParameterMode
    semantic_refs: list[str] = Field(default_factory=list)
    semantic_ref_source: SemanticRefSource
    warnings: list[str] = Field(default_factory=list)
    compiler_revision: str = Field(min_length=1)


class RelationArtifact(DomainModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    artifact_id: str = Field(min_length=1)
    producer_step_id: str = Field(min_length=1)
    relation_schema: RelationSchema = Field(
        alias="schema", serialization_alias="schema"
    )
    query_recipe_id: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    bounded_preview: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=100
    )
    result_digest: str = Field(min_length=1)
    truncation: bool
    snapshot_consistency: SnapshotConsistency


class ValidationOutcome(DomainModel):
    validation_id: str = Field(min_length=1)
    validator: str = Field(min_length=1)
    status: ValidationStatus
    mandatory: bool = True
    critical: bool = False
    evidence: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def critical_validation_must_be_mandatory(self) -> ValidationOutcome:
        if self.critical and not self.mandatory:
            raise ValueError("critical validations must be mandatory")
        return self


class ClaimEvidence(DomainModel):
    claim_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    claim_type: str = Field(min_length=1)
    structured_facts: list[dict[str, JsonValue]] = Field(
        default_factory=list, max_length=100
    )
    units: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    exact_time_boundaries: dict[str, JsonValue] = Field(default_factory=dict)
    source_artifact_ids: list[str] = Field(min_length=1)
    validation_ids: list[str] = Field(default_factory=list)
    semantic_provenance: dict[str, JsonValue] = Field(default_factory=dict)
    result_digest: str = Field(min_length=1)
    completeness: EvidenceCompleteness


class QueryRecord(DomainModel):
    query_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    execution_sql_evidence: str = Field(min_length=1)
    physical_sql_public: str = Field(min_length=1)
    stored_parameter_evidence: list[dict[str, JsonValue]] = Field(default_factory=list)
    semantic_provenance: dict[str, JsonValue] = Field(default_factory=dict)
    status: QueryStatus
    row_count: int | None = Field(default=None, ge=0)
    elapsed_ms: int | None = Field(default=None, ge=0)
    truncation: bool = False
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def terminal_query_record_is_consistent(self) -> QueryRecord:
        if self.status is QueryStatus.SUCCEEDED:
            if self.error_code is not None:
                raise ValueError("succeeded query records cannot carry an error_code")
            if self.row_count is None:
                raise ValueError("succeeded query records require row_count")
        elif self.truncation:
            raise ValueError("only succeeded query records can be truncated")
        return self


class ObservationDecision(DomainModel):
    action: ObservationAction
    reason_codes: list[str] = Field(min_length=1)
    satisfied_requirement_ids: list[str] = Field(default_factory=list)
    unmet_requirement_ids: list[str] = Field(default_factory=list)
    proposed_next_goals: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def action_matches_remaining_requirements(self) -> ObservationDecision:
        if self.action is ObservationAction.COMPLETE and self.unmet_requirement_ids:
            raise ValueError("a complete decision cannot have unmet requirements")
        if (
            self.action is ObservationAction.REQUEST_MORE_EVIDENCE
            and not self.unmet_requirement_ids
        ):
            raise ValueError("request_more_evidence requires unmet requirements")
        return self


class TaskAnswer(DomainModel):
    text: str = Field(min_length=1)
    verification: PublicVerificationState
    validation_outcomes: list[ValidationOutcome] = Field(default_factory=list)
    evidence_completeness: EvidenceCompleteness
    claim_result_truncated: bool = False
    semantics_reviewed: bool
    snapshot_consistency: SnapshotConsistency
    unresolved_critical_ambiguity: bool = False
    safe_partial_claim_remains: bool = False
    claim_evidence_ids: list[str] = Field(default_factory=list)
    request_grounding_evidence_id: str | None = Field(default=None, min_length=1)

    def __init__(self, **data: object) -> None:
        try:
            super().__init__(**data)
        except ValidationError as error:
            if "request_grounding_required" in str(error):
                raise ValueError("request_grounding_required") from None
            raise

    @model_validator(mode="after")
    def verification_must_match_evidence(self) -> TaskAnswer:
        self._validate_safe_partial_claim_flag()
        derived = derive_public_verification(
            validation_outcomes=self.validation_outcomes,
            evidence_completeness=self.evidence_completeness,
            claim_result_truncated=self.claim_result_truncated,
            semantics_reviewed=self.semantics_reviewed,
            snapshot_consistency=self.snapshot_consistency,
            unresolved_critical_ambiguity=self.unresolved_critical_ambiguity,
            safe_partial_claim_remains=self.safe_partial_claim_remains,
        )
        if self.verification is not derived:
            raise ValueError(
                f"verification must equal derived public state {derived.value!r}"
            )
        if (
            self.verification
            in {
                PublicVerificationState.VERIFIED,
                PublicVerificationState.PARTIALLY_VERIFIED,
            }
            and not self.claim_evidence_ids
        ):
            raise ValueError(
                "verified and partially verified answers require claim evidence"
            )
        if (
            self.verification
            in {
                PublicVerificationState.VERIFIED,
                PublicVerificationState.PARTIALLY_VERIFIED,
            }
            and not self.request_grounding_evidence_id
        ):
            raise ValueError("request_grounding_required")
        return self

    def _validate_safe_partial_claim_flag(self) -> None:
        if not self.safe_partial_claim_remains:
            return
        mandatory = [
            outcome for outcome in self.validation_outcomes if outcome.mandatory
        ]
        has_noncritical_failure = any(
            outcome.status is ValidationStatus.FAILED and not outcome.critical
            for outcome in mandatory
        )
        has_disqualifying_outcome = any(
            outcome.status in {ValidationStatus.BLOCKED, ValidationStatus.INCONCLUSIVE}
            or (outcome.critical and outcome.status is ValidationStatus.FAILED)
            for outcome in mandatory
        )
        acceptable_snapshot = self.snapshot_consistency in {
            SnapshotConsistency.STATEMENT,
            SnapshotConsistency.REPEATABLE_READ,
        }
        if (
            self.evidence_completeness is not EvidenceCompleteness.PARTIAL
            or not has_noncritical_failure
            or has_disqualifying_outcome
            or self.claim_result_truncated
            or not self.semantics_reviewed
            or not acceptable_snapshot
            or self.unresolved_critical_ambiguity
        ):
            raise ValueError(
                "safe_partial_claim_remains requires only a non-critical mandatory "
                "failure with otherwise safe partial evidence"
            )


def derive_public_verification(
    *,
    validation_outcomes: list[ValidationOutcome],
    evidence_completeness: EvidenceCompleteness,
    claim_result_truncated: bool,
    semantics_reviewed: bool,
    snapshot_consistency: SnapshotConsistency,
    unresolved_critical_ambiguity: bool,
    safe_partial_claim_remains: bool,
) -> PublicVerificationState:
    """Implement the Section 4.7 verification mapping without runtime policy.

    A non-critical failed validation is only partially verified when the caller
    explicitly records a safe remaining partial claim. Otherwise the answer is
    unverified; critical failures and policy blocks are always blocked.
    """

    mandatory = [outcome for outcome in validation_outcomes if outcome.mandatory]
    if not mandatory:
        return PublicVerificationState.UNVERIFIED
    if any(outcome.status is ValidationStatus.BLOCKED for outcome in mandatory):
        return PublicVerificationState.BLOCKED
    if any(
        outcome.critical and outcome.status is ValidationStatus.FAILED
        for outcome in mandatory
    ):
        return PublicVerificationState.BLOCKED
    if any(outcome.status is ValidationStatus.INCONCLUSIVE for outcome in mandatory):
        return PublicVerificationState.UNVERIFIED
    if (
        evidence_completeness is EvidenceCompleteness.INSUFFICIENT
        or not semantics_reviewed
        or unresolved_critical_ambiguity
        or snapshot_consistency
        not in {SnapshotConsistency.STATEMENT, SnapshotConsistency.REPEATABLE_READ}
    ):
        return PublicVerificationState.UNVERIFIED
    if any(outcome.status is ValidationStatus.FAILED for outcome in mandatory):
        if (
            safe_partial_claim_remains
            and evidence_completeness is EvidenceCompleteness.PARTIAL
            and not claim_result_truncated
        ):
            return PublicVerificationState.PARTIALLY_VERIFIED
        return PublicVerificationState.UNVERIFIED
    if claim_result_truncated:
        return PublicVerificationState.PARTIALLY_VERIFIED
    if evidence_completeness is EvidenceCompleteness.PARTIAL:
        return PublicVerificationState.PARTIALLY_VERIFIED
    return PublicVerificationState.VERIFIED


class StructuredError(DomainModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class TaskResult(DomainModel):
    task_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    status: TaskStatus
    answer: TaskAnswer | None = None
    structured_errors: list[StructuredError] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    query_records: list[QueryRecord] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def terminal_task_answer_contract(self) -> TaskResult:
        answer_required = {TaskStatus.COMPLETED, TaskStatus.PARTIALLY_COMPLETED}
        if self.status in answer_required and self.answer is None:
            raise ValueError(
                "completed and partially completed tasks require an answer"
            )
        if self.status is TaskStatus.BLOCKED and self.answer is not None:
            if self.answer.verification is not PublicVerificationState.BLOCKED:
                raise ValueError("blocked task answers must have blocked verification")
        if self.status is TaskStatus.FAILED and self.answer is not None:
            raise ValueError("failed terminal tasks cannot carry an answer")
        if self.status in {
            TaskStatus.BUDGET_EXCEEDED,
            TaskStatus.TIMED_OUT,
            TaskStatus.CANCELLED,
            TaskStatus.ABANDONED,
        }:
            if (
                self.answer is not None
                and self.answer.verification is PublicVerificationState.VERIFIED
            ):
                raise ValueError(
                    "interrupted terminal tasks cannot carry verified answers"
                )
        if self.answer is not None:
            missing_evidence = set(self.answer.claim_evidence_ids) - set(
                self.evidence_ids
            )
            if missing_evidence:
                raise ValueError(
                    "answer claim evidence IDs must be present in task evidence_ids: "
                    + ", ".join(sorted(missing_evidence))
                )
        return self


class RequestRecord(DomainModel):
    run_id: str = Field(min_length=1)
    status: RequestStatus
    tasks: list[TaskResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def request_status_must_match_legal_task_state(self) -> RequestRecord:
        nonterminal = {RequestStatus.ACCEPTED, RequestStatus.RUNNING}
        if self.status in nonterminal:
            if self.tasks:
                raise ValueError(
                    "nonterminal requests cannot contain terminal task results"
                )
            return self
        if not self.tasks:
            raise ValueError("terminal requests require at least one task")
        derived = self.aggregate_terminal_status(self.tasks)
        if self.status is not derived:
            raise ValueError(
                f"request status must equal aggregate task status {derived.value!r}"
            )
        return self

    @staticmethod
    def aggregate_terminal_status(tasks: list[TaskResult]) -> RequestStatus:
        """Derive a terminal request state without concealing task failures."""
        if not tasks:
            raise ValueError("cannot aggregate an empty task list")
        statuses = {task.status for task in tasks}
        if statuses == {TaskStatus.COMPLETED}:
            return RequestStatus.COMPLETED
        if (
            TaskStatus.COMPLETED in statuses
            or TaskStatus.PARTIALLY_COMPLETED in statuses
        ):
            return RequestStatus.PARTIALLY_COMPLETED
        if TaskStatus.BLOCKED in statuses:
            return RequestStatus.BLOCKED
        if statuses == {TaskStatus.FAILED}:
            return RequestStatus.FAILED
        if statuses == {TaskStatus.BUDGET_EXCEEDED}:
            return RequestStatus.BUDGET_EXCEEDED
        if statuses == {TaskStatus.TIMED_OUT}:
            return RequestStatus.TIMED_OUT
        if statuses == {TaskStatus.CANCELLED}:
            return RequestStatus.CANCELLED
        if statuses == {TaskStatus.ABANDONED}:
            return RequestStatus.ABANDONED
        return RequestStatus.FAILED
