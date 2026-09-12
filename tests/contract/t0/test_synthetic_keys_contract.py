"""A declared FK target is unique even when it is not the parent's PK."""

import random

import pytest

from evals.synthetic import random_instance
from grepbit.domain.schema_model import SchemaModel


def natural_key_schema(kind):
    return SchemaModel.model_validate(
        {
            "datasource_id": "synthetic_keys",
            "schema_name": "public",
            "business_timezone": "Asia/Taipei",
            "tables": [
                {
                    "name": "projects",
                    "primary_key": ["id"],
                    "columns": [
                        {
                            "name": "id",
                            "kind": "numeric",
                            "data_type": "integer",
                            "nullable": False,
                        },
                        {
                            "name": "project_key",
                            "kind": kind,
                            "data_type": "integer" if kind == "numeric" else "text",
                            "nullable": False,
                        },
                    ],
                },
                {
                    "name": "tickets",
                    "primary_key": ["id"],
                    "columns": [
                        {
                            "name": "id",
                            "kind": "numeric",
                            "data_type": "integer",
                            "nullable": False,
                        },
                        {
                            "name": "project_key",
                            "kind": kind,
                            "data_type": "integer" if kind == "numeric" else "text",
                            "nullable": True,
                        },
                    ],
                },
            ],
            "foreign_keys": [
                {
                    "table": "tickets",
                    "column": "project_key",
                    "referenced_table": "projects",
                    "referenced_column": "project_key",
                }
            ],
        }
    )


@pytest.mark.parametrize("kind", ["text", "numeric"])
def test_random_instances_preserve_declared_natural_key_uniqueness(kind):
    schema = natural_key_schema(kind)
    for seed in range(20):
        tables = random_instance(schema, random.Random(seed))
        keys = [row["project_key"] for row in tables["projects"]]
        assert len(keys) == len(set(keys))
        assert None not in keys
        if kind == "numeric":
            # Distinct values expose a join that accidentally uses the first PK.
            assert set(keys).isdisjoint(row["id"] for row in tables["projects"])
        assert any(row["project_key"] in keys for row in tables["tickets"])
