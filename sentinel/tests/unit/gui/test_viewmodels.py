"""Tests de ``gui.viewmodels`` (FD §2/§4 de domain-entities)."""

from __future__ import annotations

from sentinel.core.api.schemas import (
    AlertOut,
    AssetDetail,
    AssetSummary,
    EventOut,
    HealthStatus,
    ObservationOut,
)
from sentinel.gui.viewmodels import (
    AssetDetailVM,
    AssetRowVM,
    DiscoveryRunVM,
    ErrorVM,
    HealthVM,
    PageVM,
    TimelineEntryVM,
)


def _obs(
    source: str, *, payload: dict | None = None, at: str = "2026-11-11T10:00:00+00:00"
) -> ObservationOut:
    return ObservationOut(
        dedup_key=f"k-{source}-{at}",
        source=source,
        kind="sample",
        observed_at=at,
        payload=payload or {},
    )


def _detail(**overrides: object) -> AssetDetail:
    base: dict = {
        "asset_id": "a-1",
        "ips": ["10.0.0.10"],
        "mac": "AA:BB:CC:DD:EE:01",
        "hostname": "ws-01",
        "status": "present",
        "first_seen": "2026-11-01T00:00:00+00:00",
        "last_seen": "2026-11-11T10:00:00+00:00",
        "os_name": "Linux",
        "os_provenance": "observed",
        "recent_observations": [],
        "recent_events": [],
    }
    base.update(overrides)
    return AssetDetail(**base)


class TestAssetRowVM:
    def test_from_detail_labels_and_sources(self) -> None:
        detail = _detail(
            recent_observations=[
                _obs("discovery"),
                _obs("traffic"),
                _obs("discovery", at="2026-11-11T10:00:01+00:00"),
            ]
        )
        row = AssetRowVM.from_detail(detail)
        assert row.os_label == "Linux"
        assert row.provenance_label == "observado"
        assert row.status_label == "presente"
        assert row.sources == ["discovery", "traffic"]

    def test_unknown_os(self) -> None:
        row = AssetRowVM.from_detail(_detail(os_name=None, os_provenance="unknown"))
        assert row.os_label == "desconocido"
        assert row.provenance_label == "desconocido"

    def test_from_summary_without_detail(self) -> None:
        summary = AssetSummary(
            asset_id="a-2",
            ips=["10.0.0.11"],
            status="absent",
            first_seen="2026-11-01T00:00:00+00:00",
            last_seen="2026-11-02T00:00:00+00:00",
        )
        row = AssetRowVM.from_summary_with_detail(summary, None)
        assert row.asset_id == "a-2"
        assert row.os_label == "desconocido"
        assert row.status_label == "ausente"


class TestPageVM:
    def test_pages_and_offset(self) -> None:
        page = PageVM.build(list(range(100)), page=2, total=150, limit=100)
        assert (page.pages, page.offset, page.has_prev, page.has_next) == (2, 100, True, False)
        first = PageVM.build(list(range(50)), page=1, total=150, limit=100)
        assert (first.has_prev, first.has_next) == (False, True)

    def test_empty_is_one_page(self) -> None:
        page: PageVM = PageVM.build([], page=1, total=0, limit=100)
        assert page.pages == 1
        assert not page.has_prev and not page.has_next


