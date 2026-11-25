"""BR-U7-19/20/21: contrato del ServiceMonitor standalone (sin Helm).

Sin dependencia de PyYAML en el proyecto: se valida el contrato textual que
consume el Prometheus Operator (selector, namespace, puerto y ausencia de
``interval``/``scrapeTimeout`` para heredar los defaults del operador).
"""

from __future__ import annotations

from pathlib import Path

SERVICE_MONITOR = (
    Path(__file__).resolve().parents[2] / "deploy" / "monitoring" / "servicemonitor.yaml"
)


def test_servicemonitor_contract() -> None:
    text = SERVICE_MONITOR.read_text(encoding="utf-8")
    assert "kind: ServiceMonitor" in text
    assert "apiVersion: monitoring.coreos.com/v1" in text
    assert "name: sentinel-core" in text
    assert "namespace: sentinel" in text
    assert "release: monitoring" in text
    assert "app.kubernetes.io/name: sentinel-core" in text
    assert "matchNames:\n      - sentinel" in text
    assert "port: metrics" in text
    assert "path: /metrics" in text
    assert "interval:" not in text
    assert "scrapeTimeout:" not in text
