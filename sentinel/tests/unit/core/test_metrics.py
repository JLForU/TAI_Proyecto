"""Tests del adapter de métricas 9108 (BR-U2-38, P7, IP7, P13)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel.core.api.app import _compose_hooks, create_app
from sentinel.core.config import CoreSettings
from sentinel.core.db.database import Database
from sentinel.core.metrics.collect import (
    ApiRequestCounter,
    CycleCounter,
    ObservationCounters,
    collect,
    render_prometheus,
)
from sentinel.foundation.metrics_contract import METRIC_FAMILIES
from sentinel.foundation.models import ArpObservation, TrafficObservation

from .conftest import sample_batch


def _families(text: str) -> set[str]:
    return {line.split()[2] for line in text.splitlines() if line.startswith("# TYPE ")}


def _scrape(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
        assert resp.status == 200
        return resp.read().decode()


def test_collect_returns_all_families_and_no_extras() -> None:
    samples = collect(api_requests=ApiRequestCounter())
    names = {name for name, _, _ in samples}
    assert names == set(METRIC_FAMILIES)
    api = next(v for n, _l, v in samples if n == "sentinel_api_requests_total")
    hb = next(v for n, _l, v in samples if n == "sentinel_collector_heartbeat_age_seconds")
    assert api == 0.0 and hb == 0.0
    for name, _labels, value in samples:
        if name in {
            "sentinel_api_requests_total",
            "sentinel_collector_heartbeat_age_seconds",
        }:
            continue
        assert value == 0.0, name


def test_api_request_counter_and_render() -> None:
    counter = ApiRequestCounter()
    counter.inc("200")
    counter.inc("200")
    counter.inc("404")
    text = render_prometheus(collect(api_requests=counter, heartbeats={}))
    assert 'sentinel_api_requests_total{component="api",state="200"} 2' in text
    assert 'sentinel_api_requests_total{component="api",state="404"} 1' in text
    assert "# TYPE sentinel_api_requests_total counter" in text
    assert "# TYPE sentinel_alerts_firing gauge" in text
    for family in METRIC_FAMILIES:
        assert family in text


def test_heartbeat_age_from_health() -> None:
    now = datetime.now(UTC)
    recent = (now - timedelta(seconds=30)).isoformat()
    samples = collect(heartbeats={"s0": recent}, now=now.timestamp())
    age = next(v for n, _l, v in samples if n == "sentinel_collector_heartbeat_age_seconds")
    assert 29.0 <= age <= 31.0


def test_scrape_grows_with_requests(tmp_path: Path) -> None:
    """P13: scrape ⇒ familias U1 sin extra; crece tras N requests."""
    settings = CoreSettings(
        db_path=str(tmp_path / "metrics.db"),
        ingest_token="t",
        page_limit=100,
        missing_cycles=3,
    )
    app = create_app(settings, metrics_port=0)  # puerto efímero
    with TestClient(app, raise_server_exceptions=False) as client:
        port = app.state.metrics_server.port
        for _ in range(5):
            assert client.get("/api/v1/health").status_code == 200
        r = client.post(
            "/api/v1/ingest", json=sample_batch(1), headers={"Authorization": "Bearer t"}
        )
        assert r.status_code == 202

        text = _scrape(port)
        families = _families(text)
        assert families == set(METRIC_FAMILIES)
        total = sum(
            float(line.rsplit(" ", 1)[1])
            for line in text.splitlines()
            if line.startswith("sentinel_api_requests_total{")
        )
        assert total >= 6  # 5 health + 1 ingest

        assert client.get("/api/v1/does-not-exist").status_code == 404
        text2 = _scrape(port)
        assert 'sentinel_api_requests_total{component="api",state="404"}' in text2


def test_metrics_404_on_unknown_path(tmp_path: Path) -> None:
    settings = CoreSettings(db_path=str(tmp_path / "m2.db"), ingest_token="t")
    app = create_app(settings, metrics_port=0)
    with TestClient(app, raise_server_exceptions=False):
        port = app.state.metrics_server.port
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
        assert exc.value.code == 404


def test_metrics_disabled_when_port_is_none(tmp_path: Path) -> None:
    settings = CoreSettings(db_path=str(tmp_path / "m3.db"), ingest_token="t")
    app = create_app(settings, metrics_port=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert app.state.metrics_server is None
        assert client.get("/api/v1/health").status_code == 200


def _traffic_observation(*, flows: int = 3) -> TrafficObservation:
    now = datetime.now(UTC)
    return TrafficObservation(
        observed_at=now,
        window_start=now - timedelta(seconds=10),
        window_end=now,
        interface="eth0",
        protocol="tcp",
        packet_length_bytes=100,
        bytes_per_second=10.0,
        packets=10,
        flows=flows,
    )


def _arp_observation() -> ArpObservation:
    return ArpObservation(
        observed_at=datetime.now(UTC),
        interface="eth0",
        opcode=1,
        psrc="10.0.0.1",
        pdst="10.0.0.2",
        hwsrc="aa:bb:cc:dd:ee:ff",
        hwdst="00:00:00:00:00:00",
    )


def test_observation_counters_accumulate_accepted() -> None:
    counters = ObservationCounters()
    counters.on_accepted([_traffic_observation(flows=3), _arp_observation()])
    counters.on_accepted([_traffic_observation(flows=2)])
    assert counters.snapshot() == {"flows_total": 5, "arp_messages_total": 1}


def test_collect_emits_traffic_counters_with_traffic_component() -> None:
    counters = ObservationCounters()
    counters.on_accepted([_traffic_observation(flows=4), _arp_observation()])
    samples = collect(obs_counters=counters)
    flows = next(s for s in samples if s[0] == "sentinel_flows_total")
    arp = next(s for s in samples if s[0] == "sentinel_arp_messages_total")
    assert flows[1] == {"component": "traffic"} and flows[2] == 4.0
    assert arp[1] == {"component": "traffic"} and arp[2] == 1.0


def test_cycle_counter_failed_total() -> None:
    cycles = CycleCounter()
    cycles.record("ok")
    cycles.record("failed")
    cycles.record("timeout")
    samples = collect(cycles=cycles)
    failed = next(s for s in samples if s[0] == "sentinel_discovery_cycles_failed_total")
    assert failed[2] == 2.0


def test_collect_sqlite_gauges_and_latest_traffic(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "gauges.db"))
    db.startup_checks()
    now = datetime.now(UTC).isoformat()
    payload = json.dumps(
        {"source": "traffic", "interface": "eth0", "protocol": "tcp", "bytes_per_second": 1234.5}
    )
    with db.write() as conn:
        conn.execute(
            "INSERT INTO assets (asset_id, status, first_seen, last_seen, source)"
            " VALUES ('a1', 'active', ?, ?, 'discovery')",
            (now, now),
        )
        conn.execute(
            "INSERT INTO events (event_id, type, occurred_at, details, created_at)"
            " VALUES ('e1', 'asset_first_seen', ?, '{}', ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO alerts (alert_id, condition_id, rule, state, fired_at, updated_at)"
            " VALUES ('al1', 'c1', 'R-01', 'firing', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO observations (dedup_key, source, kind, observed_at, received_at, payload)"
            " VALUES ('o1', 'traffic', 'traffic', ?, ?, ?)",
            (now, now, payload),
        )
    samples = collect(db=db)
    values = {name: value for name, _labels, value in samples}
    assert values["sentinel_assets_total"] == 1.0
    assert values["sentinel_asset_changes_total"] == 1.0
    assert values["sentinel_alerts_firing"] == 1.0
    bps = next(s for s in samples if s[0] == "sentinel_bytes_per_second")
    assert bps[1] == {"interface": "eth0", "protocol": "tcp"}
    assert bps[2] == 1234.5


def test_render_escapes_label_values() -> None:
    text = render_prometheus([("sentinel_flows_total", {"component": 'a"b\\c'}, 1.0)])
    assert 'component="a\\"b\\\\c"' in text


def test_render_rejects_label_outside_allowlist() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        render_prometheus([("sentinel_flows_total", {"hostname": "x"}, 1.0)])


def test_compose_hooks_isolates_failures() -> None:
    calls: list[str] = []

    def bad(_observations: object) -> None:
        calls.append("bad")
        raise RuntimeError("boom")

    def good(_observations: object) -> None:
        calls.append("good")

    _compose_hooks(bad, good)([])
    assert calls == ["bad", "good"]
