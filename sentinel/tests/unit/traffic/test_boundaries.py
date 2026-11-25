"""Frontera de imports de ``sentinel.traffic`` (U5, BR-U5-32/33)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAFFIC_PKG = REPO_ROOT / "src" / "sentinel" / "traffic"
SRC_ROOT = REPO_ROOT / "src"
REQUIREMENTS = REPO_ROOT / "requirements.txt"


def _module_imports() -> set[str]:
    """Nombres importados por el paquete (absolutos y relativos con punto)."""
    found: set[str] = set()
    for path in sorted(TRAFFIC_PKG.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * node.level
                found.add(prefix + (node.module or ""))
    return found


def test_boundary_no_core_no_sqlite() -> None:
    imports = _module_imports()
    assert not any(name == "sentinel.core" or name.startswith("sentinel.core") for name in imports)
    assert "sqlite3" not in imports
    # solo foundation dentro de sentinel (más los módulos propios relativos)
    for name in imports:
        if name.startswith("sentinel."):
            assert name.startswith("sentinel.foundation") or name.startswith("sentinel.traffic"), (
                name
            )


def test_boundary_relative_imports_stay_in_package() -> None:
    imports = _module_imports()
    for name in imports:
        if name.startswith("."):
            target = name.lstrip(".").split(".")[0]
            assert target != "core", name


def test_no_scapy_anywhere_in_src() -> None:
    """BR-U5-33: sin código de captura real — grep scapy en src/ ⇒ 0."""
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "scapy" not in text, path


def test_no_capture_dependency_in_requirements() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8").lower()
    assert "scapy" not in requirements
    assert "pypcap" not in requirements
