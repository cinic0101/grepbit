"""Layer rulers: domain is pure, ports are neutral, application never sees adapters."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "grepbit"
DOMAIN_THIRD_PARTY = {"pydantic", "pydantic_core"}
FORBIDDEN_DOMAIN_IMPORT_ROOTS = {
    "adapters",
    "application",
    "fastapi",
    "openai",
    "ports",
    "psycopg",
    "sqlglot",
    "yaml",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def is_stdlib(module: str) -> bool:
    return module.split(".")[0] in sys.stdlib_module_names


def test_domain_imports_only_stdlib_pydantic_and_domain() -> None:
    for path in (PACKAGE / "domain").rglob("*.py"):
        for module in imported_modules(path):
            root = module.split(".")[0]
            assert root not in FORBIDDEN_DOMAIN_IMPORT_ROOTS, (
                f"{path.name} imports {module}"
            )
            allowed = (
                is_stdlib(module)
                or root in DOMAIN_THIRD_PARTY
                or module.startswith("grepbit.domain")
            )
            assert allowed, f"{path.name} imports {module}"


def test_ports_import_only_stdlib_and_domain() -> None:
    for path in (PACKAGE / "ports").rglob("*.py"):
        for module in imported_modules(path):
            assert is_stdlib(module) or module.startswith("grepbit.domain"), (
                f"ports/{path.name} imports {module}"
            )


def test_application_never_imports_adapters_or_providers() -> None:
    for path in (PACKAGE / "application").rglob("*.py"):
        for module in imported_modules(path):
            allowed = (
                is_stdlib(module)
                or module.startswith("grepbit.domain")
                or module.startswith("grepbit.ports")
                or module.startswith("grepbit.application")
            )
            assert allowed, f"application/{path.name} imports {module}"


def test_sql_is_built_only_inside_the_sqlglot_adapter() -> None:
    for path in PACKAGE.rglob("*.py"):
        if path.is_relative_to(PACKAGE / "adapters" / "sqlglot"):
            continue
        roots = {module.split(".")[0] for module in imported_modules(path)}
        assert "sqlglot" not in roots, f"{path.relative_to(PACKAGE)} imports sqlglot"
