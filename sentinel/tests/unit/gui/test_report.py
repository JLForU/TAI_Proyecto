"""Tests del reporte: builders, esc(), fail-fast y determinismo (ST-M10-06)."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from sentinel.core.api.schemas import AlertOut, AssetSummary, EventOut
from sentinel.gui.client import GuiClient
from sentinel.gui.errors import CoreUnavailableError
from sentinel.gui.report.sections import (
    SECTION_ORDER,
    ReportRequest,
    build_alerts_section,
    build_changes_section,
    build_evidence_range_section,
    build_inventory_section,
    build_top_talkers_section,
    esc,
    render_markdown,
)
from sentinel.gui.report.service import ReportService

from .conftest import alert, asset_summary, event, ok, page

FIXED_NOW = "2026-01-02T00:00:00Z"
RANGE = ReportRequest(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2))


def _md(sections: list) -> str:
    return render_markdown(RANGE, sections, FIXED_NOW).decode("utf-8")


def _all_sections(**kw: Any) -> list:
    assets = kw.get("assets", [])
    events = kw.get("events", [])
    talkers = kw.get("talkers", [])
    alerts = kw.get("alerts", [])
    counts = kw.get(
        "counts",
        {
            "assets": len(assets),
            "events": len(events),
            "alerts": len(alerts),
            "talker_details": len(assets),
        },
    )
    return [
        build_inventory_section(assets),
        build_changes_section(events),
        build_top_talkers_section(talkers),
        build_alerts_section(alerts),
        build_evidence_range_section(RANGE, counts),
    ]


# --------------------------------------------------------------------------- #
# esc() + estructura (P5, BR-U3-20/21)
# --------------------------------------------------------------------------- #


def test_esc_escapes_html_and_markdown() -> None:
    out = esc("<script>alert(1)</script> *bold* _u_ #h `c` [a](b)")
    assert "&lt;script&gt;" in out and "&lt;/script&gt;" in out
    assert "<script>" not in out
    assert "\\*bold\\*" in out and "\\_u\\_" in out
    assert "\\#h" in out and "\\`c\\`" in out
    assert "\\[a\\]" in out and "\\] (b)".replace(" (b)", "") in out or "\\[a\\](b)" in out


def test_render_markdown_five_sections_fixed_order() -> None:
    md = _md(_all_sections())
    heads = [line for line in md.splitlines() if line.startswith("## ")]
    assert len(heads) == 5
    assert heads == [
        "## Inventory summary",
        "## Changes",
        "## Top talkers",
        "## Alerts",
        "## Evidence range",
    ]
    assert SECTION_ORDER == ("inventory", "changes", "top_talkers", "alerts", "evidence_range")
    # Generated at FUERA de las secciones (BR-U3-21): antes del primer ##
    gen = md.index("Generated at:")
    assert gen < md.index("## Inventory summary")


def test_render_markdown_rejects_incomplete_sections() -> None:
    with pytest.raises(ValueError, match="5 sections"):
        render_markdown(RANGE, _all_sections()[:3], FIXED_NOW)


def test_inventory_section_escapes_hostname() -> None:
    summary = asset_summary("a-1", hostname="<script>x</script>")
    section = build_inventory_section([AssetSummary.model_validate(summary)])
    body = section.to_markdown()
    assert "&lt;script&gt;" in body
    assert "<script>" not in body
    assert "Total: 1" in body


def test_changes_section_filters_event_types() -> None:
    events = [
        EventOut.model_validate(event("e1", type_="asset_first_seen")),
        EventOut.model_validate(event("e2", type_="port_service_changed")),
        EventOut.model_validate(event("e3", type_="condition_firing")),
        EventOut.model_validate(event("e4", type_="sensor_heartbeat")),
    ]
    section = build_changes_section(events)
    # esc() escapa "_" (MD-significativo): asset_first_seen ⇒ asset\_first\_seen
    assert "asset\\_first\\_seen" in section.body
    assert "port\\_service\\_changed" in section.body
    assert "condition\\_firing" not in section.body
    assert "sensor\\_heartbeat" not in section.body


def test_top_talkers_empty_shows_sin_datos() -> None:
    section = build_top_talkers_section([])
    assert "sin datos" in section.body


def test_top_talkers_ranks_desc() -> None:
    section = build_top_talkers_section(
        [("a", "10.0.0.1→10.0.0.2", 5.0), ("b", "10.0.0.3→10.0.0.4", 50.0)]
    )
    lines = [ln for ln in section.body.splitlines() if ln.startswith("|") and "---" not in ln]
    assert "10.0.0.3" in lines[1]  # primera fila = mayor bytes/s


def test_alerts_and_evidence_sections() -> None:
    alerts = [AlertOut.model_validate(alert("al-1"))]
    alerts_md = build_alerts_section(alerts).to_markdown()
    assert "firing" in alerts_md and "port\\_open" in alerts_md
    empty = build_alerts_section([]).to_markdown()
    assert "Sin alertas" in empty
    evidence = build_evidence_range_section(
        RANGE, {"assets": 3, "events": 7, "alerts": 1, "talker_details": 3}
    ).to_markdown()
    assert "2026-01-01 a 2026-01-02" in evidence
    assert "assets: 3" in evidence and "events: 7" in evidence


# --------------------------------------------------------------------------- #
# ReportService: fetch + fail-fast + determinismo (P2)
# --------------------------------------------------------------------------- #


def _report_handler(fail_on: str | None = None, *, hostname: str = "host1"):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if fail_on is not None and fail_on in path:
            raise httpx.ConnectError("boom", request=request)
        if path == "/api/v1/assets" and request.url.params.get("offset") in (None, "0"):
            return ok(page([asset_summary("a-1", hostname=hostname)]))
        if path.startswith("/api/v1/assets/"):
            detail = {
                **asset_summary("a-1", hostname=hostname),
                "os_name": "Linux",
                "os_provenance": "observed",
                "recent_observations": [
                    {
                        "dedup_key": "t:1",
                        "source": "traffic",
                        "kind": "flow",
                        "sensor_id": None,
                        "observed_at": "2026-01-01T00:00:00+00:00",
                        "payload": {
                            "bytes_per_second": 9.0,
                            "pairs": [
                                {
                                    "src_ip": "10.0.0.1",
                                    "dst_ip": "10.0.0.2",
                                    "bytes_per_second": 9.0,
                                }
                            ],
                        },
                    }
                ],
                "recent_events": [],
            }
            return ok(detail)
        if path == "/api/v1/events":
            return ok(page([event("e1", type_="asset_first_seen")]))
        if path == "/api/v1/alerts":
            return ok(page([alert("al-1")]))
        return ok({"detail": f"unexpected {path}"}, status=500)

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def _service(handler) -> ReportService:  # noqa: ANN001
    client = GuiClient(transport=httpx.MockTransport(handler))
    from datetime import UTC, datetime

    return ReportService(client, now=lambda: datetime(2026, 1, 2, tzinfo=UTC))


def test_service_generates_five_sections_md() -> None:
    svc = _service(_report_handler())
    artifact = svc.generate(RANGE, "md")
    assert artifact.format == "md"
    assert artifact.filename == "reporte_2026-01-01_2026-01-02.md"
    assert artifact.content_type.startswith("text/markdown")
    text = artifact.data.decode("utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    assert len(heads) == 5
    assert "Generated at: 2026-01-02T00:00:00Z" in text


def test_service_determinism_same_bytes() -> None:
    handler = _report_handler()
    md1 = _service(handler).generate(RANGE, "md").data
    md2 = _service(handler).generate(RANGE, "md").data
    assert md1 == md2


def test_service_failfast_on_third_call() -> None:
    # Orden: assets → events → detail (3ª) ⇒ falla antes de alerts/secciones
    handler = _report_handler(fail_on="/api/v1/assets/a-1")
    svc = _service(handler)
    with pytest.raises(CoreUnavailableError):
        svc.generate(RANGE, "md")


def test_service_failfast_5xx_api_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return ok({"detail": "boom"}, status=500)
        if request.url.path == "/api/v1/assets":
            return ok(page([asset_summary("a-1")]))
        return ok({"detail": "unexpected"}, status=500)

    svc = _service(handler)
    from sentinel.gui.errors import ApiStatusError

    with pytest.raises(ApiStatusError):
        svc.generate(RANGE, "md")


def test_service_escapes_dynamic_fields() -> None:
    svc = _service(_report_handler(hostname="<script>alert(1)</script>"))
    text = svc.generate(RANGE, "md").data.decode("utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_service_pdf_from_same_md() -> None:
    svc = _service(_report_handler())
    artifact = svc.generate(RANGE, "pdf")
    assert artifact.format == "pdf"
    assert artifact.filename.endswith(".pdf")
    assert artifact.content_type == "application/pdf"
    assert artifact.data.startswith(b"%PDF")


# --------------------------------------------------------------------------- #
# Endpoints /ui/report + /api/v1/report (C7)
# --------------------------------------------------------------------------- #


def _gui_with_report(make_gui, handler):  # noqa: ANN001
    tc = make_gui(handler)
    # reloj congelado para comparar bytes
    from datetime import UTC, datetime

    tc.app.state.report_clock = lambda: datetime(2026, 1, 2, tzinfo=UTC)
    tc.app.state.report_service = None  # se recrea con el reloj
    return tc


def test_report_endpoints_md_and_headers(make_gui) -> None:
    tc = _gui_with_report(make_gui, _report_handler())
    params = {"from": "2026-01-01", "to": "2026-01-02", "format": "md"}
    r1 = tc.get("/ui/report", params=params)
    r2 = tc.get("/api/v1/report", params=params)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers["content-disposition"].startswith("attachment;")
    assert "reporte_2026-01-01_2026-01-02.md" in r1.headers["content-disposition"]
    assert r1.content == r2.content  # mismo servicio (Q8=A)
    assert len([ln for ln in r1.text.splitlines() if ln.startswith("## ")]) == 5


def test_report_missing_range_is_400(make_gui) -> None:
    tc = _gui_with_report(make_gui, _report_handler())
    r = tc.get("/ui/report")
    assert r.status_code == 400
    assert "Solicitud inválida" in r.text
    r2 = tc.get("/ui/report", params={"from": "2026-01-05", "to": "2026-01-01"})
    assert r2.status_code == 400


def test_report_invalid_format_is_400(make_gui) -> None:
    tc = _gui_with_report(make_gui, _report_handler())
    r = tc.get("/ui/report", params={"from": "2026-01-01", "to": "2026-01-02", "format": "exe"})
    assert r.status_code == 400


def test_report_api_down_is_502_without_partial_md(make_gui) -> None:
    tc = _gui_with_report(make_gui, _report_handler(fail_on="/api/v1/events"))
    r = tc.get("/api/v1/report", params={"from": "2026-01-01", "to": "2026-01-02"})
    assert r.status_code == 502
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["code"] == "core_unavailable"
    assert "## " not in r.text  # nunca MD parcial
    r_html = tc.get("/ui/report", params={"from": "2026-01-01", "to": "2026-01-02"})
    assert r_html.status_code == 502
    assert "Core API no disponible" in r_html.text
