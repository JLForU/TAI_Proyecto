"""Tests del paquete: sin side effects, sin I/O prohibido, sin entrypoint (BR-19, BR-27)."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

FOUNDATION_DIR = Path(__file__).resolve().parents[3] / "src" / "sentinel" / "foundation"

FORBIDDEN_IMPORTS = ("fastapi", "sqlite3", "scapy", "nmap", "socket", "kubernetes")


def test_import_has_no_env_side_effects() -> None:
    code = (
        "import os, sys;"
        "os.environ['SENTINEL_LOG_LEVEL'] = 'TOTALLY_INVALID';"
        "import sentinel.foundation;"
        "sys.exit(0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(FOUNDATION_DIR.parents[2]),
        env={"PYTHONPATH": str(FOUNDATION_DIR.parents[1]), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr


def test_foundation_has_no_forbidden_imports() -> None:
    for path in FOUNDATION_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IMPORTS:
            assert f"import {forbidden}" not in source, f"{path} imports {forbidden}"
            assert f"from {forbidden}" not in source, f"{path} imports from {forbidden}"


def test_module_is_not_an_entrypoint() -> None:
    src = str(FOUNDATION_DIR.parents[1])
    result = subprocess.run(
        [sys.executable, "-m", "sentinel.foundation"],
        capture_output=True,
        text=True,
        cwd=str(FOUNDATION_DIR.parents[2]),
        env={"PYTHONPATH": src, "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "cannot be directly executed" in combined or "library" in combined


def test_reimport_is_idempotent() -> None:
    module = importlib.import_module("sentinel.foundation")
    module2 = importlib.import_module("sentinel.foundation")
    assert module is module2


def test_public_api_exports() -> None:
    import sentinel.foundation as foundation

    for name in foundation.__all__:
        assert hasattr(foundation, name), name
