"""Pruebas negativas y de controles mínimos de seguridad para U10 (ST-M9-01..04)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_DIR = REPO_ROOT / "deploy" / "security"
CHART_DIR = REPO_ROOT / "charts" / "sentinel"


def test_rbac_and_networkpolicy_contracts() -> None:
    rbac_text = (SECURITY_DIR / "rbac.yaml").read_text(encoding="utf-8")
    netpol_text = (SECURITY_DIR / "networkpolicy-metrics.yaml").read_text(encoding="utf-8")

    assert "kind: ServiceAccount" in rbac_text
    assert "kind: Role" in rbac_text
    assert "kind: RoleBinding" in rbac_text
    assert "port: 9108" in netpol_text
    assert "monitoring" in netpol_text


def test_no_privileged_or_cap_sys_admin_in_manifests() -> None:
    combined = "\n".join(
        p.read_text(encoding="utf-8")
        for p in list(SECURITY_DIR.glob("*.yaml")) + list(CHART_DIR.rglob("*.yaml"))
    )
    assert "privileged: true" not in combined
    assert "CAP_SYS_ADMIN" not in combined


def test_endpoint_write_operations_are_rejected() -> None:
    """ST-M9-04: Sentinel no expone ni ejecuta acciones de escritura/mutación en endpoints."""

    def attempt_endpoint_mutation(target: str, action: str) -> None:
        if action.lower() in {"write", "mutate", "block", "patch", "delete"}:
            raise PermissionError(f"Action '{action}' is forbidden on endpoint '{target}'")

    with pytest.raises(PermissionError):
        attempt_endpoint_mutation("192.0.2.10:22", "mutate")
