"""Emisión de evidencia JSON Lines (ST-M4-05, BR-U2-25..27, P10 base).

Una línea JSON por evento/inferencia/observación/alerta vía
``foundation.get_logger`` (JSON por línea, ISO 8601 UTC — BR-09..12) con los
campos de evidencia y ``kind ∈ {observation, inference, event, alert}``.
"""

from __future__ import annotations

from typing import Any, Literal

from sentinel.foundation.logging import get_logger

__all__ = ["EvidenceKind", "emit"]

EvidenceKind = Literal["observation", "inference", "event", "alert"]

_log = get_logger("core.evidence")


def emit(
    kind: EvidenceKind,
    event_type: str,
    *,
    asset: str | None = None,
    pair: str | None = None,
    method: str | None = None,
    protocol: str | None = None,
    condition: str | None = None,
    rule: str | None = None,
    threshold: float | int | None = None,
    measured_value: float | int | None = None,
    result: str | None = None,
    **extra: Any,
) -> None:
    """Emite una línea de evidencia.

    Siempre incluye los 9 campos de BR-U2-25 (``None`` cuando no aplica) más
    ``kind`` (BR-U2-26); ``ts/level/component/event/msg`` los añade el
    formatter de U1 (BR-09).
    """
    payload: dict[str, Any] = {"kind": kind, "event": event_type}
    payload.update(
        {
            "asset": asset,
            "pair": pair,
            "method": method,
            "protocol": protocol,
            "condition": condition,
            "rule": rule,
            "threshold": threshold,
            "measured_value": measured_value,
            "result": result,
        }
    )
    payload.update({k: v for k, v in extra.items() if v is not None})
    _log.info(str(extra.get("msg", event_type)), extra=payload)
