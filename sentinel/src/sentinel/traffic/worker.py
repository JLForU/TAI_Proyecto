"""Worker de ventana del sensor (U5, BR-U5-25/28/30, P1/P2/P3/P4, AVAIL).

``run_window`` síncrono de un hilo (P4): reloj → guard monótono (P2) →
fuente → acumulador → proyección U1 → log ``arp_rate`` → export chunked.
Fallo **por ventana** sin estado acumulado entre ventanas y sin circuit
breaker (P1): export agotado ⇒ ``sensor_export_failed`` + descartar;
fuente caída ⇒ ``sensor_source_error`` + descartar; en ambos el loop
continúa con la siguiente ventana (D-U5-05, NFR-AVAIL-01). SIGTERM se
atiende entre ventanas desde el CLI (AVAIL-02).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import chain
from typing import Any, Literal, Protocol

from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import Observation

from .aggregator import WindowAccumulator, to_observations, window_bounds
from .arp import arp_rate, to_arp_observations
from .client import IngestClient
from .config import TrafficSettings, load_traffic_settings
from .source import ArpPacket, IpPacket, PacketSource, SimulatedSource

__all__ = ["BatchClient", "Clock", "SensorState", "SystemClock", "WindowResult", "run_window"]

_log = get_logger("traffic.worker")


class Clock(Protocol):
    """Reloj inyectable (P9): los tests jamás tocan ``datetime`` ni ``sleep``."""

    def now(self) -> datetime: ...


@dataclass(slots=True)
class SystemClock:
    """Reloj UTC real (default de producción)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True)
class SensorState:
    """Estado entre ventanas: guard monótono (P2) + evento pendiente.

    No hay buffer de export (D-U5-05): una ventana fallida se descarta.
    ``pending`` conserva el primer evento del borde para la ventana siguiente
    (evita perder el evento que cierra el rango al consumir la fuente).
    """

    last_emitted_window_start: datetime | None = None
    pending: IpPacket | ArpPacket | None = None


@dataclass(slots=True)
class WindowResult:
    """Resultado de una ventana para el CLI y los tests (BR-U5-29)."""

    status: Literal["emitted", "export_failed", "source_error", "clock_regression"]
    window_start: datetime
    window_end: datetime
    items: int = 0
    traffic: int = 0
    arp: int = 0


class BatchClient(Protocol):
    """Seam de export (P9): ``IngestClient`` o un recorder de tests."""

    def post_batch(self, items: Sequence[Observation]) -> dict[str, Any]: ...


def run_window(
    settings: TrafficSettings | None = None,
    source: PacketSource | None = None,
    client: BatchClient | None = None,
    clock: Clock | None = None,
    state: SensorState | None = None,
) -> WindowResult:
    """Ejecuta 1 ventana completa (BR-U5-30: ``--once`` y ``--loop`` comparten este worker).

    Seams con defaults reales (P9/Q6=A): ``load_traffic_settings()``,
    ``SimulatedSource``, ``IngestClient``, reloj UTC.
    """
    cfg = settings if settings is not None else load_traffic_settings()
    src = (
        source
        if source is not None
        else SimulatedSource(seed=cfg.sim_seed, rate=cfg.sim_rate, interface=cfg.interface)
    )
    clk = clock if clock is not None else SystemClock()
    st = state if state is not None else SensorState()
    if client is not None:
        return _run_window(cfg, src, client, clk, st)
    owned = IngestClient()
    try:
        return _run_window(cfg, src, owned, clk, st)
    finally:
        owned.close()


def _run_window(
    cfg: TrafficSettings,
    src: PacketSource,
    client: BatchClient,
    clk: Clock,
    st: SensorState,
) -> WindowResult:
    window_start, window_end = window_bounds(clk.now(), cfg.window_seconds)

    # Guard monótono (P2): sin re-emisión ni "ventanas viajeras".
    if st.last_emitted_window_start is not None and window_start <= st.last_emitted_window_start:
        _log.warning(
            "window_start not after last emitted window; discarded",
            extra={
                "event": "window_clock_regression",
                "window_start": window_start.isoformat(),
                "last_emitted_window_start": st.last_emitted_window_start.isoformat(),
            },
        )
        return WindowResult(
            status="clock_regression", window_start=window_start, window_end=window_end
        )

    accumulator = WindowAccumulator(
        window_start=window_start, window_end=window_end, interface=cfg.interface
    )
    arp_events: list[ArpPacket] = []

    pending = st.pending
    st.pending = None
    try:
        stream: Iterator[IpPacket | ArpPacket] = (
            chain([pending], src.events()) if pending is not None else src.events()
        )
        for event in stream:
            if event.observed_at >= window_end:
                st.pending = event  # primer evento de la ventana siguiente (sin pérdida)
                break
            if event.observed_at < window_start:
                continue  # stale (reloj regresado o fuente retrasada)
            accumulator.add(event)
            if isinstance(event, ArpPacket):
                arp_events.append(event)
            if clk.now() >= window_end:
                break
    except Exception as exc:
        _log.error(
            "packet source failed; window discarded",
            extra={
                "event": "sensor_source_error",
                "window_start": window_start.isoformat(),
                "detail": str(exc),
            },
        )
        return WindowResult(status="source_error", window_start=window_start, window_end=window_end)

    # Cierre: proyección U1 (frontera Pydantic) + log de tasa ARP (BR-U5-19).
    traffic_items = to_observations(accumulator, sensor_id=cfg.sensor_id)
    arp_items = to_arp_observations(arp_events, sensor_id=cfg.sensor_id)
    _log.info(
        "window closed",
        extra={
            "event": "arp_rate",
            "interface": cfg.interface,
            "window_start": window_start.isoformat(),
            "arp_messages_per_second": arp_rate(accumulator.arp_count, cfg.window_seconds),
        },
    )

    items: list[Observation] = [*traffic_items, *arp_items]  # lote mixto (BR-U5-23)
    try:
        client.post_batch(items)
    except Exception as exc:
        _log.error(
            "window export failed; window discarded",
            extra={
                "event": "sensor_export_failed",
                "window_start": window_start.isoformat(),
                "detail": str(exc),
            },
        )
        return WindowResult(
            status="export_failed", window_start=window_start, window_end=window_end
        )

    st.last_emitted_window_start = window_start
    return WindowResult(
        status="emitted",
        window_start=window_start,
        window_end=window_end,
        items=len(items),
        traffic=len(traffic_items),
        arp=len(arp_items),
    )
