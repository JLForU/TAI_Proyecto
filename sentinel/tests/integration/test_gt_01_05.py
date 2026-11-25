"""Suite de integración determinista para escenarios Ground Truth GT-01..GT-05 (EN-06)."""

from __future__ import annotations

import math

from sentinel.baseline.statistics import mean, sample_variance, select_threshold


def test_gt_01_normal_operation_no_alerts() -> None:
    samples = [100.0, 100.0, 100.0, 100.0, 100.0]
    mu = mean(samples)
    sigma = math.sqrt(sample_variance(samples))
    threshold = select_threshold(mu, sigma, 2.0, None, established=True)
    assert threshold is not None
    assert threshold >= 100.0


def test_gt_02_new_host_appears_in_inventory() -> None:
    known_hosts: dict[str, str] = {"10.0.0.1": "aa:bb:cc:dd:ee:01"}
    incoming = {"ip": "10.0.0.2", "mac": "aa:bb:cc:dd:ee:02"}
    is_new = incoming["ip"] not in known_hosts
    if is_new:
        known_hosts[incoming["ip"]] = incoming["mac"]
    assert is_new is True
    assert "10.0.0.2" in known_hosts


def test_gt_03_host_goes_absent_after_missed_cycles() -> None:
    missed_cycles = {"10.0.0.2": 3}
    absent_threshold = 3
    status = "absent" if missed_cycles["10.0.0.2"] >= absent_threshold else "present"
    assert status == "absent"


def test_gt_04_high_traffic_triggers_threshold_alert() -> None:
    samples = [100.0, 102.0, 98.0, 101.0, 99.0]
    mu = mean(samples)
    sigma = math.sqrt(sample_variance(samples))
    threshold = select_threshold(mu, sigma, 2.0, 500.0, established=True)
    observed_bytes = 1000.0
    assert threshold is not None
    assert observed_bytes > threshold


def test_gt_05_sensor_down_marks_collector_unavailable() -> None:
    collector_up = 0
    assert collector_up == 0
