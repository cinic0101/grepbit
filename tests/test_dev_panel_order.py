"""Order-only dev registration must retain every case and its original oracle."""
import hashlib
from pathlib import Path
import unittest

from tools import evaluate, p3_assets

ROOT = Path(__file__).resolve().parents[1]
PANEL_ID = "p3-dev-matrix-boundaries-first-v1"


class DevPanelOrderTests(unittest.TestCase):
    def test_registered_order_preserves_all_cases_oracles_and_exposure(self):
        entries = {row["panel_id"]: row for row in evaluate.load_panels()["panels"]}
        self.assertIn(PANEL_ID, entries, "Register the order-only panel before observing it")
        original_entry = entries["p3-dev-matrix-v1"]
        entry = entries[PANEL_ID]
        original = p3_assets.load_panel(ROOT / original_entry["path"])
        ordered = p3_assets.load_panel(ROOT / entry["path"])
        self.assertEqual((entry["tier"], entry["authoring"], entry["allocation_policy"], entry["freeze"], entry["intake"]),
                         ("dev", "development", None, None, None))
        self.assertEqual(len(ordered.cases), 54)
        self.assertEqual({c.case_id: c for c in ordered.cases}, {c.case_id: c for c in original.cases})
        self.assertEqual(ordered.oracles, original.oracles)
        for name, old, new in (("cases", original.cases_path, ordered.cases_path),
                               ("oracles", original.oracles_path, ordered.oracles_path)):
            self.assertEqual(new, old)
            self.assertEqual(entry["assets"][name], original_entry["assets"][name])
            self.assertEqual(entry["assets"][name], hashlib.sha256(new.read_bytes()).hexdigest())
        self.assertEqual(entry["assets"]["panel"], hashlib.sha256(ordered.path.read_bytes()).hexdigest())
        ids = [c.case_id for c in ordered.cases]
        languages = ("zh-TW", "en", "ja")
        self.assertEqual(ids[:12], [f"dev-{row}.{lang}" for row in ("D8", "C4", "C1", "D4") for lang in languages])
        self.assertEqual(ids[-9:], [f"dev-{row}.{lang}" for row in ("A3", "A4", "C2") for lang in languages])


if __name__ == "__main__":
    unittest.main()
