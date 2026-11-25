"""Tests de las vistas /ui (ST-M10-01..05, USAB-02, BR-U3-17/31, SEC-01)."""

from __future__ import annotations

import httpx

from .conftest import (
    alert,
    asset_detail,
    asset_summary,
    event,
    health,
    observation,
    ok,
    page,
)


def _dispatch(
    *,
    assets=None,  # noqa: ANN001
    details=None,  # noqa: ANN001
    events=None,  # noqa: ANN001
    alerts=None,  # noqa: ANN001
    health_payload=None,  # noqa: ANN001
    discovery=None,  # noqa: ANN001
    down: bool = False,
):
    assets = assets if assets is not None else []
    details = details if details is not None else {}
    events = events if events is not None else []
    alerts = alerts if alerts is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        if down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        method = request.method
        if method == "GET" and path == "/api/v1/assets":
            return ok(page(assets))
        if method == "GET" and path.startswith("/api/v1/assets/"):
            asset_id = path.rsplit("/", 1)[-1]
            detail = details.get(asset_id)
            if detail is None:
                return ok({"detail": "not found", "code": "not_found"}, status=404)
            return ok(detail)
        if method == "GET" and path == "/api/v1/events":
            return ok(page(events))
        if method == "GET" and path == "/api/v1/alerts":
            return ok(page(alerts))
        if method == "GET" and path == "/api/v1/health":
            return ok(health_payload if health_payload is not None else health())
        if method == "POST" and path == "/api/v1/discovery":
            if discovery is None:
                return ok(
                    {
                        "run_id": "r-1",
                        "status": "running",
                        "started_at": "2026-01-01T00:00:00+00:00",
                    }
                )
            if isinstance(discovery, httpx.Response):
                return discovery
            return ok(discovery)
        if method == "GET" and path.startswith("/api/v1/discovery/"):
            return ok(
                {
                    "run_id": "r-1",
                    "status": "completed",
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:01:00+00:00",
                    "hosts_seen": 3,
                    "error": None,
                }
            )
        return ok({"detail": f"unexpected {method} {path}"}, status=500)

    return handler


# --------------------------------------------------------------------------- #
# ST-M10-01 — inventario
# --------------------------------------------------------------------------- #


def test_assets_view_renders_rows_and_pagination(make_gui) -> None:
    tc = make_gui(
        _dispatch(
            assets=[asset_summary("a-1"), asset_summary("a-2", hostname="host2")],
            details={
                "a-1": asset_detail(asset_summary("a-1")),
                "a-2": asset_detail(asset_summary("a-2", hostname="host2")),
            },
        )
    )
    r = tc.get("/ui/assets")
    assert r.status_code == 200
    assert 'id="assets-table"' in r.text
    assert "host1" in r.text and "host2" in r.text
    assert "/ui/assets/a-1" in r.text
    assert "Página 1 / 1 · 2 activos" in r.text
    assert "presente" in r.text


