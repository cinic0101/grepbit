"""The frozen v10 recipe output schema, restored by v12, that `grepbit/bedrock.py` pins.

v11 and v13 fail closed on `bedrock_converse` (docs/count-cue-policy.md,
docs/count-assumption-v13.md). Tests of the Bedrock adapter and of historical
Bedrock tools keep exercising the unchanged compaction against this frozen copy
instead of the current schema.
"""
import copy
import json
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parent / "fixtures/recipe-output-schema-v2.json"
_SCHEMA = json.loads(PATH.read_text(encoding="utf-8"))


def schema() -> dict:
    return copy.deepcopy(_SCHEMA)


def patched():
    """Serve the frozen schema wherever the runtime asks for the recipe output schema."""
    return patch("grepbit.recipe_model.output_schema", new=schema)
