"""Research-only faithful presentation and reversible candidate factorization."""

import hashlib
import json
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.metric_wire_selection import (
    OccurrenceInterpretation,
    Selection,
    bind_selection,
)


def conditional(properties, then, *, required=None):
    return {
        "if": {"properties": properties, "required": required or list(properties)},
        "then": then,
    }


def shown_interpretation(schema, concepts):
    """Describe existing constraints; the unchanged runtime is still mandatory."""
    shown = deepcopy(OccurrenceInterpretation.model_json_schema())
    span = shown["$defs"]["OccurrenceSpan"]
    scopes = {
        "output_action": ["output"],
        "mention_only": ["output_label"],
        "grouping_constraint": ["grouping"],
        "business_predicate": ["population", "numerator", "denominator"],
        "unresolved": ["population", "numerator", "denominator"],
    }
    span["properties"]["concept"] = {"enum": [None, *sorted(concepts)]}
    span["allOf"] = []
    for role, allowed in scopes.items():
        fields = {"scope": {"enum": allowed}}
        if role == "business_predicate":
            fields["concept"] = {"type": "string"}
        elif role != "unresolved":
            fields["concept"] = {"const": None}
        span["allOf"].append(
            conditional(
                {"role": {"const": role}},
                {
                    "properties": fields,
                    **(
                        {"required": ["concept"]}
                        if role == "business_predicate"
                        else {}
                    ),
                },
            )
        )
    basis = shown["$defs"]["Basis"]
    basis["properties"]["entity"] = {"enum": [t.name for t in schema.tables]}
    basis["allOf"] = [
        conditional(
            {"aggregate": {"enum": ["sum", "count_distinct"]}},
            {"properties": {"column": {"type": "string"}}},
        )
    ]
    for table in schema.tables:
        # Preserve the old integrity validator's empty-string tolerance. This
        # renderer does not silently turn that tolerance into a new contract.
        basis["allOf"].append(
            conditional(
                {"entity": {"const": table.name}},
                {
                    "properties": {
                        "column": {
                            "enum": [
                                None,
                                "",
                                *[f"{table.name}.{c.name}" for c in table.columns],
                            ]
                        }
                    }
                },
            )
        )
    shown["$defs"]["Requirement"]["properties"]["concept"] = {"enum": sorted(concepts)}

    def role(value):
        return {"properties": {"role": {"const": value}}, "required": ["role"]}

    shown["properties"]["basis"]["oneOf"] = [
        {"maxItems": 0},
        {"minItems": 1, "maxItems": 1, "items": role("value")},
        {
            "minItems": 2,
            "maxItems": 2,
            "allOf": [
                {"contains": role("numerator")},
                {"contains": role("denominator")},
            ],
        },
    ]
    shown["properties"]["unresolved"]["uniqueItems"] = True
    shown["allOf"] = [
        conditional(
            {"state": {"const": "clear"}},
            {
                "properties": {
                    "unresolved": {"maxItems": 0},
                    "basis": {"minItems": 1},
                    "requirements": {
                        "items": {
                            "properties": {
                                "concept": {
                                    "enum": sorted(
                                        k for k, v in concepts.items() if v is not None
                                    ),
                                }
                            }
                        }
                    },
                }
            },
        ),
        conditional(
            {"state": {"enum": ["ambiguous", "missing_definition"]}},
            {"properties": {"unresolved": {"minItems": 1}}},
        ),
        conditional(
            {"state": {"const": "missing_definition"}},
            {
                "properties": {
                    "unresolved": {
                        "contains": {"const": "business_binding"},
                    }
                }
            },
        ),
    ]
    for roles, scopes_for_roles in (
        (["value"], ["population"]),
        (["numerator", "denominator"], ["numerator", "denominator"]),
    ):
        shown["allOf"].append(
            conditional(
                {"state": {"const": "clear"}, "basis": {"contains": role(roles[0])}},
                {
                    "properties": {
                        "populations": {
                            "required": scopes_for_roles,
                            "properties": {
                                s: {"enum": ["all_rows", "constrained"]}
                                for s in scopes_for_roles
                            },
                            "additionalProperties": False,
                        },
                        "requirements": {
                            "items": {
                                "properties": {
                                    "role": {"enum": scopes_for_roles},
                                }
                            }
                        },
                    }
                },
            )
        )
    for scope in ("population", "numerator", "denominator"):
        restricted = {
            "properties": {
                "role": {"const": scope},
                "polarity": {"enum": ["include", "exclude"]},
            },
            "required": ["role", "polarity"],
        }
        for policy in ("constrained", "all_rows"):
            restriction = {"contains": restricted}
            if policy == "all_rows":
                restriction = {"not": restriction}
            shown["allOf"].append(
                conditional(
                    {
                        "state": {"const": "clear"},
                        "populations": {
                            "properties": {scope: {"const": policy}},
                            "required": [scope],
                        },
                    },
                    {"properties": {"requirements": restriction}},
                )
            )
        for concept in concepts:
            shown["allOf"].append(
                {
                    "properties": {
                        "requirements": {
                            "contains": {
                                "properties": {
                                    "role": {"const": scope},
                                    "concept": {"const": concept},
                                },
                                "required": ["role", "concept"],
                            },
                            "minContains": 0,
                            "maxContains": 1,
                        }
                    }
                }
            )
    return shown


