"""U4 — Configuration, scope & Discovery.

Frontera (BR-U4-26, unit-of-work §imports): todo el paquete importa solo
``sentinel.foundation`` y HTTP; nunca ``sentinel.core`` ni ``sqlite3``. La
única excepción es ``runner.py`` (puente U2 aprobado en FD §3.8), que importa
solo ``sentinel.core.discovery.trigger.DiscoveryTimeoutError``.
"""

from __future__ import annotations

from sentinel.discovery.config import DiscoverySettings, load_discovery_settings
from sentinel.discovery.domain import CycleResult, HostFinding, resolve_targets
from sentinel.discovery.scope import ScopeValidator, ValidationResult
from sentinel.discovery.worker import run_cycle

__all__ = [
    "CycleResult",
    "DiscoverySettings",
    "HostFinding",
    "ScopeValidator",
    "ValidationResult",
    "load_discovery_settings",
    "resolve_targets",
    "run_cycle",
]
