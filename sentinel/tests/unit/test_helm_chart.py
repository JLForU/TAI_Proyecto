"""Validación estructural local del chart de Helm de Sentinel (U9, ST-M8-01..04)."""

from __future__ import annotations

from pathlib import Path

CHART_DIR = Path(__file__).resolve().parents[2] / "charts" / "sentinel"


def test_helm_chart_workloads_and_entrypoints() -> None:
    chart_yaml = (CHART_DIR / "Chart.yaml").read_text(encoding="utf-8")
    values_yaml = (CHART_DIR / "values.yaml").read_text(encoding="utf-8")
    core_tpl = (CHART_DIR / "templates" / "core.yaml").read_text(encoding="utf-8")
    workloads_tpl = (CHART_DIR / "templates" / "workloads.yaml").read_text(encoding="utf-8")

    assert "name: sentinel" in chart_yaml
    assert "sentinel.core" in values_yaml
    assert "sentinel.discovery" in values_yaml
    assert "sentinel.traffic" in values_yaml
    assert "kind: Deployment" in core_tpl
    assert "kind: Service" in core_tpl
    assert "kind: PersistentVolumeClaim" in core_tpl
    assert "kind: CronJob" in workloads_tpl
    assert "app.kubernetes.io/name: sentinel-traffic" in workloads_tpl
