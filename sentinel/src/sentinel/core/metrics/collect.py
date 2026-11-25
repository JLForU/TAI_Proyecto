"""Colector real de métricas de U7 (ST-M6-01..03, P7, IP7, BR-U7-01..24).

Arquitectura híbrida (FD §3.3):

- **Contadores en proceso**: ``ApiRequestCounter``, ``CycleCounter`` y
  ``ObservationCounters`` (flows/ARP alimentados por el hook post-commit).
- **Gauges de SQLite al scrape**: alertas firing, activos, cambios de
  activo y última ventana de tráfico por serie ``(interface, protocol)``.
- **Indicadores de U6**: ``ConditionService.metric_samples()`` bajo demanda.
- **Zero-fill**: toda familia sin muestra se emite en cero con
  ``component=core``; el catálogo de ``METRIC_FAMILIES`` se preserva.
- **Validación**: ``assert_allowed`` (denylist + allowlist v2) por sample.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from sentinel.foundation.metrics_contract import (
    METRIC_FAMILIES,
    assert_allowed,
    metric_name,
)
from sentinel.foundation.models import ArpObservation, Observation, TrafficObservation

if TYPE_CHECKING:  # pragma: no cover - solo anotación (sin import runtime)
    from ..db.database import Database

__all__ = [
    "HELP_TEXT",
    "LATEST_OBS_LIMIT",
    "ApiRequestCounter",
    "CycleCounter",
    "ObservationCounters",
    "Sample",
    "collect",
    "render_prometheus",
]

#: ``(nombre_familia, labels, valor)``
Sample = tuple[str, dict[str, str], float]

#: Techo barato para la query de última ventana de tráfico por scrape (Q3=A).
LATEST_OBS_LIMIT = 500

#: HELP real por familia (14) — sin el «U2 stub» (BR-U7-08, Q11=A).
HELP_TEXT: dict[str, str] = {
    "sentinel_api_requests_total": "Total de respuestas de la API interna por estado HTTP.",
    "sentinel_discovery_cycles_total": "Total de ciclos de descubrimiento por estado.",
    "sentinel_discovery_cycles_failed_total": "Ciclos de descubrimiento fallidos o con timeout.",
    "sentinel_flows_total": "Flujos observados acumulados en ventanas de tráfico aceptadas.",
    "sentinel_arp_messages_total": "Mensajes ARP observados acumulados.",
    "sentinel_bytes_per_second": "Última tasa de bytes/s por interfaz y protocolo.",
    "sentinel_alerts_firing": "Alertas actualmente en estado firing.",
    "sentinel_baseline_established": "Indica si la línea base de la serie está establecida.",
    "sentinel_traffic_threshold_exceeded": "Indica si la serie supera el umbral R-01.",
    "sentinel_baseline_status": "Estado vigente de la línea base por serie.",
    "sentinel_collector_up": "Disponibilidad del colector según su heartbeat.",
    "sentinel_collector_heartbeat_age_seconds": "Antigüedad del heartbeat más reciente.",
    "sentinel_assets_total": "Activos registrados en el inventario.",
    "sentinel_asset_changes_total": "Eventos acumulados de cambio de activo.",
}


class ApiRequestCounter:
    """Contador en proceso de respuestas API por ``state`` (status code)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def inc(self, state: str) -> None:
        self._counts[state] = self._counts.get(state, 0) + 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)

    def total(self) -> int:
        return sum(self._counts.values())


class CycleCounter:
    """Contador en proceso de runs de discovery por ``state`` (U4, BR-U4-28).

    Espejo de ``ApiRequestCounter``: ``cycles_total`` cuenta todos los runs y
    ``cycles_failed_total`` solo ``failed``/``timeout`` (FD §3.6).
    """

    _FAILED = frozenset({"failed", "timeout"})

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, status: str) -> None:
        self._counts[status] = self._counts.get(status, 0) + 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)

    def failed_total(self) -> int:
        return sum(n for state, n in self._counts.items() if state in self._FAILED)


class ObservationCounters:
    """Contadores en proceso de tráfico/ARP alimentados por el hook (BR-U7-11).

    Solo se invocan con observaciones **aceptadas** (post-commit), por lo que
    un lote reenviado y deduplicado no duplica contadores. Se reinician con
    el proceso; Prometheus absorbe los resets (BR-U7-13).
    """

    def __init__(self) -> None:
        self._flows = 0
        self._arp_messages = 0

    def on_accepted(self, observations: Iterable[Observation]) -> None:
        for obs in observations:
            if isinstance(obs, TrafficObservation):
                self._flows += int(obs.flows)
            elif isinstance(obs, ArpObservation):
                self._arp_messages += 1

    def snapshot(self) -> dict[str, int]:
        return {"flows_total": self._flows, "arp_messages_total": self._arp_messages}


def _heartbeat_age_seconds(heartbeats: Mapping[str, str], now: float | None = None) -> float:
    if not heartbeats:
        return 0.0
    newest: float | None = None
    for iso in heartbeats.values():
        try:
            from datetime import datetime

            ts = datetime.fromisoformat(iso).timestamp()
        except ValueError:  # pragma: no cover - dato corrupto
            continue
        if newest is None or ts > newest:
            newest = ts
    if newest is None:  # pragma: no cover - todos inválidos
        return 0.0
    return max(0.0, (now if now is not None else time.time()) - newest)


