"""Puente runner ↔ U2 (FD §3.8, BR-U4-36): ``CycleRunnerImpl``.

Satisface el protocolo ``CycleRunner.run(hosts, timeout_seconds) -> int`` de
``core.discovery.trigger`` (duck-typing; el protocolo no se importa). Único
módulo del paquete autorizado a importar de ``sentinel.core`` — y solo
``DiscoveryTimeoutError``, la excepción que U2 mapea a ``status="timeout"``
(domain-entities §2; composición de arranque aprobada en FD §3.8).
"""

from __future__ import annotations

from sentinel.core.discovery.trigger import DiscoveryTimeoutError
from sentinel.discovery.client import IngestClient
from sentinel.discovery.config import DiscoverySettings, load_discovery_settings
from sentinel.discovery.domain import CycleResult
from sentinel.discovery.scanner import Scanner, create_scanner
from sentinel.discovery.worker import run_cycle
from sentinel.foundation.errors import ProbeError, ScopeError

__all__ = ["CycleRunnerImpl"]


class CycleRunnerImpl:
    """Runner con defaults reales y seams por constructor (P9/Q6=A)."""

    def __init__(
        self,
        settings: DiscoverySettings | None = None,
        *,
        scanner: Scanner | None = None,
        client: IngestClient | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._settings = settings if settings is not None else load_discovery_settings()
        self._scanner = scanner if scanner is not None else create_scanner(self._settings)
        self._client = client if client is not None else IngestClient()
        self._timeout = (
            timeout_seconds if timeout_seconds is not None else self._settings.timeout_seconds
        )

    @property
    def settings(self) -> DiscoverySettings:
        return self._settings

    def run(self, hosts: list[str], timeout_seconds: int) -> int:
        """Un ciclo completo; devuelve ``hosts_seen`` (protocolo U2).

        - ``timeout`` (parciales ya ingeridos con ``reconcile=false``) ⇒
          ``DiscoveryTimeoutError`` (U2 ⇒ ``status="timeout"``).
        - Scope/escáner/ingesta ⇒ la excepción propaga (U2 ⇒ ``failed``).
        """
        result = run_cycle(
            self._settings,
            self._scanner,
            self._client,
            timeout_seconds,
            hosts=hosts,
        )
        return self._post(result)

    def run_once(self) -> int:
        """Ciclo standalone sobre la allowlist de config (CLI ``--once``)."""
        result = run_cycle(self._settings, self._scanner, self._client, self._timeout)
        return self._post(result)

    @staticmethod
    def _post(result: CycleResult) -> int:
        if result.status == "timeout":
            raise DiscoveryTimeoutError(result.error or "timeout")
        if result.status == "failed":
            cause = result.error or "cycle failed"
            if cause == "scope_violation":
                raise ScopeError(cause)
            raise ProbeError(cause)
        return result.hosts_seen
