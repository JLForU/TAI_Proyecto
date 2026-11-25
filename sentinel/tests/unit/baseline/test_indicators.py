"""Indicadores → U7 (MNT-02, FD §3.5): cardinalidad, labels, valores, flag."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sentinel.baseline.conditions import BaselineState, ConditionService
from sentinel.baseline.indicators import metric_samples
from sentinel.foundation.metrics_contract import FORBIDDEN_LABELS, metric_name

KEY = "bytes_per_second|eth0|tcp"
FIRING = {"c1": {"condition_id": "c1", "metric_key": KEY, "state": "firing"}}
RESOLVED = {"c1": {"condition_id": "c1", "metric_key": KEY, "state": "resolved"}}


def _state(*, established: bool) -> BaselineState:
    return BaselineState(
        metric_key=KEY,
        interval_seconds=5,
        samples=[100.0] * 5,
        mean=100.0,
        variance=0.0,
        established=established,
        t_first=None,
    )


def test_label_cardinality() -> None:
    """MNT-02: cada familia tiene labels acotados y únicos por serie."""
    samples = metric_samples([_state(established=True)], {}, collector_up=1)
    # 4 familias × 1 serie + collector = 4+1 (R-01, status, established, collector)
    assert len(samples) == 4
    # Cardinalidad: labels de serie = {interface, protocol} (+metric, +state)
    for name, labels, _ in samples:
        if name == "sentinel_collector_up":
            assert labels == {"collector": "traffic"}
        else:
            assert {"interface", "protocol"} <= set(labels)


def test_no_forbidden_labels() -> None:
    samples = metric_samples([_state(established=True)], FIRING, collector_up=1)
    for _, labels, _ in samples:
        assert FORBIDDEN_LABELS.intersection(labels) == set()


def test_values_follow_state() -> None:
    firing = metric_samples([_state(established=True)], FIRING, collector_up=1)
    exceeded = [v for n, _, v in firing if n == "sentinel_traffic_threshold_exceeded"]
    assert exceeded == [1.0]

    resolved = metric_samples([_state(established=True)], RESOLVED, collector_up=1)
    exceeded = [v for n, _, v in resolved if n == "sentinel_traffic_threshold_exceeded"]
    assert exceeded == [0.0]

    establishing = metric_samples([_state(established=False)], {}, collector_up=1)
    status = [v for n, _, v in establishing if n == "sentinel_baseline_status"]
    assert status == [1.0]
    est = [v for n, labels, v in establishing if n == "sentinel_baseline_established"]
    assert est == [0.0]
    # Sin alerta firing ⇒ R-01 en 0 incluso sin serie firing
    exceeded = [v for n, _, v in establishing if n == "sentinel_traffic_threshold_exceeded"]
    assert exceeded == [0.0]


def test_collector_flag() -> None:
    up = metric_samples([], {}, collector_up=1)
    down = metric_samples([], {}, collector_up=0)
    assert [v for n, _, v in up if n == "sentinel_collector_up"] == [1.0]
    assert [v for n, _, v in down if n == "sentinel_collector_up"] == [0.0]


def test_metric_name_valid_for_families() -> None:
    """Las 3 familias nuevas pasan por metric_name() (BR-20)."""
    for bare in (
        "traffic_threshold_exceeded",
        "baseline_status",
        "collector_up",
        "baseline_established",
    ):
        full = metric_name(bare)
        assert full.startswith("sentinel_")


def test_service_metric_samples_uses_heartbeat() -> None:
    """metric_samples() del servicio deriva collector_up de su heartbeat."""
    from sentinel.baseline.config import BaselineSettings

    svc = ConditionService(
        baselines=_NoStore(),
        alerts=_NoStore(),
        settings=BaselineSettings(),
        clock=_FixedClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    samples = svc.metric_samples()
    assert [v for n, _, v in samples if n == "sentinel_collector_up"] == [0.0]
    # Tráfico visto hace 10s ⇒ up
    svc._last_traffic_seen = datetime(2026, 1, 1, tzinfo=UTC) - timedelta(seconds=10)
    samples = svc.metric_samples()
    assert [v for n, _, v in samples if n == "sentinel_collector_up"] == [1.0]


class _NoStore:
    def list(self) -> list[dict]:
        return []

    def upsert(self, row: dict) -> None:  # noqa: D102
        return None

    def list_firing(self) -> list[dict]:
        return []


class _FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now
