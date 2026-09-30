"""A copy of the candidate registry whose current candidate gains a same-bytes twin.

The gate's `same_bytes` refusal and the aggregate's same-bytes inclusion need two
registered ids with one model-facing identity. The real registry has such a pair
only while the current candidate repeats earlier bytes (v12 repeated v7), so
these rulers build the pair instead of assuming it of whichever candidate is
current.
"""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools import candidate_registry as registry

TWIN = "p3-registry-twin-of-current"


def use(test) -> tuple[str, str]:
    """Serve the twin registry for the rest of `test`; returns (twin id, same-bytes sibling id).

    The twin is appended as the new current entry, so the live runtime still
    passes `registry.check()`; the sibling is the real current candidate.
    """
    tmp = tempfile.TemporaryDirectory(prefix="registry-twin-", dir=registry.ROOT / ".artifacts")
    test.addCleanup(tmp.cleanup)
    directory = Path(tmp.name)
    for path in registry.INDEX.parent.glob("*.json"):
        shutil.copyfile(path, directory / path.name)
    index_path = directory / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    head = registry.current()
    twin = dict(head, candidate_id=TWIN, ancestor=head["candidate_id"], ancestor_sha256=index["entries"][-1]["sha256"],
                note="Test twin: the current candidate's model-facing bytes under another id.")
    text = json.dumps(twin, indent=2, ensure_ascii=False) + "\n"
    (directory / f"{TWIN}.json").write_text(text, encoding="utf-8")
    index["entries"].append({"candidate_id": TWIN, "path": f"{TWIN}.json",
                             "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                             "ancestor": head["candidate_id"]})
    index["current"] = TWIN
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    patcher = patch.object(registry, "INDEX", index_path)
    patcher.start()
    test.addCleanup(patcher.stop)
    return TWIN, head["candidate_id"]
