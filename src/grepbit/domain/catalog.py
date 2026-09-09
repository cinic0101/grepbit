"""Server-owned, value-free semantic catalog contracts (spec Section 5)."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from grepbit.domain.models import DomainModel

_IDENTIFIER = r"^[a-z_][a-z0-9_]*$"
_QUALIFIED_IDENTIFIER = r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$"
_TIMEZONE_ID = r"^[A-Za-z_]+(/[A-Za-z_+-]+)*$"
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _synonyms_are_specific(synonyms: list[str]) -> None:
    """A single CJK character matches inside unrelated words; require two or more."""

    for synonym in synonyms:
        if not synonym.strip():
            raise ValueError("catalog_synonym_empty")
        if _CJK.search(synonym) and len(synonym.strip()) < 2:
            raise ValueError("catalog_synonym_too_short")


class ReviewState(StrEnum):
    VERIFIED = "verified"
    CANDIDATE = "candidate"


class QueryShape(StrEnum):
    METRIC_SCALAR = "metric_scalar"
    METRIC_BY_DIMENSION = "metric_by_dimension"
    METRIC_OVER_TIME = "metric_over_time"
    COMPARE_PERIODS = "compare_periods"
    TOP_N = "top_n"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"


class DimensionKind(StrEnum):
    TEXT = "text"
    ENUM = "enum"


class CatalogModel(DomainModel):
    name: str = Field(pattern=_IDENTIFIER)
    grain: list[str] = Field(min_length=1)
    description: str = ""


class CatalogRelationship(DomainModel):
    parent_model: str = Field(pattern=_IDENTIFIER)
    parent_key: str = Field(pattern=_IDENTIFIER)
    child_model: str = Field(pattern=_IDENTIFIER)
    child_key: str = Field(pattern=_IDENTIFIER)
    cardinality: Literal["one_to_many"] = "one_to_many"

    @property
    def id(self) -> str:
        return f"{self.parent_model}_{self.child_model}"

    @model_validator(mode="after")
    def models_differ(self) -> CatalogRelationship:
        if self.parent_model == self.child_model:
            raise ValueError("catalog_relationship_self_reference")
        return self


class EnumValue(DomainModel):
    value_id: str = Field(pattern=_IDENTIFIER)
    value: str = Field(min_length=1)
    synonyms: list[str] = Field(default_factory=list)


class CatalogDimension(DomainModel):
    id: str = Field(pattern=_QUALIFIED_IDENTIFIER)
    model: str = Field(pattern=_IDENTIFIER)
    column: str = Field(pattern=_IDENTIFIER)
    kind: DimensionKind = DimensionKind.TEXT
    values: list[EnumValue] = Field(default_factory=list)
    review_state: ReviewState
    synonyms: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    description: str = ""

    @model_validator(mode="after")
    def identity_and_values_are_coherent(self) -> CatalogDimension:
        _synonyms_are_specific(self.synonyms)
        for value in self.values:
            _synonyms_are_specific(value.synonyms)
        if self.id != f"{self.model}.{self.column}":
            raise ValueError("catalog_dimension_id_mismatch")
        value_ids = [value.value_id for value in self.values]
        if len(value_ids) != len(set(value_ids)):
            raise ValueError("catalog_dimension_value_id_duplicate")
        if self.kind is DimensionKind.ENUM and not self.values:
            raise ValueError("catalog_enum_dimension_requires_values")
        if self.kind is DimensionKind.TEXT and self.values:
            raise ValueError("catalog_text_dimension_rejects_values")
        return self

    def value(self, value_id: str) -> EnumValue | None:
        return next((item for item in self.values if item.value_id == value_id), None)


class CatalogTimeField(DomainModel):
    id: str = Field(pattern=_QUALIFIED_IDENTIFIER)
    model: str = Field(pattern=_IDENTIFIER)
    column: str = Field(pattern=_IDENTIFIER)
    default: bool = False
    description: str = ""

    @model_validator(mode="after")
    def identity_is_coherent(self) -> CatalogTimeField:
        if self.id != f"{self.model}.{self.column}":
            raise ValueError("catalog_time_field_id_mismatch")
        return self


class DefaultFilter(DomainModel):
    dimension_id: str = Field(pattern=_QUALIFIED_IDENTIFIER)
    value_id: str = Field(pattern=_IDENTIFIER)
    assumption: str = Field(min_length=1)


class NullPolicy(DomainModel):
    field: str = Field(pattern=_QUALIFIED_IDENTIFIER)
    treat_as: str = Field(min_length=1)
    assumption: str = Field(min_length=1)


class CatalogMetric(DomainModel):
    id: str = Field(pattern=_IDENTIFIER)
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    review_state: ReviewState
    reviewed_by: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    ambiguity_group: str | None = Field(default=None, pattern=_IDENTIFIER)
    disambiguators: list[str] = Field(default_factory=list)
    base_model: str = Field(pattern=_IDENTIFIER)
    aggregate: Literal["sum"] = "sum"
    row_expression: str = Field(min_length=1)
    zero_literal: str = "CAST(0 AS DECIMAL(12, 2))"
    default_filters: list[DefaultFilter] = Field(default_factory=list)
    null_policy: NullPolicy | None = None
    supported_shapes: list[QueryShape] = Field(min_length=1)
    semantic_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def definition_is_reviewable(self) -> CatalogMetric:
        _synonyms_are_specific(self.synonyms)
        if self.review_state is ReviewState.VERIFIED and not self.reviewed_by:
            raise ValueError("catalog_verified_metric_requires_reviewer")
        if ":" in self.row_expression or ";" in self.row_expression:
            raise ValueError("catalog_metric_expression_invalid")
        if len(set(self.supported_shapes)) != len(self.supported_shapes):
            raise ValueError("catalog_metric_shape_duplicate")
        dimension_ids = [item.dimension_id for item in self.default_filters]
        if len(dimension_ids) != len(set(dimension_ids)):
            raise ValueError("catalog_default_filter_duplicate")
        return self


class SemanticCatalog(DomainModel):
    catalog_revision: str = Field(min_length=1)
    business_timezone: str = Field(pattern=_TIMEZONE_ID)
    models: list[CatalogModel] = Field(min_length=1)
    relationships: list[CatalogRelationship] = Field(default_factory=list)
    metrics: list[CatalogMetric] = Field(min_length=1)
    dimensions: list[CatalogDimension] = Field(default_factory=list)
    time_fields: list[CatalogTimeField] = Field(default_factory=list)
    unsafe_patterns: list[str] = Field(default_factory=list)
    unsupported_patterns: list[str] = Field(default_factory=list)
    semantic_gap_patterns: list[str] = Field(default_factory=list)
    max_top_n: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def references_resolve(self) -> SemanticCatalog:
        model_names = [model.name for model in self.models]
        if len(model_names) != len(set(model_names)):
            raise ValueError("catalog_model_name_duplicate")
        for collection, code in (
            (self.metrics, "catalog_metric_id_duplicate"),
            (self.dimensions, "catalog_dimension_id_duplicate"),
            (self.time_fields, "catalog_time_field_id_duplicate"),
        ):
            ids = [item.id for item in collection]
            if len(ids) != len(set(ids)):
                raise ValueError(code)
        known = set(model_names)
        for dimension in self.dimensions:
            if dimension.model not in known:
                raise ValueError("catalog_dimension_model_unknown")
        defaults_per_model: dict[str, int] = {}
        for time_field in self.time_fields:
            if time_field.model not in known:
                raise ValueError("catalog_time_field_model_unknown")
            if time_field.default:
                defaults_per_model[time_field.model] = (
                    defaults_per_model.get(time_field.model, 0) + 1
                )
        if any(count > 1 for count in defaults_per_model.values()):
            raise ValueError("catalog_default_time_field_duplicate")
        for relationship in self.relationships:
            if relationship.parent_model not in known:
                raise ValueError("catalog_relationship_model_unknown")
            if relationship.child_model not in known:
                raise ValueError("catalog_relationship_model_unknown")
        for metric in self.metrics:
            if metric.base_model not in known:
                raise ValueError("catalog_metric_model_unknown")
            for default_filter in metric.default_filters:
                dimension = self.dimension(default_filter.dimension_id)
                if dimension is None or dimension.kind is not DimensionKind.ENUM:
                    raise ValueError("catalog_default_filter_dimension_invalid")
                if dimension.model != metric.base_model:
                    raise ValueError("catalog_default_filter_model_mismatch")
                if dimension.value(default_filter.value_id) is None:
                    raise ValueError("catalog_default_filter_value_unknown")
        groups: dict[str, list[CatalogMetric]] = {}
        for metric in self.metrics:
            if metric.ambiguity_group is not None:
                groups.setdefault(metric.ambiguity_group, []).append(metric)
        for members in groups.values():
            if len(members) < 2:
                raise ValueError("catalog_ambiguity_group_needs_members")
            if any(not member.disambiguators for member in members):
                raise ValueError("catalog_ambiguity_member_needs_disambiguators")
        if any(not pattern.strip() for pattern in self.unsafe_patterns):
            raise ValueError("catalog_unsafe_pattern_empty")
        if any(not pattern.strip() for pattern in self.unsupported_patterns):
            raise ValueError("catalog_unsupported_pattern_empty")
        if any(not pattern.strip() for pattern in self.semantic_gap_patterns):
            raise ValueError("catalog_semantic_gap_pattern_empty")
        return self

    def model(self, name: str) -> CatalogModel | None:
        return next((item for item in self.models if item.name == name), None)

    def metric(self, metric_id: str) -> CatalogMetric | None:
        return next((item for item in self.metrics if item.id == metric_id), None)

    def dimension(self, dimension_id: str) -> CatalogDimension | None:
        return next((item for item in self.dimensions if item.id == dimension_id), None)

    def time_field(self, time_field_id: str) -> CatalogTimeField | None:
        return next(
            (item for item in self.time_fields if item.id == time_field_id), None
        )

    def default_time_field(self, model_name: str) -> CatalogTimeField | None:
        return next(
            (
                item
                for item in self.time_fields
                if item.model == model_name and item.default
            ),
            None,
        )

    def relationship(
        self, *, parent_model: str, child_model: str
    ) -> CatalogRelationship | None:
        return next(
            (
                item
                for item in self.relationships
                if item.parent_model == parent_model and item.child_model == child_model
            ),
            None,
        )

    def ambiguity_members(self, group: str) -> list[CatalogMetric]:
        return [item for item in self.metrics if item.ambiguity_group == group]

    def relation_grains(self) -> dict[str, list[str]]:
        return {model.name: list(model.grain) for model in self.models}

    def digest(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
