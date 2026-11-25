"""ReportService — generación fail-fast del reporte de red (P2, FR-GUI-06).

Fetch secuencial contra la API U2 por loopback (nunca SQLite): inventario →
cambios → top talkers → alertas → evidencia. Cualquier fallo ⇒ excepción
hacia el handler (502), **nunca** un MD parcial (BR-U3-21/AVAIL-01). La MD
se construye en memoria y solo se emite con las 5 secciones completas.
El ``GuiClient`` inyectado debe usar timeout 30 s (P2).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..client import GuiClient
from ..errors import ApiStatusError, CoreUnavailableError
from ..viewmodels import AssetDetailVM, TrafficSummaryVM
from .sections import (
    SECTION_ORDER,
    ReportArtifact,
    ReportFormat,
    ReportRequest,
    build_alerts_section,
    build_changes_section,
    build_evidence_range_section,
    build_inventory_section,
    build_top_talkers_section,
    render_markdown,
)

__all__ = ["ReportService"]

_PDF_CONTENT_TYPE = "application/pdf"
_MD_CONTENT_TYPE = "text/markdown; charset=utf-8"
#: Fetch page size para el paginado del reporte (U2 permite hasta 1000).
_REPORT_PAGE_LIMIT = 1000


class ReportService:
    """Genera ``ReportArtifact`` md/pdf para un rango (ST-M10-06, C7)."""

    def __init__(
        self,
        client: GuiClient,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._now = now or (lambda: datetime.now(UTC))

    # -- fetch (fail-fast: cualquier error se propaga) ----------------------
    def _fetch_all(self, fetch_page: Callable[[int], Any]) -> list:
        items: list = []
        offset = 0
        while True:
            page = fetch_page(offset)
            items.extend(page.items)
            offset += len(page.items)
            if offset >= page.total or not page.items:
                return items

    def _fetch_inventory(self) -> list:
        return self._fetch_all(
            lambda offset: self._client.get_assets(limit=_REPORT_PAGE_LIMIT, offset=offset)
        )

    def _fetch_events(self, request: ReportRequest) -> list:
        date_from = request.date_from.isoformat()
        date_to = request.date_to.isoformat()
        return self._fetch_all(
            lambda offset: self._client.get_events(
                date_from=date_from,
                date_to=date_to,
                limit=_REPORT_PAGE_LIMIT,
                offset=offset,
            )
        )

    def _fetch_alerts(self, request: ReportRequest) -> list:
        date_from = request.date_from.isoformat()
        date_to = request.date_to.isoformat()
        return self._fetch_all(
            lambda offset: self._client.get_alerts(
                date_from=date_from,
                date_to=date_to,
                limit=_REPORT_PAGE_LIMIT,
                offset=offset,
            )
        )

    def _fetch_talkers(self, assets: list) -> list[tuple[str, str, float]]:
        talkers: list[tuple[str, str, float]] = []
        for asset in assets:
            detail = self._client.get_asset(asset.asset_id)
            vm = AssetDetailVM.from_detail(detail)
            traffic: TrafficSummaryVM = vm.traffic
            if not traffic.available:
                continue
            for pair in traffic.pairs:
                if pair.bytes_per_second is not None:
                    talkers.append((asset.asset_id, pair.pair, pair.bytes_per_second))
        return talkers

    # -- orquestación -------------------------------------------------------
    def generate(self, request: ReportRequest, fmt: ReportFormat) -> ReportArtifact:
        """Construye el artefacto completo o lanza (nunca MD parcial)."""
        try:
            inventory = self._fetch_inventory()
            events = self._fetch_events(request)
            talkers = self._fetch_talkers(inventory)
            alerts = self._fetch_alerts(request)
            source_counts = {
                "assets": len(inventory),
                "events": len(events),
                "alerts": len(alerts),
                "talker_details": len(inventory),
            }
            sections = [
                build_inventory_section(inventory),
                build_changes_section(events),
                build_top_talkers_section(talkers),
                build_alerts_section(alerts),
                build_evidence_range_section(request, source_counts),
            ]
            generated_at = self._now().strftime("%Y-%m-%dT%H:%M:%SZ")
            markdown = render_markdown(request, sections, generated_at)
        except (ApiStatusError, CoreUnavailableError):
            raise
        except Exception as exc:  # noqa: BLE001 — P2: cualquier fallo ⇒ 502
            raise CoreUnavailableError(f"report generation failed: {exc}") from exc

        if fmt == "pdf":
            from .pdf import render_pdf

            data = render_pdf(markdown)
            return ReportArtifact(
                format="pdf",
                filename=f"{request.filename}.pdf",
                content_type=_PDF_CONTENT_TYPE,
                data=data,
            )
        return ReportArtifact(
            format="md",
            filename=f"{request.filename}.md",
            content_type=_MD_CONTENT_TYPE,
            data=markdown,
        )

    @property
    def section_order(self) -> tuple[str, ...]:
        return SECTION_ORDER