def test_assets_view_empty_state(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.get("/ui/assets")
    assert r.status_code == 200
    assert "Sin activos en el inventario" in r.text
    assert "dispara discovery" in r.text or "Aún no se ha observado" in r.text


def test_assets_view_invalid_status_is_400(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.get("/ui/assets", params={"status": "bogus"})
    assert r.status_code == 400
    assert "Solicitud inválida" in r.text


def test_assets_view_api_down_502_html(make_gui) -> None:
    tc = make_gui(_dispatch(down=True))
    r = tc.get("/ui/assets")
    assert r.status_code == 502
    assert "Core API no disponible" in r.text
    assert "Traceback" not in r.text


# --------------------------------------------------------------------------- #
# ST-M10-02 — detalle
# --------------------------------------------------------------------------- #


def test_asset_detail_four_sections_and_sin_datos(make_gui) -> None:
    detail = asset_detail(
        recent_observations=[
            observation(kind="arp", payload={"psrc": "10.0.0.1", "hwsrc": "aa:bb:cc:dd:ee:ff"}),
            observation(
                source="traffic",
                kind="flow",
                payload={
                    "bytes_per_second": 12.5,
                    "pairs": [
                        {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "bytes_per_second": 12.5}
                    ],
                    "window_start": "2026-01-01T00:00:00+00:00",
                    "window_end": "2026-01-01T01:00:00+00:00",
                },
            ),
        ],
        recent_events=[event()],
    )
    tc = make_gui(_dispatch(assets=[asset_summary("a-1")], details={"a-1": detail}))
    r = tc.get("/ui/assets/a-1")
    assert r.status_code == 200
    for heading in ("Observaciones", "Eventos", "Tráfico", "ARP"):
        assert heading in r.text
    assert "12.5" in r.text
    assert "port_service_changed" in r.text
    assert "aa:bb:cc:dd:ee:ff" in r.text


def test_asset_detail_without_traffic_shows_sin_datos(make_gui) -> None:
    tc = make_gui(_dispatch(assets=[asset_summary("a-1")], details={"a-1": asset_detail()}))
    r = tc.get("/ui/assets/a-1")
    assert r.status_code == 200
    # Sin observaciones de tráfico ⇒ "sin datos", nunca 0 inventado (BR-U3-07)
    assert "sin datos" in r.text


def test_asset_detail_404_page(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.get("/ui/assets/ghost")
    assert r.status_code == 404
    assert "No encontrado" in r.text


def test_asset_detail_escapes_html_payload(make_gui) -> None:
    detail = asset_detail(hostname="<script>alert(1)</script>")
    tc = make_gui(
        _dispatch(
            assets=[asset_summary("a-1", hostname="<script>alert(1)</script>")],
            details={"a-1": detail},
        )
    )
    r = tc.get("/ui/assets/a-1")
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


# --------------------------------------------------------------------------- #
# ST-M10-03 — timeline + alertas
# --------------------------------------------------------------------------- #


def test_events_view_merges_sorted_with_badges(make_gui) -> None:
    events = [
        event("e-old", occurred_at="2026-01-01T08:00:00+00:00", severity="info"),
        event(
            "e-new",
            type_="asset_missing",
            occurred_at="2026-01-01T12:00:00+00:00",
            severity="critical",
        ),
    ]
    alerts = [alert("al-1", fired_at="2026-01-01T10:00:00+00:00")]
    tc = make_gui(_dispatch(events=events, alerts=alerts))
    r = tc.get("/ui/events")
    assert r.status_code == 200
    assert 'id="timeline"' in r.text
    # orden DESC: 12:00 (evento) antes que 10:00 (alerta) antes que 08:00
    positions = [
        r.text.index(x)
        for x in ("2026-01-01T12:00:00", "2026-01-01T10:00:00", "2026-01-01T08:00:00")
    ]
    assert positions == sorted(positions)
    assert "asset_missing" in r.text and "port_open" in r.text
    assert "badge-severity-critical" in r.text
    assert "badge-state-firing" in r.text
    assert "/api/v1/export?format=csv" in r.text


def test_events_view_filters_and_invalid_date_400(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.get("/ui/events", params={"from": "31/12/2026", "to": "2026-01-02"})
    assert r.status_code == 400
    assert "Solicitud inválida" in r.text
    r_ok = tc.get(
        "/ui/events", params={"from": "2026-01-01", "to": "2026-01-02", "severity": "critical"}
    )
    assert r_ok.status_code == 200


def test_events_view_empty_state(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.get("/ui/events")
    assert r.status_code == 200
    assert "Sin eventos ni alertas" in r.text


def test_alerts_view_shows_only_alerts(make_gui) -> None:
    tc = make_gui(
        _dispatch(
            alerts=[
                alert("al-1"),
                alert("al-2", state="resolved", resolved_at="2026-01-01T11:00:00+00:00"),
            ]
        )
    )
    r = tc.get("/ui/alerts")
    assert r.status_code == 200
    assert 'id="alerts-table"' in r.text
    assert "badge-state-firing" in r.text and "badge-state-resolved" in r.text
    assert "port_open" in r.text


# --------------------------------------------------------------------------- #
# ST-M10-05 — salud
# --------------------------------------------------------------------------- #


def test_health_view_badges_and_sensor_down(make_gui) -> None:
    from datetime import UTC, datetime, timedelta

    stale = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
    fresh = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    payload = health(
        heartbeats={"sensor-a": stale, "sensor-b": fresh},
        counts={"assets": 0, "events": 3, "alerts": 0},
    )
    tc = make_gui(_dispatch(health_payload=payload))
    r = tc.get("/ui/health")
    assert r.status_code == 200
    assert 'id="health-status"' in r.text and "up" in r.text
    assert "sensor caído" in r.text
    # Vacío de activos no se pinta como "red sin activos" (USAB-02)
    assert "¿ha corrido el discovery?" in r.text


# --------------------------------------------------------------------------- #
# ST-M10-04 — discovery
# --------------------------------------------------------------------------- #


def test_discovery_post_returns_202_with_status(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.post("/ui/discovery", data={"host": "192.168.1.10"})
    assert r.status_code == 200
    assert 'id="discovery-status"' in r.text
    assert 'data-status="running"' in r.text
    assert "r-1" in r.text


def test_discovery_post_hx_fragment(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.post("/ui/discovery", data={"host": "192.168.1.10"}, headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert 'id="discovery-status"' in r.text
    assert "<nav" not in r.text  # fragmento, sin layout completo


def test_discovery_post_409_inline_message(make_gui) -> None:
    conflict = httpx.Response(409, json={"detail": "discovery already running", "code": "conflict"})
    tc = make_gui(_dispatch(discovery=conflict))
    r = tc.post("/ui/discovery", data={"host": "192.168.1.10"})
    assert r.status_code == 200
    assert "ciclo ya en curso" in r.text
    assert 'id="discovery-message"' in r.text


def test_discovery_post_503_inline_message(make_gui) -> None:
    unavailable = httpx.Response(503, json={"detail": "discovery runner not available"})
    tc = make_gui(_dispatch(discovery=unavailable))
    r = tc.post("/ui/discovery", data={"host": "192.168.1.10"})
    assert r.status_code == 200
    assert "descubrimiento no disponible (U4 pendiente)" in r.text


def test_discovery_post_invalid_host_400(make_gui) -> None:
    tc = make_gui(_dispatch())
    r = tc.post("/ui/discovery", data={"host": "../../etc/passwd"})
    assert r.status_code == 400
    assert "Solicitud inválida" in r.text


def test_discovery_post_scope_violation_shows_message(make_gui) -> None:
    scoped = httpx.Response(400, json={"detail": "out of scope", "code": "scope_violation"})
    tc = make_gui(_dispatch(discovery=scoped))
    r = tc.post("/ui/discovery", data={"host": "8.8.8.8"})
    assert r.status_code == 200
    assert "host fuera de alcance" in r.text
