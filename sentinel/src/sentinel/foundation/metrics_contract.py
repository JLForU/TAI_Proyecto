"""Contrato de métricas de Sentinel (BR-20..BR-22).

Foundation **no** recolecta ni expone métricas: solo define prefijo,
catálogo de familias y labels válidos. U7 (``MetricsExporter``) importa
estas constantes. Prohibido por cardinalidad: ``src_ip``, ``dst_ip``,
``mac``, ``asset_id``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

__all__ = [
    "ALLOWED_LABELS_DEFAULT",
    "FORBIDDEN_LABELS",
    "METRIC_FAMILIES",
    "METRIC_PREFIX",
    "assert_allowed",
    "assert_labels",
    "metric_name",
]

METRIC_PREFIX = "sentinel_"

FORBIDDEN_LABELS = frozenset({"src_ip", "dst_ip", "mac", "asset_id"})

#: Allowlist v2 (U7): 5 labels base de U1 + ``collector``/``metric`` de U6.
ALLOWED_LABELS_DEFAULT = frozenset(
    {"component", "protocol", "interface", "rule", "state", "collector", "metric"}
)

#: Catálogo v2 de 14 familias (nombres completos; valores en U7).
METRIC_FAMILIES: tuple[str, ...] = (
    "sentinel_discovery_cycles_total",
    "sentinel_discovery_cycles_failed_total",
    "sentinel_flows_total",
    "sentinel_bytes_per_second",
    "sentinel_arp_messages_total",
    "sentinel_alerts_firing",
    "sentinel_baseline_established",
    "sentinel_traffic_threshold_exceeded",
    "sentinel_baseline_status",
    "sentinel_collector_up",
    "sentinel_collector_heartbeat_age_seconds",
    "sentinel_api_requests_total",
    "sentinel_assets_total",
    "sentinel_asset_changes_total",
)

_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def metric_name(name: str) -> str:
    """Devuelve el nombre completo ``sentinel_<name>`` (BR-20).

    Idempotente si ``name`` ya lleva el prefijo. Lanza ``ValueError`` si el
    nombre (sin prefijo) no cumple ``[a-z0-9_]+``.
    """
    bare = name[len(METRIC_PREFIX) :] if name.startswith(METRIC_PREFIX) else name
    if not bare or not _NAME_RE.match(bare):
        raise ValueError(
            f"invalid metric name {name!r}: must match [a-z0-9_]+ after '{METRIC_PREFIX}'"
        )
    return METRIC_PREFIX + bare


def assert_labels(labels: Mapping[str, Any]) -> None:
    """Valida que ningún label esté en :data:`FORBIDDEN_LABELS` (BR-21).

    Lanza ``ValueError`` con el label prohibido encontrados.
    """
    forbidden = FORBIDDEN_LABELS.intersection(labels)
    if forbidden:
        raise ValueError(f"forbidden metric labels (cardinality): {sorted(forbidden)}")


def assert_allowed(labels: Mapping[str, Any]) -> None:
    """Denylist BR-21 **y** allowlist v2 por sample (BR-U7-03/04).

    Lanza ``ValueError`` si algún label está prohibido por cardinalidad o si
    no pertenece a :data:`ALLOWED_LABELS_DEFAULT`. ``assert_labels`` no cambia
    para mantener compatibilidad con U6.
    """
    assert_labels(labels)
    unknown = set(labels).difference(ALLOWED_LABELS_DEFAULT)
    if unknown:
        raise ValueError(f"labels outside metric allowlist: {sorted(unknown)}")