def _sqlite_gauges(db: Database) -> list[Sample]:
    """Gauges de SQLite al scrape (solo lectura, FD §3.3 paso 2)."""
    with db.read() as conn:
        firing = int(
            conn.execute("SELECT COUNT(*) FROM alerts WHERE state = 'firing'").fetchone()[0]
        )
        assets = int(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0])
        changes = int(
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE type IN"
                " ('asset_first_seen','asset_missing','arp_mapping_changed',"
                "'port_service_changed')"
            ).fetchone()[0]
        )
        rows = list(
            conn.execute(
                "SELECT payload FROM observations WHERE source = 'traffic'"
                " ORDER BY observed_at DESC LIMIT ?",
                (LATEST_OBS_LIMIT,),
            )
        )

    samples: list[Sample] = [
        ("sentinel_alerts_firing", {"component": "core"}, float(firing)),
        ("sentinel_assets_total", {"component": "core"}, float(assets)),
        ("sentinel_asset_changes_total", {"component": "core"}, float(changes)),
    ]

    latest: dict[tuple[str, str], float] = {}
    for row in rows:
        try:
            payload: Any = json.loads(row["payload"])
        except (TypeError, ValueError):  # pragma: no cover - payload corrupto
            continue
        if not isinstance(payload, dict) or payload.get("source") != "traffic":
            continue
        interface = payload.get("interface")
        protocol = payload.get("protocol")
        bps = payload.get("bytes_per_second")
        if interface is None or protocol is None or bps is None:
            continue
        key = (str(interface), str(protocol))
        if key not in latest:  # primera fila = observación más reciente
            latest[key] = float(bps)

    for (interface, protocol), value in sorted(latest.items()):
        samples.append(
            (
                "sentinel_bytes_per_second",
                {"interface": interface, "protocol": protocol},
                value,
            )
        )
    return samples


def collect(
    *,
    api_requests: ApiRequestCounter | None = None,
    cycles: CycleCounter | None = None,
    heartbeats: Mapping[str, str] | None = None,
    now: float | None = None,
    condition_service: Any | None = None,
    db: Database | None = None,
    obs_counters: ObservationCounters | None = None,
) -> list[Sample]:
    """Materializa las 14 familias del contrato v2 (providers opcionales)."""
    counter = api_requests or ApiRequestCounter()
    samples: list[Sample] = []

    counts = counter.snapshot()
    if counts:
        for state, n in sorted(counts.items()):
            samples.append(
                (metric_name("api_requests_total"), {"component": "api", "state": state}, float(n))
            )
    else:
        samples.append(
            (metric_name("api_requests_total"), {"component": "api", "state": "none"}, 0.0)
        )

    cycle_counts = cycles.snapshot() if cycles is not None else {}
    if cycle_counts:
        for state, n in sorted(cycle_counts.items()):
            samples.append(
                (
                    metric_name("discovery_cycles_total"),
                    {"component": "discovery", "state": state},
                    float(n),
                )
            )
        samples.append(
            (
                metric_name("discovery_cycles_failed_total"),
                {"component": "discovery", "state": "failed"},
                float(cycles.failed_total() if cycles is not None else 0),
            )
        )
    else:
        samples.append(
            (
                metric_name("discovery_cycles_total"),
                {"component": "discovery", "state": "none"},
                0.0,
            )
        )
        samples.append(
            (
                metric_name("discovery_cycles_failed_total"),
                {"component": "discovery", "state": "none"},
                0.0,
            )
        )

    if obs_counters is not None:
        snapshot = obs_counters.snapshot()
        samples.append(
            (
                metric_name("flows_total"),
                {"component": "traffic"},
                float(snapshot["flows_total"]),
            )
        )
        samples.append(
            (
                metric_name("arp_messages_total"),
                {"component": "traffic"},
                float(snapshot["arp_messages_total"]),
            )
        )

    if db is not None:
        samples.extend(_sqlite_gauges(db))

    samples.append(
        (
            metric_name("collector_heartbeat_age_seconds"),
            {"component": "core"},
            _heartbeat_age_seconds(heartbeats or {}, now=now),
        )
    )

    if condition_service is not None:
        samples.extend(condition_service.metric_samples())

    emitted = {name for name, _, _ in samples}
    for family in METRIC_FAMILIES:
        if family in emitted:
            continue
        samples.append((family, {"component": "core"}, 0.0))

    # Validación por sample (denylist BR-21 + allowlist v2) y catálogo exacto.
    for _name, labels, _value in samples:
        assert_allowed(labels)
    names = {name for name, _, _ in samples}
    assert names == set(METRIC_FAMILIES), f"unexpected families: {names ^ set(METRIC_FAMILIES)}"
    return samples


def _type_of(name: str) -> str:
    return "counter" if name.endswith("_total") else "gauge"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace('"', '\\"')


def _sanitize_help(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", " ")


def render_prometheus(samples: Iterable[Sample]) -> str:
    """Renderiza ``samples`` como exposition text/plain de Prometheus."""
    by_family: dict[str, list[Sample]] = {}
    for sample in samples:
        by_family.setdefault(sample[0], []).append(sample)

    lines: list[str] = []
    for family in sorted(by_family):
        help_text = _sanitize_help(HELP_TEXT.get(family, f"Sentinel {family}"))
        lines.append(f"# HELP {family} {help_text}")
        lines.append(f"# TYPE {family} {_type_of(family)}")
        for name, labels, value in by_family[family]:
            assert name == family
            assert_allowed(labels)
            if labels:
                label_str = ",".join(
                    f'{k}="{_escape_label(str(v))}"' for k, v in sorted(labels.items())
                )
                lines.append(f"{name}{{{label_str}}} {_fmt(value)}")
            else:
                lines.append(f"{name} {_fmt(value)}")
    return "\n".join(lines) + "\n"


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)
