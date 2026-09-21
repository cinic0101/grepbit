"""Keep uv environment management compatible with the accepted frozen closure."""
from importlib import metadata
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DependencyTests(unittest.TestCase):
    def test_direct_dependencies_match_frozen_declarations(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(project["project"]["dependencies"]),
            sorted((ROOT / "requirements.in").read_text(encoding="utf-8").splitlines()),
        )
        self.assertEqual(project["project"]["requires-python"], ">=3.11")
        self.assertIs(project["tool"]["uv"]["package"], False)
        self.assertNotIn("build-system", project)

    def test_lock_matches_frozen_closure_and_project_metadata(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        registry = [item for item in lock["package"] if "registry" in item["source"]]
        self.assertEqual(
            sorted(f'{item["name"]}=={item["version"]}' for item in registry),
            sorted((ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()),
        )
        self.assertEqual(lock["requires-python"], project["project"]["requires-python"])
        virtual = [item for item in lock["package"] if item["source"] == {"virtual": "."}]
        self.assertEqual(len(virtual), 1)
        self.assertEqual(len(lock["package"]), len(registry) + 1)
        self.assertEqual(virtual[0]["name"], project["project"]["name"])
        self.assertEqual(virtual[0]["version"], project["project"]["version"])
        self.assertEqual(
            sorted(item["name"] + item["specifier"]
                   for item in virtual[0]["metadata"]["requires-dist"]),
            sorted(project["project"]["dependencies"]),
        )

    def test_installed_versions_match_locked_closure(self):
        lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        for item in lock["package"]:
            if "registry" in item["source"]:
                with self.subTest(dependency=item["name"]):
                    self.assertEqual(metadata.version(item["name"]), item["version"])


if __name__ == "__main__":
    unittest.main()
