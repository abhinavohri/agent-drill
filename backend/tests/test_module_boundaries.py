import ast
import unittest
from pathlib import Path

DOMAINS = {"drill_mcp", "simulations"}
APP_ROOT = Path(__file__).parents[1] / "app"


class ModuleBoundaryTests(unittest.TestCase):
    def test_domains_do_not_import_another_domains_internal_package(self) -> None:
        violations: list[str] = []

        for path in APP_ROOT.rglob("*.py"):
            relative_parts = path.relative_to(APP_ROOT).parts
            owner = relative_parts[0] if relative_parts[0] in DOMAINS else None
            tree = ast.parse(path.read_text(), filename=str(path))

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                parts = node.module.split(".")
                if len(parts) < 4 or parts[0] != "app" or parts[2] != "internal":
                    continue
                imported_domain = parts[1]
                if imported_domain in DOMAINS and imported_domain != owner:
                    violations.append(f"{path}: {node.lineno}: {node.module}")

        self.assertEqual(violations, [])