class FactorPair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    basis_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)


class FactoredSelection(BaseModel):
    """Proposed pair envelope with the old decision/role/decline semantics."""

    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["pick", "clarify", "no_candidate"]
    slots: dict[Literal["value", "numerator", "denominator"], FactorPair]
    output_label: str | None
    reason: Literal["ambiguous", "missing_definition", "outside_catalog"] | None

    @model_validator(mode="after")
    def original_envelope_rules(self):
        Selection.model_validate(
            {
                **self.model_dump(),
                "slots": {
                    role: json.dumps(pair.model_dump(), sort_keys=True)
                    for role, pair in self.slots.items()
                },
            }
        )
        return self


def identity(prefix, definition):
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(encoded.encode()).hexdigest()[:16]


def factor_catalog(candidates):
    bases, populations, pairs = {}, {}, {}
    if len(candidates) > 64 or len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("invalid_original_catalog")
    for candidate in candidates:
        basis = {k: candidate[k] for k in ("base_table", "operation", "column")}
        population = {
            "base_table": candidate["base_table"],
            "predicates": candidate["population"],
        }
        bid, pid = identity("b_", basis), identity("p_", population)
        if (bid in bases and bases[bid] != basis) or (
            pid in populations and populations[pid] != population
        ):
            raise ValueError("factor_id_collision")
        if (bid, pid) in pairs:
            raise ValueError("duplicate_pair_identity")
        bases[bid], populations[pid] = basis, population
        pairs[bid, pid] = deepcopy(candidate)
    return bases, populations, pairs


def factor_cards(candidates):
    bases, populations, pairs = factor_catalog(candidates)
    return {
        "bases": [{"id": k, **v} for k, v in sorted(bases.items())],
        "populations": [{"id": k, **v} for k, v in sorted(populations.items())],
        "allowed_pairs": [
            {
                "basis_id": b,
                "population_id": p,
                "reviewed_metrics": c["reviewed_metrics"],
            }
            for (b, p), c in sorted(pairs.items())
        ],
    }


def bind_factors(payload, candidates, question):
    parsed = FactoredSelection.model_validate(payload)
    _, _, pairs = factor_catalog(candidates)
    slots = {}
    for role, pair in parsed.slots.items():
        key = (pair.basis_id, pair.population_id)
        if key not in pairs:
            raise ValueError("pair_not_offered")
        slots[role] = pairs[key]["id"]
    # Preserve the original operand verbatim, including metric provenance.
    return bind_selection({**parsed.model_dump(), "slots": slots}, candidates, question)
