"""Validación de alcance autorizado — C12 (U4, BR-U4-06..09, ST-M1-02).

``ScopeValidator`` opera sobre la allowlist cargada por ``DiscoverySettings``:
el worker lo aplica **siempre** antes de enviar paquetes (Ruta A, defensa en
profundidad) y la API solo si el proceso tiene config de scope (Ruta B,
D-U4-04).
"""

from __future__ import annotations

from collections.abc import Sequence
from ipaddress import IPv4Address, IPv4Network, IPv6Network, ip_network

from pydantic import BaseModel, ConfigDict

from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.domain import ScopeConfig

__all__ = ["ScopeValidator", "ValidationResult"]


class ValidationResult(BaseModel):
    """Resultado de una validación de alcance (domain-entities §1.5)."""

    model_config = ConfigDict(frozen=True)

    ok: bool = True
    errors: tuple[str, ...] = ()


class ScopeValidator:
    """Allowlist en memoria: match exacto (hosts) o pertenencia a red (cidr)."""

    def __init__(self, config: DiscoverySettings | ScopeConfig) -> None:
        self._networks: tuple[IPv4Network | IPv6Network, ...] = ()
        if isinstance(config, DiscoverySettings):
            self._mode = config.scope_mode
            self._hosts = frozenset(config.hosts_list())
            networks: list[IPv4Network | IPv6Network] = []
            for raw in config.cidrs_list():
                try:
                    networks.append(ip_network(raw, strict=False))
                except ValueError:
                    continue
            self._networks = tuple(networks)
        else:
            self._mode = config.mode
            self._hosts = frozenset(host.strip() for host in config.hosts if host.strip())
            self._networks = tuple(ip_network(raw, strict=False) for raw in config.cidrs)

    @property
    def mode(self) -> str:
        return self._mode

    def validate_target(self, host: str) -> ValidationResult:
        """Un host contra la allowlist (BR-U4-06): fuera ⇒ error en ES."""
        candidate = host.strip()
        if not candidate:
            return ValidationResult(ok=False, errors=("host vacío",))
        if self._mode == "explicit_hosts":
            if candidate in self._hosts:
                return ValidationResult()
            return ValidationResult(ok=False, errors=("host fuera de alcance",))
        try:
            address = IPv4Address(candidate)
        except ValueError:
            return ValidationResult(ok=False, errors=("host fuera de alcance",))
        if any(address in network for network in self._networks):
            return ValidationResult()
        return ValidationResult(ok=False, errors=("host fuera de alcance",))

    def validate_scope(self, hosts: Sequence[str]) -> ValidationResult:
        """Todos los hosts antes de sondear (BR-U4-07) o de crear el run (BR-U4-08)."""
        errors: list[str] = []
        for host in hosts:
            result = self.validate_target(host)
            if not result.ok:
                errors.extend(result.errors)
        if errors:
            return ValidationResult(ok=False, errors=tuple(errors))
        return ValidationResult()

    def validate_ports(self, ports: Sequence[int]) -> ValidationResult:
        """Puertos de la allowlist (BR-U4-09): rango válido y no vacíos."""
        if not ports:
            return ValidationResult(ok=False, errors=("lista de puertos vacía",))
        errors: list[str] = []
        for port in ports:
            if not isinstance(port, int) or not 1 <= port <= 65535:
                errors.append(f"puerto inválido: {port}")
        if errors:
            return ValidationResult(ok=False, errors=tuple(errors))
        return ValidationResult()
