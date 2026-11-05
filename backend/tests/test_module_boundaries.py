import ast
import unittest
from pathlib import Path

DOMAINS = {"drill_mcp", "evaluations", "refunds", "simulations", "workflows"}
OFFLINE_DOMAINS = ("evaluations", "refunds", "workflows")
APP_ROOT = Path(__file__).parents[1] / "app"
MAX_SOURCE_LINES = 250
MAX_TEST_LINES = 350


class ModuleBoundaryTests(unittest.TestCase):
    def test_python_files_stay_within_size_limits(self) -> None:
        violations: list[str] = []

        for root, limit in ((APP_ROOT, MAX_SOURCE_LINES), (Path(__file__).parent, MAX_TEST_LINES)):
            for path in root.rglob("*.py"):
                line_count = len(path.read_text().splitlines())
                if line_count > limit:
                    violations.append(f"{path}: {line_count} lines, limit {limit}")

        self.assertEqual(violations, [])

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

    def test_offline_domains_have_no_network_client_import(self) -> None:
        prohibited = {"aiohttp", "httpx", "requests", "socket"}
        violations: list[str] = []
        paths = [path for domain in OFFLINE_DOMAINS for path in (APP_ROOT / domain).rglob("*.py")]

        for path in paths:
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = {node.module.split(".")[0]}
                else:
                    continue
                if names & prohibited:
                    violations.append(f"{path}: {node.lineno}: {sorted(names & prohibited)}")

        self.assertEqual(violations, [])

