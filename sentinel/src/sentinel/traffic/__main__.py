"""CLI del sensor de tráfico (U5, TS-U5-08, BR-U5-29/30).

``python -m sentinel.traffic --once``  → 1 ventana → exit ``0`` (emitida) / ``1``
``python -m sentinel.traffic --loop``   → ventanas continuas (demo / Deployment U9)

Ambos modos comparten ``run_window`` (BR-U5-30); el reloj y la fuente son
inyectables ⇒ los tests corren sin ``sleep`` (MNT-02). En ``--loop`` un fallo
por ventana solo loguea y sigue (P1, sin circuit breaker). SIGTERM se atiende
**entre** ventanas ⇒ exit ``0`` (AVAIL-02).
"""

from __future__ import annotations

import argparse
import signal
import sys
from collections.abc import Sequence
from time import sleep, time

from sentinel.foundation.errors import ConfigError
from sentinel.foundation.logging import get_logger

from .client import IngestClient
from .config import load_traffic_settings
from .source import SimulatedSource
from .worker import SensorState, SystemClock, run_window

__all__ = ["main"]

_log = get_logger("traffic.cli")

_TERMINATE = False


def _handle_sigterm(_signum: int, _frame: object) -> None:
    global _TERMINATE
    _TERMINATE = True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sentinel.traffic")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run a single window and exit")
    mode.add_argument("--loop", action="store_true", help="run windows forever (demo mode)")
    return parser


def _sleep(seconds: float) -> None:
    """Seam de sueño (los tests no duermen, MNT-02)."""
    sleep(seconds)


def _sleep_until_next_boundary(window_seconds: int) -> None:
    """Duerme hasta el próximo borde de ventana en slices cortos.

    Los slices permiten atender SIGTERM entre ventanas (AVAIL-02) con
    latencia ≤ 0.25 s.
    """
    now = time()
    target = now + (window_seconds - (now % window_seconds))
    while not _TERMINATE:
        remaining = target - time()
        if remaining <= 0:
            return
        _sleep(min(0.25, remaining))


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del CLI; devuelve el código de salida (BR-U5-29)."""
    global _TERMINATE
    _TERMINATE = False
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    try:
        settings = load_traffic_settings()
    except ConfigError as exc:
        _log.error(
            "invalid traffic configuration",
            extra={
                "event": "sensor_config_failed",
                "cause": "config_error",
                "detail": str(exc),
            },
        )
        return 1

    source = SimulatedSource(
        seed=settings.sim_seed, rate=settings.sim_rate, interface=settings.interface
    )
    client = IngestClient()
    clock = SystemClock()
    state = SensorState()

    if args.loop:
        signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        while True:
            result = run_window(settings, source, client, clock, state)
            if args.once:
                return 0 if result.status == "emitted" else 1
            if _TERMINATE:
                return 0
            _sleep_until_next_boundary(settings.window_seconds)
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
