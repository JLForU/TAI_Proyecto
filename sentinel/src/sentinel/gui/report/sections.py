"""Builders de las 5 secciones del reporte + escape de datos dinámicos (P5).

Toda función es pura: entra data, sale Markdown. Ningún I/O. El orden de
secciones es fijo (BR-U3-20, `SECTION_ORDER`) y `esc()` se aplica a todo
campo dinámico insertado en el Markdown (NFR-U3-SEC-01).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sentinel.core.api.schemas import AlertOut, AssetSummary, EventOut

__all__ = [
    "CHANGES_EVENT_TYPES",
    "SECTION_ORDER",
    "ReportArtifact",
    "ReportFormat",
    "ReportRequest",
    "ReportSection",
    "build_alerts_section",
    "build_changes_section",
    "build_evidence_range_section",
    "build_inventory_section",
    "build_top_talkers_section",
    "esc",
    "render_markdown",
]

ReportFormat = Literal["md", "pdf"]

#: Orden fijo de las secciones `## ` (BR-U3-20).
SECTION_ORDER: tuple[str, ...] = (
    "inventory",
    "changes",
    "top_talkers",
    "alerts",
    "evidence_range",
)

#: Tipos de evento que componen la sección Changes (BR-U3-23).
CHANGES_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "asset_first_seen",
        "asset_missing",
        "port_service_changed",
        "arp_mapping_changed",
    }
)

#: Máximo de pares en Top talkers (presentación, no contractual).
TOP_TALKERS_LIMIT = 10

_HTML_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))
_MD_ESCAPES = (("*", "\\*"), ("_", "\\_"), ("#", "\\#"), ("`", "\\`"), ("[", "\\["), ("]", "\\]"))


def esc(value: object) -> str:
    """Escapa HTML y Markdown en un valor dinámico (P5, NFR-U3-SEC-01).

    Aplicar a todo campo de red (hostnames, IPs, details, nombres de
    servicio) antes de insertarlo en el Markdown. Sin recortes: los datos
    de red son legítimos.
    """
    text = "" if value is None else str(value)
    for old, new in _HTML_ESCAPES:
        text = text.replace(old, new)
    for old, new in _MD_ESCAPES:
        text = text.replace(old, new)
    return text


@dataclass(frozen=True)
class ReportSection:
    """Sección `## heading` + cuerpo Markdown (anchor = clave de SECTION_ORDER)."""

    anchor: str
    heading: str
    body: str

    def to_markdown(self) -> str:
        return f"## {self.heading}\n\n{self.body}\n"


@dataclass(frozen=True)
class ReportRequest:
    """Rango pedido, requerido y con `from <= to` (Q10=A)."""

    date_from: date
    date_to: date

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise ValueError("date_from must be <= date_to")

    @property
    def filename(self) -> str:
        return f"reporte_{self.date_from.isoformat()}_{self.date_to.isoformat()}"


@dataclass(frozen=True)
class ReportArtifact:
    format: ReportFormat
    filename: str
    content_type: str
    data: bytes


def _table(headers: list[str], rows: Sequence[Sequence[object]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(" --- " for _ in headers) + "|"
    body = "\n".join(
        "| " + " | ".join("" if c is None else esc(c) for c in row) + " |" for row in rows
    )
    return "\n".join([head, sep, body])


def build_inventory_section(assets: list[AssetSummary]) -> ReportSection:
    """`## Inventory summary` — conteos + tabla resumen (FD §3.6.1)."""
    if not assets:
        body = "Sin activos en el inventario para el rango consultado."
        return ReportSection("inventory", "Inventory summary", body)
    present = sum(1 for a in assets if a.status == "present")
    absent = len(assets) - present
    rows = [
        [
            a.ips[0] if a.ips else "",
            a.mac or "—",
            a.hostname or "—",
            a.os_name or "desconocido",
            a.status,
            a.last_seen,
        ]
        for a in assets
    ]
    counts = f"Total: {len(assets)} · presentes: {present} · ausentes: {absent}\n\n"
    table = _table(["IP", "MAC", "Hostname", "SO", "Estado", "Last seen"], rows)
    return ReportSection("inventory", "Inventory summary", counts + table)


def build_changes_section(events: list[EventOut]) -> ReportSection:
    """`## Changes` — eventos del rango con tipo ∈ CHANGES_EVENT_TYPES (BR-U3-23)."""
    changes = [e for e in events if e.type in CHANGES_EVENT_TYPES]
    if not changes:
        return ReportSection("changes", "Changes", "Sin cambios de inventario en el rango.")
    rows = [
        [
            e.occurred_at,
            e.type,
            e.severity,
            e.asset_id,
            ", ".join(f"{k}={v}" for k, v in sorted((e.details or {}).items())),
        ]
        for e in changes
    ]
    table = _table(["Ocurrecido", "Tipo", "Severidad", "Activo", "Detalle"], rows)
    return ReportSection("changes", "Changes", table)


def build_top_talkers_section(
    talkers: list[tuple[str, str, float]],
) -> ReportSection:
    """`## Top talkers` — pares por `bytes_per_second` desc; vacío ⇒ `sin datos` (BR-U3-22).

    `talkers`: filas `(asset_id, pair, bytes_per_second)` ya agregadas.
    """
    if not talkers:
        return ReportSection(
            "top_talkers", "Top talkers", "sin datos (sin observaciones de tráfico)."
        )
    ranked = sorted(talkers, key=lambda t: t[2], reverse=True)[:TOP_TALKERS_LIMIT]
    rows = [[asset_id, pair, round(bps, 3)] for asset_id, pair, bps in ranked]
    table = _table(["Activo", "Par", "bytes/s"], rows)
    return ReportSection("top_talkers", "Top talkers", table)


def build_alerts_section(alerts: list[AlertOut]) -> ReportSection:
    """`## Alerts` — alertas del rango con estado `firing|resolved` (FD §3.6.4)."""
    if not alerts:
        return ReportSection("alerts", "Alerts", "Sin alertas en el rango.")
    rows = [
        [
            a.rule,
            a.state,
            a.metric_key,
            a.measured_value,
            a.threshold,
            a.asset_id,
            a.fired_at,
            a.resolved_at,
        ]
        for a in alerts
    ]
    table = _table(
        ["Regla", "Estado", "Métrica", "Valor", "Umbral", "Activo", "Disparada", "Resuelta"],
        rows,
    )
    return ReportSection("alerts", "Alerts", table)


def build_evidence_range_section(
    request: ReportRequest,
    source_counts: dict[str, int],
) -> ReportSection:
    """`## Evidence range` — rango pedido + fuentes consultadas + conteos (FD §3.6.5)."""
    lines = [
        f"Rango: {request.date_from.isoformat()} a {request.date_to.isoformat()} (UTC).",
        "",
        "Fuentes consultadas (API U2 por loopback):",
    ]
    for source, count in sorted(source_counts.items()):
        lines.append(f"- {esc(source)}: {count}")
    return ReportSection("evidence_range", "Evidence range", "\n".join(lines))


def render_markdown(
    request: ReportRequest,
    sections: list[ReportSection],
    generated_at: str,
) -> bytes:
    """Ensambla cabecera + `Generated at` FUERA de las secciones (BR-U3-21).

    Determinista: mismos `sections` + mismo `generated_at` ⇒ bytes idénticos.
    `generated_at` debe venir de datos persistidos/fijos para el test de
    determinismo (la fuente real lo inyecta el caller con reloj propio).
    """
    anchors = [s.anchor for s in sections]
    if anchors != list(SECTION_ORDER) or len(sections) != 5:
        raise ValueError(f"expected exactly the 5 sections in order, got {anchors}")
    parts = [
        "# Sentinel network report",
        "",
        f"Generated at: {generated_at}",
        "",
    ]
    for section in sections:
        parts.append(section.to_markdown())
        parts.append("")
    return "\n".join(parts).encode("utf-8")
