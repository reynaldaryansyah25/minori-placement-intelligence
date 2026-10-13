"""Guard dependency direction as the modular monolith grows."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def imported_modules(path: Path) -> list[str]:
    modules = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_domain_and_services_depend_inward():
    for layer in ("domain", "services"):
        for path in (ROOT / "backend/minori" / layer).rglob("*.py"):
            for module in imported_modules(path):
                allowed = module.split(".")[0] in sys.stdlib_module_names or (
                    module == "minori.domain" or module.startswith("minori.domain.")
                )
                assert allowed, f"{path.name} imports outward dependency {module}"


def test_frontend_does_not_import_backend_or_database():
    for path in (ROOT / "frontend/minori_frontend").rglob("*.py"):
        for module in imported_modules(path):
            assert module.split(".")[0] not in {"minori", "sqlalchemy", "sqlite3"}, (
                f"{path.name} bypasses the backend HTTP boundary: {module}"
            )
