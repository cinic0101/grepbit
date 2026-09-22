"""Historical byte witness for archive tests; never admit the current checkout as frozen."""
import json
from pathlib import Path
import subprocess

from tools import p3_admission, p3_expectations

ROOT = Path(__file__).resolve().parents[1]


def historical_bytes(name):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "show", f"{p3_admission.FROZEN_CANDIDATE}:{name}"],
        cwd=ROOT, timeout=5)


def historical_candidate():
    baseline = json.loads((ROOT / "tests/fixtures/p310_identity_baseline.json").read_bytes())
    return {"candidate_freeze_sha": p3_admission.FROZEN_CANDIDATE,
            "declared_at": p3_admission.FREEZE_DECLARED_AT,
            "declaration": "https://github.com/cinic0101/grepbit/issues/43",
            "files_sha256": baseline["protected_files_sha256"],
            "evidence_expectations": p3_expectations.identity()}
