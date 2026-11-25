"""CLI del worker de discovery (U4, TS-U4-06, FD §3.7, BR-U4-30/32).

``python -m sentinel.discovery --once``            → 1 ciclo (CronJob U9)
``python -m sentinel.discovery --loop [--interval]`` → bucle de demo (sin chart)

Códigos de salida: ``completed ⇒ 0``; ``timeout``/``failed`` ⇒ 1 (el Job se
marca fallido en K8s). En ``--loop`` un fallo solo loguea y sigue (P1: sin
circuit breaker). FQ1=C: sin reporte HTTP de fallo al Core.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from time import sleep

from sentinel.discovery.client import IngestClient
from sentinel.discovery.config import load_discovery_settings
from sentinel.discovery.scanner import create_scanner
from sentinel.discovery.worker import run_cycle
from sentinel.foundation.errors import ConfigError, SentinelError
from sentinel.foundation.logging import get_logger

__all__ = ["main"]

_log = get_logger("discovery.cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sentinel.discovery")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run a single cycle and exit")
    mode.add_argument("--loop", action="store_true", help="run cycles forever (demo mode)")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        metavar="MIN",
        help="minutes between cycles (--loop only; default SENTINEL_DISCOVERY_INTERVAL_MIN)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del CLI; devuelve el código de salida (BR-U4-32)."""
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    try:
        settings = load_discovery_settings()
    except ConfigError as exc:
        _log.error(
            "invalid discovery configuration",
            extra={"event": "discovery_cycle_failed", "cause": "config_error", "detail": str(exc)},
        )
        return 1

    scanner = create_scanner(settings)
    client = IngestClient()
    interval_minutes = args.interval if args.interval is not None else settings.interval_minutes
    if interval_minutes < 1:
        _log.error(
            "invalid interval",
            extra={"event": "discovery_cycle_failed", "cause": "config_error"},
        )
        return 1

    while True:
        exit_code = _run_one(settings, scanner, client, settings.timeout_seconds)
        if args.once:
            return exit_code
        sleep(interval_minutes * 60)


def _run_one(settings, scanner, client, timeout_seconds: int) -> int:  # type: ignore[no-untyped-def]
    """Un ciclo standalone: exit 0 en completed; 1 + log en timeout/failed."""
    try:
        result = run_cycle(settings, scanner, client, timeout_seconds)
    except SentinelError as exc:
        _log.error(
            "discovery cycle failed",
            extra={"event": "discovery_cycle_failed", "cause": exc.code, "detail": str(exc)},
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - el CLI no debe morir sin log
        _log.error(
            "discovery cycle failed",
            extra={"event": "discovery_cycle_failed", "cause": "unexpected", "detail": str(exc)},
        )
        return 1

    if result.status == "completed":
        return 0
    _log.error(
        "discovery cycle failed",
        extra={
            "event": "discovery_cycle_failed",
            "cause": result.error or result.status,
            "hosts_seen": result.hosts_seen,
        },
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
