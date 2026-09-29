"""Archived v11 evidence vocabulary is pinned in the report reader (#79).

v11 reports must stay readable after a candidate that lacks
grepbit/count_policy.py and v11's recipe_model vocabulary (the v10 fallback).
"""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from grepbit import recipe_model
from tools import p3_assets, p3_live_evidence as live

ROOT = Path(__file__).resolve().parents[1]
V10_REASONS = ("root_shape", "unknown_recipe", "request_fields", "request_values", "clarification_shape",
               "choice_count", "choice_shape", "choice_values", "choice_consistency", "question_binding",
               "export_drift")
PINNED = {
    "ARCHIVED_INVALID_REQUEST_REASONS": (*V10_REASONS, "count_cue_shape", "count_cue_values", "count_cue_binding"),
    "ARCHIVED_COUNT_READINGS": ("absent", "none", "bound", "contrast", "generic"),
    "ARCHIVED_ACTION_SOURCES": ("model", "count_policy"),
    "ARCHIVED_COUNT_POLICY_RULES": ("other_unsupported", "bound_seats", "bound_unsupported", "contrast_unexecutable",
                                    "contrast", "generic_booking", "generic_unframed"),
}
_STAGES = dict.fromkeys(recipe_model.protocol.STAGES, "passed")
V11_ROWS = [
    {"http_status": 200, "stages": _STAGES, "error_code": None, "stop_reason": None,
     "invalid_request_reason": None, "count_reading": "generic", "action_source": "count_policy",
     "count_policy_rule": "generic_booking"},
    {"http_status": 200, "stages": _STAGES, "error_code": None, "stop_reason": None,
     "invalid_request_reason": None, "count_reading": "absent", "action_source": "model",
     "count_policy_rule": None},
    {"http_status": 200, "stages": {**_STAGES, "request_validation": "failed", "kernel_execution": "not_run"},
     "error_code": "invalid_request", "stop_reason": None, "invalid_request_reason": "count_cue_binding",
     "count_reading": "bound", "action_source": None, "count_policy_rule": None},
]
INVALID_ROWS = [
    {**V11_ROWS[0], "count_policy_rule": "generic_unknown"},
    {**V11_ROWS[1], "count_reading": "headcount"},
    {**V11_ROWS[2], "invalid_request_reason": "count_cue_scope"},
]
# Simulates a v10-shaped runtime: no count_policy module and v10's reason set.
_WITHOUT_V11_RUNTIME = """
import json, sys
import grepbit, grepbit.recipe_model as runtime
for name in ("ACTION_SOURCES", "COUNT_READINGS"):
    runtime.__dict__.pop(name, None)
runtime.INVALID_REQUEST_REASONS = tuple(json.loads(sys.argv[1]))
grepbit.__dict__.pop("count_policy", None)
sys.modules["grepbit.count_policy"] = None
from tools import p3_assets, p3_live_evidence as live
for row in json.loads(sys.argv[2]):
    assert live._evidence(row) == row, row
for row in json.loads(sys.argv[3]):
    try:
        live._evidence(row)
    except p3_assets.P3Error:
        continue
    raise AssertionError(row)
print("archived-v11-readback-ok")
"""


class ArchivedEvidenceVocabularyTests(unittest.TestCase):
    def test_reader_does_not_import_runtime_count_vocabulary(self):
        tree = ast.parse((ROOT / "tools/p3_live_evidence.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertNotIn("grepbit.count_policy", {alias.name for alias in node.names})
            if isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names}
                self.assertNotEqual(node.module, "grepbit.count_policy")
                self.assertNotIn("count_policy", names if node.module == "grepbit" else set())
                if node.module == "grepbit.recipe_model":
                    self.assertFalse(names & {"ACTION_SOURCES", "COUNT_READINGS", "INVALID_REQUEST_REASONS"})

    def test_archived_vocabulary_is_pinned(self):
        for name, value in PINNED.items():
            self.assertEqual(getattr(live, name), value, name)

    def test_current_runtime_vocabulary_is_covered(self):
        self.assertLessEqual(set(recipe_model.INVALID_REQUEST_REASONS), set(live.ARCHIVED_INVALID_REQUEST_REASONS))
        self.assertLessEqual(set(getattr(recipe_model, "COUNT_READINGS", ())), set(live.ARCHIVED_COUNT_READINGS))
        self.assertLessEqual(set(getattr(recipe_model, "ACTION_SOURCES", ())), set(live.ARCHIVED_ACTION_SOURCES))
        if importlib.util.find_spec("grepbit.count_policy") is not None:
            from grepbit import count_policy
            self.assertLessEqual(set(count_policy.RULES), set(live.ARCHIVED_COUNT_POLICY_RULES))

    def test_v11_evidence_is_validated_in_process(self):
        for row in V11_ROWS:
            self.assertEqual(live._evidence(row), row)
        for row in INVALID_ROWS:
            with self.assertRaises(p3_assets.P3Error):
                live._evidence(row)

    def test_v11_evidence_reads_back_without_v11_runtime(self):
        completed = subprocess.run(
            [sys.executable, "-c", _WITHOUT_V11_RUNTIME, json.dumps(V10_REASONS), json.dumps(V11_ROWS),
             json.dumps(INVALID_ROWS)],
            cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
            timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        self.assertEqual(completed.stdout.strip(), "archived-v11-readback-ok")


if __name__ == "__main__":
    unittest.main()