class TestAssetDetailVM:
    def test_sections_empty_traffic(self) -> None:
        vm = AssetDetailVM.from_detail(_detail(recent_observations=[_obs("discovery")]))
        assert vm.traffic.available is False
        assert vm.arp == []
        assert vm.summary.sources == ["discovery"]

    def test_traffic_aggregate(self) -> None:
        obs = [
            _obs(
                "traffic",
                payload={
                    "bytes_per_second": 204.8,
                    "window_start": "2026-11-11T10:00:00+00:00",
                    "window_end": "2026-11-11T10:00:05+00:00",
                    "pairs": [{"src_ip": "10.0.0.10", "dst_ip": "10.0.0.20"}],
                },
            ),
            _obs(
                "traffic",
                payload={
                    "bytes_per_second": 512.0,
                    "pairs": [
                        {"src_ip": "10.0.0.10", "dst_ip": "10.0.0.20"},
                        {"src_ip": "10.0.0.10", "dst_ip": "10.0.0.30"},
                    ],
                },
            ),
        ]
        vm = AssetDetailVM.from_detail(_detail(recent_observations=obs))
        assert vm.traffic.available is True
        assert vm.traffic.bytes_per_second_max == 512.0
        assert [p.pair for p in vm.traffic.pairs] == [
            "10.0.0.10 → 10.0.0.20",
            "10.0.0.10 → 10.0.0.30",
        ]
        assert vm.traffic.window.startswith("2026-11-11T10:00:00")

    def test_arp_mappings(self) -> None:
        obs = [_obs("arp", payload={"psrc": "10.0.0.10", "hwsrc": "aa:bb:cc:dd:ee:01"})]
        vm = AssetDetailVM.from_detail(_detail(recent_observations=obs))
        assert len(vm.arp) == 1
        assert vm.arp[0].ip == "10.0.0.10"
        assert vm.arp[0].mac == "aa:bb:cc:dd:ee:01"


class TestTimelineEntryVM:
    def test_from_event(self) -> None:
        event = EventOut(
            event_id="e-1",
            type="asset_first_seen",
            asset_id="a-1",
            severity="info",
            occurred_at="2026-11-11T10:00:00+00:00",
            details={"ip": "10.0.0.10"},
        )
        entry = TimelineEntryVM.from_event(event)
        assert entry.kind == "event"
        assert entry.title == "asset_first_seen"
        assert entry.severity_or_state == "info"
        assert "ip=10.0.0.10" in entry.detail

    def test_from_alert(self) -> None:
        alert = AlertOut(
            alert_id="al-1",
            condition_id="c-1",
            rule="R-01",
            metric_key="bytes_per_second:eth0:tcp",
            state="firing",
            measured_value=10.0,
            threshold=5.0,
            fired_at="2026-11-11T10:00:00+00:00",
        )
        entry = TimelineEntryVM.from_alert(alert)
        assert entry.kind == "alert"
        assert entry.severity_or_state == "firing"
        assert entry.resolved_at is None
        assert "threshold=5.0" in entry.detail


class TestHealthVM:
    def test_sensors_down_threshold(self) -> None:
        health = HealthStatus(
            status="up",
            uptime_seconds=10.0,
            db_connected=True,
            sensor_heartbeats={
                "s-old": "2026-11-11T10:00:00+00:00",
                "s-new": "2026-11-11T12:00:00+00:00",
            },
            counts={"assets": 3},
            last_discovery_run={"run_id": "r-1", "finished_at": "2026-11-11T11:00:00+00:00"},
        )
        from datetime import datetime

        now = datetime.fromisoformat("2026-11-11T12:01:00+00:00").timestamp()
        vm = HealthVM.from_status(health, now_epoch=now, stale_after=300.0)
        by_id = {s.sensor_id: s for s in vm.sensors}
        assert by_id["s-old"].down is True
        assert by_id["s-new"].down is False
        assert vm.last_cycle_at == "2026-11-11T11:00:00+00:00"
        assert vm.counts == {"assets": 3}


class TestDiscoveryRunVM:
    def test_poll_state(self) -> None:
        running = DiscoveryRunVM("r-1", "running", "t0", None, None, None)
        done = DiscoveryRunVM("r-2", "completed", "t0", "t1", 1, None)
        assert running.poll_state == "active"
        assert done.poll_state == "stopped"


class TestErrorVM:
    def test_fields(self) -> None:
        vm = ErrorVM(
            status=502, title="Core API no disponible", detail="x", code="core_unavailable"
        )
        assert (vm.status, vm.code) == (502, "core_unavailable")
