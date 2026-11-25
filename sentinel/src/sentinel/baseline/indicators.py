"""Indicadores de baseline hacia U7 (FD §3.5, BR-U6-22/23, P7).

Proyección **pura** del estado del ``ConditionService`` a tuplas
``(nombre, labels, valor)`` (formato ``Sample`` de U2/U7) — bajo demanda,
sin caché. Sin labels prohibidos por BR-21 (``src_ip``/``dst_ip``/``mac``/
``asset_id``). U6 produce; U7 expondrá vía ``/metrics``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from sentinel.foundation.metrics_contract import assert_labels

__all__ = ["Sample", "metric_samples"]

#: ``(nombre_familia, labels, valor)`` — espejo de ``core.metrics.collect.Sample``.
Sample = tuple[str, dict[str, str], float]


class _StateLike(Protocol):
    """Forma mínima de ``BaselineState`` (duck-typing, sin import circular)."""

    metric_key: str
    established: bool
    mean: float
    variance: float


def metric_samples(
    states: Iterable[_StateLike],
    active_alerts: Mapping[str, Mapping[str, Any]],
    *,
    collector_up: int,
) -> list[Sample]:
    """Materializa el estado vigente de todas las series (O(series), sin caché)."""
    samples: list[Sample] = []
    for st in states:
        metric, sep, rest = st.metric_key.partition("|")
        interface, sep2, protocol = rest.partition("|")
        if not sep or not sep2:
            continue  # clave malformada ⇒ no emitir (defensivo)
        base_labels = {"interface": interface, "protocol": protocol}
        assert_labels(base_labels)
        established = 1.0 if st.established else 0.0

        # R-01: 1 si la serie tiene una alerta firing vigente (FD §3.5).
        if metric == "bytes_per_second":
            firing = any(
                row.get("metric_key") == st.metric_key and row.get("state") == "firing"
                for row in active_alerts.values()
            )
            samples.append(
                (
                    "sentinel_traffic_threshold_exceeded",
                    dict(base_labels),
                    1.0 if firing else 0.0,
                )
            )

        # Estado vigente por serie: establishing | available (labels únicos
        # por serie ⇒ se añade ``metric`` — cardinalidad acotada, BR-21 ok).
        status_labels = {
            **base_labels,
            "state": "available" if st.established else "establishing",
            "metric": metric,
        }
        assert_labels(status_labels)
        samples.append(("sentinel_baseline_status", status_labels, 1.0))

        established_labels = {**base_labels, "metric": metric}
        assert_labels(established_labels)
        samples.append(("sentinel_baseline_established", established_labels, established))

    collector_labels = {"collector": "traffic"}
    assert_labels(collector_labels)
    samples.append(("sentinel_collector_up", collector_labels, float(collector_up)))
    return samples
