"""API pública de ``sentinel.foundation`` (librería pura, sin I/O — BR-19).

Re-exporta los contratos que consumen U2–U11: modelos, errores, eventos,
config, logging, contrato de métricas y retry. Importar este paquete no
tiene side effects (no lee env, no configura logging, no abre nada).
"""

from sentinel.foundation.config import Settings, load_settings
from sentinel.foundation.errors import (
    ConfigError,
    IngestionError,
    ProbeError,
    ScopeError,
    SentinelError,
    StorageError,
    ValidationError,
)
from sentinel.foundation.events import EventName, EventType
from sentinel.foundation.logging import JsonFormatter, get_logger
from sentinel.foundation.metrics_contract import (
    ALLOWED_LABELS_DEFAULT,
    FORBIDDEN_LABELS,
    METRIC_FAMILIES,
    METRIC_PREFIX,
    assert_labels,
    metric_name,
)
from sentinel.foundation.models import (
    MAX_BATCH_ITEMS,
    MAX_PORTS_PER_OBSERVATION,
    MAX_STRING_LEN,
    AlertCondition,
    ArpMapping,
    ArpObservation,
    Asset,
    Baseline,
    Batch,
    DiscoveryCycle,
    DiscoveryObservation,
    FlowPair,
    InventoryEvent,
    Observation,
    PortInfo,
    TrafficObservation,
)
from sentinel.foundation.retry import with_retries

__all__ = [
    "ALLOWED_LABELS_DEFAULT",
    "FORBIDDEN_LABELS",
    "METRIC_FAMILIES",
    "METRIC_PREFIX",
    "MAX_BATCH_ITEMS",
    "MAX_PORTS_PER_OBSERVATION",
    "MAX_STRING_LEN",
    "AlertCondition",
    "ArpMapping",
    "ArpObservation",
    "Asset",
    "Baseline",
    "Batch",
    "ConfigError",
    "DiscoveryCycle",
    "DiscoveryObservation",
    "EventType",
    "EventName",
    "FlowPair",
    "IngestionError",
    "InventoryEvent",
    "JsonFormatter",
    "Observation",
    "PortInfo",
    "ProbeError",
    "ScopeError",
    "SentinelError",
    "Settings",
    "StorageError",
    "TrafficObservation",
    "ValidationError",
    "assert_labels",
    "get_logger",
    "load_settings",
    "metric_name",
    "with_retries",
]
