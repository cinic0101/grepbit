"""STATE.md rulers (#87 step 4): the committed handoff page equals the one generated from the registries."""
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import state

ROOT = Path(__file__).resolve().parents[1]


class StatePageRulers(unittest.TestCase):
    def test_committed_state_page_is_current_and_deterministic(self):
        rendered = state.render()
        self.assertEqual(rendered, state.render())
        self.assertEqual((ROOT / "STATE.md").read_text(encoding="utf-8"), rendered,
                         "STATE.md is stale: run .venv/bin/python tools/state.py --write and commit it")
        for heading in ("## Current candidate", "## Panels and latest results per route", "## Routes",
                        "## Last runs", "## Where the work lives"):
            self.assertIn(heading, rendered)
        self.assertIn("`p3-holdout-a-v2` | holdout", rendered)
        self.assertIn("Nothing here is promotion.", rendered)

    def test_cli_check_and_write_are_closed(self):
        with patch("sys.stdout"), patch("sys.stderr"):
            self.assertEqual(state.main(["--check"]), 0)
            self.assertEqual(state.main(["--bogus"]), 2)
            with patch.object(state, "STATE", ROOT / ".artifacts" / "state-ruler-missing.md"):
                self.assertEqual(state.main(["--check"]), 1)


if __name__ == "__main__":
    unittest.main()
