"""Evaluator-owned evidence contract, pinned to accepted history, not candidate globals."""
from hashlib import sha256
import json
from types import MappingProxyType


VERSION = "p3-evidence-expectations-v1"
SCALAR_REQUIRED_CHECKS = (
    "strict_request_and_scope", "reviewed_binding_ast", "strict_schema_and_primary_keys",
    "declared_and_actual_foreign_keys", "declared_check_constraints", "canonical_utc_second_encoding",
    "integer_line_amounts", "read_only_single_transaction", "scalar_result_shape_and_type",
    "execution_budget",
)
GROUPED_REQUIRED_CHECKS = (
    "strict_request_and_scope", "reviewed_binding_ast", "strict_schema_and_primary_keys",
    "declared_and_actual_foreign_keys", "declared_check_constraints", "canonical_utc_second_encoding",
    "integer_line_amounts", "read_only_single_transaction", "execution_budget",
    "reviewed_dimension_binding", "grouped_integer_shape_and_key_bounds",
    "declared_group_coverage_and_row_bound",
)
DIMENSION_PROFILE_ID = "learningops-grouped-amount-v1"
ORDERING = MappingProxyType({
    "booking_day": ("key_asc",),
    "category": ("key_asc_nulls_first",),
    "course": ("value_desc", "key_asc"),
})

_ACCEPTED = "e8c3a455bd4e09a266a772be599fe851d405df78"
PROVENANCE = MappingProxyType({
    "scalar_required_checks": (f"{_ACCEPTED}:grepbit/kernel.py:76-81",),
    "grouped_required_checks": (
        f"{_ACCEPTED}:grepbit/kernel.py:76-81",
        f"{_ACCEPTED}:grepbit/grouped.py:40-43",
        f"{_ACCEPTED}:tests/test_grouped.py:231-232",
    ),
    "dimension_profile_id": (
        f"{_ACCEPTED}:grepbit/grouped.py:26",
        f"{_ACCEPTED}:tests/test_grouped.py:226",
    ),
    "ordering": (
        f"{_ACCEPTED}:docs/grouped-amount.md:46-50",
        f"{_ACCEPTED}:tests/test_grouped.py:213-214",
    ),
})


def identity() -> dict[str, str]:
    payload = {
        "version": VERSION,
        "scalar_required_checks": SCALAR_REQUIRED_CHECKS,
        "grouped_required_checks": GROUPED_REQUIRED_CHECKS,
        "dimension_profile_id": DIMENSION_PROFILE_ID,
        "ordering": dict(ORDERING),
        "provenance": dict(PROVENANCE),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"version": VERSION, "sha256": sha256(encoded).hexdigest()}
