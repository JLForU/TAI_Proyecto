"""Tasa ARP (U5, BR-U5-19, ST-M3-05): función pura + log al cierre de ventana."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentinel.traffic.arp import arp_rate
from sentinel.traffic.config import TrafficSettings
from sentinel.traffic.source import FixtureSource
from sentinel.traffic.worker import run_window

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 19, 12, 0, 2, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[list] = []

    def post_batch(self, items) -> dict:  # type: ignore[no-untyped-def]
        self.calls.append(list(items))
        return {"accepted": len(items)}


def test_ten_per_second() -> None:
    """ST-M3-05 AC1: arp_rate(100, 10.0) == 10.0."""
    assert arp_rate(100, 10.0) == 10.0
    assert arp_rate(0, 5) == 0.0
    assert arp_rate(2, 5) == 0.4


def test_log_field(caplog: pytest.LogCaptureFixture) -> None:
    """Al cierre de cada ventana se registra event=arp_rate (BR-U5-19)."""
    settings = TrafficSettings(window_seconds=5, interface="eth0", sensor_id="sensor-0")
    source = FixtureSource(FIXTURES / "window_sample.json")  # 2 ARP en la ventana
    client = RecordingClient()
    with caplog.at_level(logging.INFO):
        result = run_window(settings, source, client, FakeClock(NOW))
    assert result.status == "emitted"
    records = [r for r in caplog.records if getattr(r, "event", None) == "arp_rate"]
    assert records, "debe registrar event=arp_rate al cierre"
    record = records[0]
    assert record.arp_messages_per_second == 0.4  # 2 ARP / 5 s
    assert record.interface == "eth0"
    assert record.window_start == "2026-11-19T12:00:00+00:00"
