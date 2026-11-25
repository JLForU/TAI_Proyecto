"""Frontera de imports de ``baseline/`` (BR-U6-01, unit-of-work §imports).

AST-based: el paquete importa solo ``sentinel.foundation.*`` + stdlib —
**nunca** ``sentinel.core.*`` ni ``sqlite3``; ``scapy`` = 0 en todo ``src/``.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "sentinel"
BASELINE = SRC / "baseline"


_STDLIB = {
    "__future__",
    "ast",
    "collections",
    "dataclasses",
    "datetime",
    "pathlib",
    "re",
    "typing",
    "uuid",
    "logging",
    "json",
    "sys",
    "os",
    "time",
    "enum",
    "math",
    "statistics",
    "functools",
    "itertools",
    "abc",
    "contextlib",
}


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                found.add("sentinel.baseline")  # import relativo dentro del paquete
            elif node.module:
                found.add(node.module)
    return found


def test_baseline_imports_only_foundation_and_stdlib() -> None:
    allowed_prefixes = ("sentinel.foundation", "sentinel.baseline")
    for path in _py_files(BASELINE):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imports(tree):
            if module == "sentinel" or module.startswith("sentinel."):
                assert any(module == p or module.startswith(p + ".") for p in allowed_prefixes), (
                    f"{path.name} importa módulo core-servicio prohibido: {module}"
                )
            else:
                root = module.split(".")[0]
                # stdlib conocido o terceros mínimos (pytest solo en tests)
                assert root in _STDLIB | {"pytest", "pydantic"}, (
                    f"{path.name} importa no-foundation: {module}"
                )


def test_baseline_never_imports_core_nor_sqlite() -> None:
    forbidden = {"sqlite3", "sentinel.core"}
    for path in _py_files(BASELINE):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imports(tree):
            assert not any(module == f or module.startswith(f + ".") for f in forbidden), (
                f"{path.name} viola BR-U6-01: importa {module}"
            )


def test_scapy_zero_in_src() -> None:
    offenders = [
        str(p.relative_to(SRC.parent))
        for p in _py_files(SRC)
        if "scapy" in _imports(ast.parse(p.read_text(encoding="utf-8"), filename=str(p)))
    ]
    assert offenders == []


def test_baseline_dir_exists() -> None:
    assert BASELINE.is_dir()
    assert {p.name for p in _py_files(BASELINE)} == {
        "__init__.py",
        "config.py",
        "statistics.py",
        "conditions.py",
        "indicators.py",
    }
