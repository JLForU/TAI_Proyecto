"""Validación estructural local de los artefactos de observabilidad de U8."""

from __future__ import annotations

import json
from pathlib import Path

MONITORING_DIR = Path(__file__).resolve().parents[2] / "deploy" / "monitoring"


def test_prometheus_rule_implemented_alerts_and_no_high_cardinality() -> None:
    content = (MONITORING_DIR / "prometheusrule.yaml").read_text(encoding="utf-8")
    assert "kind: PrometheusRule" in content
    assert "alert: TrafficThresholdExceeded" in content
    assert "alert: SensorUnavailable" in content
    assert "sentinel_traffic_threshold_exceeded" in content
    assert "sentinel_collector_up" in content
    # Sin etiquetas de alta cardinalidad (IP, MAC, puerto)
    for forbidden in ("src_ip", "dst_ip", "mac", "port"):
        assert forbidden not in content


def test_grafana_dashboards_and_values_structure() -> None:
    dashboards = json.loads(
        (MONITORING_DIR / "grafana-dashboards.json").read_text(encoding="utf-8")
    )
    titles = {panel["title"] for panel in dashboards["panels"]}
    assert titles == {
        "Asset Inventory",
        "Traffic Baselines & Throughput",
        "Alerts & Threshold State",
        "Sensor Health",
    }

    values_text = (MONITORING_DIR / "values-monitoring.yaml").read_text(encoding="utf-8")
    assert "webhook_configs" in values_text
    assert "ST-M7-06" in values_text
